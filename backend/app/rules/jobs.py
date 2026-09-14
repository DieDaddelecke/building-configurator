"""Hintergrundjobs des Moduls G2 (Spez. 7, Plan 3.4).

`plu_import`: wöchentlich je Gemeinde des Einzugsgebiets; erkennt neue Planstände (Spez. 5.2.5,
`plu_update_check`) und stößt die Auswertung neuer Kapitel an.
`rules_extract`: ein Zonenkapitel mit dem Sprachmodell auswerten; bis 2 Läufe, Minuten je Lauf.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import httpx2
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.claude import ClaudeExtractor, RuleExtractor
from app.integrations.http import ExternalServiceError, new_client
from app.platform.db import get_sessionmaker
from app.platform.jobs import JobContext, job, periodic
from app.platform.jobs.registry import get_job_spec
from app.platform.logging import get_logger
from app.rules import extract, plan_import
from app.rules.extract import RetryableExtractionError

log = get_logger("rules_jobs")


# Austauschbar für Tests
def client_factory() -> httpx2.Client:
    return new_client(get_settings())


def gpu_source_factory(client: httpx2.Client) -> plan_import.GpuSource:
    return plan_import.ApiGpu(client, get_settings())


def extractor_factory() -> RuleExtractor:
    return ClaudeExtractor(get_settings())


@contextmanager
def _session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@job("plu_import", max_attempts=3, timeout_seconds=900)
def plu_import(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    communes = payload.get("communes") or settings.cadastre_communes
    force = bool(payload.get("force", False))
    outcome: dict[str, Any] = {}
    failed: list[str] = []
    with client_factory() as client, ctx.session() as session:
        source = gpu_source_factory(client)
        for commune in communes:
            try:
                result = plan_import.import_commune(session, source, settings, commune, force=force)
            except (ExternalServiceError, ValueError) as exc:
                session.rollback()
                failed.append(f"{commune}: {exc}")
                outcome[commune] = {"status": "failed", "error": str(exc)}
                if ctx.attempt >= get_job_spec("plu_import").max_attempts:
                    plan_import._set_commune(session, commune, "failed", error=str(exc)[:500])
                    session.commit()
                continue
            outcome[commune] = {
                "status": result.status,
                "plan": result.land_use_plan_id,
                "chapters": result.chapters,
                "zones": result.zones,
                "notes": result.notes,
            }
    if failed:
        raise RuntimeError("plu_import_failed: " + "; ".join(failed))
    return outcome


periodic("plu_import", kind="plu_import", every=timedelta(days=7))


@job("rules_extract", max_attempts=3, timeout_seconds=3600)
def rules_extract(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    final_attempt = ctx.attempt >= get_job_spec("rules_extract").max_attempts
    try:
        result = extract.extract_chapter(
            _session,
            get_settings(),
            uuid.UUID(payload["chapter_id"]),
            extractor_factory,
            force=bool(payload.get("force", False)),
            final_attempt=final_attempt,
            skip_if_running=ctx.attempt == 1,
        )
    except RetryableExtractionError as exc:
        raise RuntimeError(f"rules_extract_retry: {exc}") from exc
    if result.status in ("failed", "budget_exceeded", "not_configured"):
        # Nicht wiederholen: jeder weitere Versuch kostet und scheitert erneut. Das Kapitel steht auf `failed`
        # und erscheint in der Abdeckung; der Fehler im Log löst den Alarm aus (Plan 6.8).
        log.error(
            "rules_extract_failed", chapter=payload["chapter_id"], status=result.status, detail=result.detail
        )
    return {
        "status": result.status,
        "detail": result.detail,
        "cost_usd": result.cost_usd,
        "counts": result.counts,
    }
