"""Auswertung eines Zonenkapitels: Läufe des Sprachmodells, Schranken, neue Regelwerksversionen (Plan 3.4).

Datenbanktransaktionen umschließen nie einen Aufruf der Claude API (Minuten). Jeder Lauf wird sofort mit
Kosten gespeichert; eine Wiederholung nach einem Fehler nutzt bereits erfolgreiche Läufe derselben Eingabe.
"""

import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.claude import ExtractionError, ExtractionRequest, RuleExtractor
from app.platform import storage
from app.platform.db import utcnow
from app.platform.logging import get_logger
from app.rules import pdf
from app.rules.domain import ENGINE_VERSION, PROMPT_VERSION
from app.rules.domain.assess import AssessedRule, DocumentPages, assess_rule, consensus, coverage
from app.rules.domain.extraction import parse_output
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)

log = get_logger("rules_extract")
ACTOR = "system:rules_extract"
SessionFactory = Callable[[], AbstractContextManager[Session]]
RUNNING_STALE_AFTER = timedelta(minutes=70)
"""Länger als das Zeitlimit des Jobs (60 min) „läuft“ kein Kapitel; danach gilt der Lauf als abgebrochen."""


class RetryableExtractionError(Exception):
    """Der Job soll es erneut versuchen (Überlastung, Netz)."""


@dataclass(frozen=True)
class ChapterOutcome:
    status: str
    """`succeeded`, `skipped`, `failed`, `budget_exceeded`, `not_configured`."""
    detail: str | None = None
    cost_usd: float = 0.0
    counts: dict[str, int] | None = None


def input_hash(settings: Settings, source_sha256: str, chapter: RegulationChapter) -> str:
    payload = {
        "source": source_sha256,
        "chapter": [chapter.code, chapter.first_page, chapter.last_page],
        "general": chapter.general_pages,
        "sectors": sorted(chapter.sectors),
        "model": settings.rules_model,
        "effort": settings.rules_effort,
        "runs": settings.rules_runs,
        "prompt": PROMPT_VERSION,
        "engine": ENGINE_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def month_cost(session: Session, now: datetime | None = None) -> float:
    current = now or utcnow()
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    total = session.execute(
        select(func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0)).where(
            RuleExtractionRun.created_at >= start
        )
    ).scalar_one()
    return float(total)


