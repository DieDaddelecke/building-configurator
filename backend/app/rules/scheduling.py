"""Auswertung einplanen und wieder aufnehmen: Import und Kapitel auf Anforderung, stündliche
Wiederaufnahme liegengebliebener Kapitel (`rules_housekeeping`, D11; aus `service.py` gelöst,
REFACTORING_PLAN S19)."""

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.platform.problems import Problem
from app.rules.domain import ENGINE_VERSION
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    RuleExtractionRun,
)
from app.rules.runs import RUNNING_STALE_AFTER, month_cost

log = get_logger("rules_service")
PENDING_WITHOUT_JOB_AFTER = timedelta(minutes=30)
RETRY_TRANSIENT_AFTER = timedelta(hours=24)
RETRY_TRANSIENT_MAX_FAILED_RUNS_WEEK = 6
TRANSIENT_ERRORS = ("rate_limited", "http_5", "transport:", "interrupted:")
"""Gründe, die sich von selbst erledigen können. `refusal`, `max_tokens` eines einzelnen Sektors,
`bad_request`, `auth`, `chapter_too_long` brauchen eine Änderung und bleiben für den Betrieb stehen."""


def enqueue_import(db: Session, communes: list[str] | None, force: bool, actor_id: str) -> uuid.UUID:
    import app.rules.jobs  # noqa: F401  Jobarten anmelden (lokal, sonst Importzyklus)

    job_id = enqueue(db, "plu_import", {"communes": communes, "force": force}, created_by=actor_id)
    db.commit()
    return job_id


_ACTIVE_EXTRACT_JOB = text(
    "SELECT id FROM job WHERE kind = 'rules_extract' AND status IN ('queued', 'running') "
    "AND payload->>'chapter_id' = :chapter ORDER BY created_at LIMIT 1"
)


def _active_extract_job(db: Session, chapter_id: uuid.UUID) -> uuid.UUID | None:
    return db.execute(_ACTIVE_EXTRACT_JOB, {"chapter": str(chapter_id)}).scalar()


def enqueue_extract(db: Session, chapter_id: uuid.UUID, force: bool, actor_id: str) -> uuid.UUID:
    """Kapitel auswerten. Wartet oder läuft schon ein Job für das Kapitel, bleibt es bei diesem: ein zweiter
    Klick kostet nicht noch einmal."""
    import app.rules.jobs  # noqa: F401

    chapter = db.get(RegulationChapter, chapter_id)
    if chapter is None:
        raise Problem(404, "not_found")
    active = _active_extract_job(db, chapter_id)
    if active is not None:
        return active
    if chapter.status != "extracting":
        chapter.status, chapter.updated_at = "pending", utcnow()
    job_id = enqueue(
        db, "rules_extract", {"chapter_id": str(chapter_id), "force": force}, created_by=actor_id
    )
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="regulation_chapter.extract",
        entity_type="regulation_chapter",
        entity_id=str(chapter_id),
        after={"force": force},
    )
    db.commit()
    return job_id


def housekeeping(db: Session, settings: Settings) -> dict[str, Any]:
    """Liegengebliebene und aus behebbarem Grund gescheiterte Kapitel wieder aufnehmen (stündlich, D11).

    - `extracting` länger als das Zeitlimit: abgebrochen (`interrupted:stale`).
    - `pending` ohne wartenden Job: neu einplanen.
    - `not_configured`, sobald ein Schlüssel eingetragen ist; `budget_exceeded`, sobald das Budget wieder
      reicht (neuer Monat, höheres Budget); vorübergehende Fehler nach 24 h, höchstens 6 gescheiterte Aufrufe
      je Woche.
    - Ausgewertet mit älterer Version der Schranken: neu bewerten (ohne Aufruf, wenn die Antworten vorliegen).
    """
    import app.rules.jobs  # noqa: F401

    now = utcnow()
    chapters = list(
        db.execute(
            select(RegulationChapter)
            .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
            .where(LandUsePlan.status == "active", func.cardinality(RegulationChapter.sectors) > 0)
            .with_for_update(of=RegulationChapter, skip_locked=True)
        ).scalars()
    )
    budget_left = month_cost(db) < settings.rules_budget_month_usd
    counts: dict[str, int] = defaultdict(int)
    for chapter in chapters:
        if chapter.status == "extracting" and now - chapter.updated_at > RUNNING_STALE_AFTER:
            chapter.status, chapter.error, chapter.updated_at = "failed", "interrupted:stale", now
            counts["stale"] += 1
        reason = _restart_reason(db, settings, chapter, now, budget_left)
        if reason is None or _active_extract_job(db, chapter.id) is not None:
            continue
        chapter.status, chapter.updated_at = "pending", now
        enqueue(
            db,
            "rules_extract",
            {"chapter_id": str(chapter.id)},
            idempotency_key=f"rules_housekeeping:{chapter.id}:{reason}:{now:%Y%m%d%H}",
            created_by=f"system:rules_housekeeping:{reason}",
        )
        counts[reason] += 1
    db.commit()
    if counts:
        log.info("rules_housekeeping", **counts)
    return dict(counts)


def _restart_reason(
    db: Session, settings: Settings, chapter: RegulationChapter, now: Any, budget_left: bool
) -> str | None:
    if chapter.status == "pending":
        return "pending" if now - chapter.updated_at > PENDING_WITHOUT_JOB_AFTER else None
    if chapter.status == "succeeded":
        stale_engine = chapter.engine_version is not None and chapter.engine_version != ENGINE_VERSION
        return "engine_changed" if stale_engine else None
    if chapter.status != "failed" or chapter.error is None:
        return None
    if chapter.error == "not_configured":
        return "configured" if settings.openrouter_api_key is not None else None
    if chapter.error == "budget_exceeded":
        return "budget" if budget_left else None
    if chapter.error.startswith(TRANSIENT_ERRORS) and now - chapter.updated_at > RETRY_TRANSIENT_AFTER:
        failed_week = db.execute(
            select(func.count())
            .select_from(RuleExtractionRun)
            .where(
                RuleExtractionRun.chapter_id == chapter.id,
                RuleExtractionRun.status == "failed",
                RuleExtractionRun.created_at > now - timedelta(days=7),
            )
        ).scalar_one()
        return "transient" if failed_week < RETRY_TRANSIENT_MAX_FAILED_RUNS_WEEK else None
    return None