def extract_chapter(
    sessions: SessionFactory,
    settings: Settings,
    chapter_id: uuid.UUID,
    extractor_factory: Callable[[], RuleExtractor],
    *,
    force: bool = False,
    final_attempt: bool = True,
    skip_if_running: bool = True,
) -> ChapterOutcome:
    # 1. Lesen
    with sessions() as session:
        chapter = session.get(RegulationChapter, chapter_id)
        if chapter is None:
            return ChapterOutcome("skipped", "chapter_missing")
        plan = session.get(LandUsePlan, chapter.land_use_plan_id)
        if plan is None or plan.status != "active":
            return ChapterOutcome("skipped", "plan_not_active")
        source = session.get(SourceFile, chapter.source_file_id)
        assert source is not None
        chapter_pages = list(range(chapter.first_page, chapter.last_page + 1))
        general_pages = [p for p in chapter.general_pages if p not in set(chapter_pages)]
        page_texts = {
            p.page: p.text
            for p in session.execute(
                select(SourcePage).where(
                    SourcePage.source_file_id == source.id, SourcePage.page.in_(chapter_pages + general_pages)
                )
            ).scalars()
        }
        digest = input_hash(settings, source.sha256, chapter)
        if not force and chapter.status == "succeeded" and chapter.input_hash == digest:
            return ChapterOutcome("skipped", "unchanged")
        if (
            skip_if_running
            and not force
            and chapter.status == "extracting"
            and utcnow() - chapter.updated_at < RUNNING_STALE_AFTER
        ):
            # Ein anderer Job wertet gerade aus; ein zweiter Lauf kostete doppelt. Eine Wiederholung desselben
            # Jobs (nach Absturz oder Zeitüberschreitung) setzt skip_if_running=False
            return ChapterOutcome("skipped", "already_running")
        if settings.anthropic_api_key is None:
            chapter.status, chapter.error, chapter.updated_at = "failed", "not_configured", utcnow()
            session.commit()
            return ChapterOutcome("not_configured")
        spent = month_cost(session)
        if spent >= settings.rules_budget_month_usd:
            chapter.status, chapter.error, chapter.updated_at = "failed", "budget_exceeded", utcnow()
            session.commit()
            log.error(
                "rules_budget_exceeded", spent_usd=round(spent, 2), budget_usd=settings.rules_budget_month_usd
            )
            return ChapterOutcome("budget_exceeded", f"{spent:.2f}")
        reusable: dict[int, RuleExtractionRun] = {}
        if not force:
            for run in session.execute(
                select(RuleExtractionRun)
                .where(
                    RuleExtractionRun.chapter_id == chapter.id,
                    RuleExtractionRun.input_hash == digest,
                    RuleExtractionRun.status == "succeeded",
                )
                .order_by(RuleExtractionRun.created_at.desc())
            ).scalars():
                reusable.setdefault(run.run_no, run)
        chapter.status, chapter.error, chapter.updated_at = "extracting", None, utcnow()
        session.commit()
        sectors = sorted(chapter.sectors)
        chapter_code = chapter.code
        storage_key, file_id = source.storage_key, source.id

    # 2. Läufe des Sprachmodells (ohne offene Transaktion)
    data = storage.get_bytes(storage_key)
    request = ExtractionRequest(
        chapter_code=chapter_code,
        sectors=sectors,
        chapter_pdf=pdf.extract_pages(data, chapter_pages),
        chapter_pages=chapter_pages,
        general_pdf=pdf.extract_pages(data, general_pages) if general_pages else None,
        general_pages=general_pages,
    )
    outputs: list[tuple[uuid.UUID, dict[str, Any]]] = []
    cost = 0.0
    model_used = settings.rules_model
    for run_no in range(1, settings.rules_runs + 1):
        if run_no in reusable and reusable[run_no].output is not None:
            outputs.append((reusable[run_no].id, reusable[run_no].output or {}))
            continue
        try:
            response = extractor_factory().extract(request)
        except ExtractionError as exc:
            with sessions() as session:
                session.add(
                    RuleExtractionRun(
                        chapter_id=chapter_id,
                        run_no=run_no,
                        input_hash=digest,
                        model=settings.rules_model,
                        prompt_version=PROMPT_VERSION,
                        status="failed",
                        error=exc.reason[:300],
                        usage=exc.usage,
                        cost_usd=_cost(settings, exc.usage),
                        created_by=ACTOR,
                    )
                )
                current = session.get(RegulationChapter, chapter_id)
                if current is not None and (not exc.retryable or final_attempt):
                    current.status, current.error, current.updated_at = "failed", exc.reason[:300], utcnow()
                elif current is not None:
                    current.status, current.updated_at = "pending", utcnow()
                session.commit()
            if exc.retryable and not final_attempt:
                raise RetryableExtractionError(exc.reason) from exc
            return ChapterOutcome("failed", exc.reason, cost)
        cost += response.cost_usd
        model_used = response.model
        with sessions() as session:
            run = RuleExtractionRun(
                chapter_id=chapter_id,
                run_no=run_no,
                input_hash=digest,
                model=response.model,
                prompt_version=PROMPT_VERSION,
                status="succeeded",
                stop_reason=response.stop_reason,
                served_by_fallback=response.served_by_fallback,
                usage=response.usage,
                cost_usd=response.cost_usd,
                duration_ms=response.duration_ms,
                request_id=response.request_id,
                output=response.output,
                created_by=ACTOR,
            )
            session.add(run)
            session.commit()
            outputs.append((run.id, response.output))

    # 3. Schranken und Abgleich
    documents = DocumentPages(general=general_pages, chapter=chapter_pages)
    sector_set = set(sectors)
    runs_assessed: list[list[AssessedRule]] = []
    dropped = 0
    for _run_id, output in outputs:
        try:
            extracted = parse_output(output)
        except ValueError:
            extracted = []
        assessed = [assess_rule(r, sector_set, documents, page_texts) for r in extracted]
        dropped += sum(1 for a in assessed if a is None)
        runs_assessed.append([a for a in assessed if a is not None])
    final = consensus(runs_assessed, sectors)

    # 4. Schreiben
    counts_total: dict[str, int] = defaultdict(int)
    with sessions() as session:
        chapter = session.get(RegulationChapter, chapter_id)
        if chapter is None:
            return ChapterOutcome("skipped", "chapter_missing")
        by_sector: dict[str, list[AssessedRule]] = defaultdict(list)
        for rule in final:
            by_sector[rule.sector].append(rule)
        for sector in sectors:
            rules = by_sector.get(sector, [])
            counts = coverage(rules)
            for key, value in counts.items():
                counts_total[key] += value
            _write_version(
                session,
                chapter,
                sector,
                rules,
                counts | {"dropped": dropped},
                file_id,
                [run_id for run_id, _ in outputs],
                digest,
                model_used,
            )
        chapter.status, chapter.input_hash, chapter.error, chapter.updated_at = (
            "succeeded",
            digest,
            None,
            utcnow(),
        )
        session.commit()
    log.info(
        "rules_extracted", chapter=chapter_code, sectors=sectors, cost_usd=round(cost, 4), **counts_total
    )
    return ChapterOutcome("succeeded", None, cost, dict(counts_total))


def _cost(settings: Settings, usage: dict[str, int]) -> float:
    from app.integrations.claude import prices

    return prices(settings).cost(usage) if usage else 0.0


def _write_version(
    session: Session,
    chapter: RegulationChapter,
    sector: str,
    rules: list[AssessedRule],
    counts: dict[str, int],
    source_file_id: uuid.UUID,
    run_ids: list[uuid.UUID],
    digest: str,
    model: str,
) -> None:
    rule_set = session.execute(
        select(RuleSet)
        .where(RuleSet.land_use_plan_id == chapter.land_use_plan_id, RuleSet.zone_code == sector)
        .with_for_update()
    ).scalar_one_or_none()
    if rule_set is None:
        rule_set = RuleSet(
            land_use_plan_id=chapter.land_use_plan_id,
            zone_code=sector,
            chapter_id=chapter.id,
            created_by=ACTOR,
        )
        session.add(rule_set)
        session.flush()
    current = (
        session.get(RuleSetVersion, rule_set.current_version_id) if rule_set.current_version_id else None
    )
    number = (
        session.execute(
            select(func.coalesce(func.max(RuleSetVersion.version), 0)).where(
                RuleSetVersion.rule_set_id == rule_set.id
            )
        ).scalar_one()
        + 1
    )
    version = RuleSetVersion(
        rule_set_id=rule_set.id,
        version=number,
        status="simulated",
        origin="extraction",
        based_on_id=current.id if current else None,
        extraction_run_ids=run_ids,
        engine_version=ENGINE_VERSION,
        prompt_version=PROMPT_VERSION,
        model=model,
        input_hash=digest,
        coverage=counts,
        created_by=ACTOR,
    )
    session.add(version)
    session.flush()
    for rule in rules:
        session.add(
            Rule(
                rule_set_version_id=version.id,
                kind=rule.kind,
                building_kind=rule.building_kind,
                status=rule.status,
                reason=rule.reason,
                detail=rule.detail,
                params=rule.params,
                source_file_id=source_file_id if rule.page is not None else None,
                page=rule.page,
                quote=rule.quote,
                quote_verified=rule.quote_verified,
                similarity=rule.similarity,
                confidence=rule.confidence,
                notes=rule.notes or None,
                alternatives=[asdict_safe(a) for a in rule.alternatives],
                origin="extraction",
                created_by=ACTOR,
            )
        )
    if current is not None and current.status == "office_reviewed":
        # Vom Büro geprüft hat Vorrang vor einer neuen automatischen Auswertung desselben Planstands
        version.note = f"not_current:office_reviewed_v{current.version}"
    else:
        if current is not None:
            current.status = "retired"
        rule_set.current_version_id = version.id
    rule_set.chapter_id = chapter.id
    rule_set.updated_at = utcnow()


def asdict_safe(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
