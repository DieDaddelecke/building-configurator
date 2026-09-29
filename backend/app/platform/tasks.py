"""Periodische Aufgaben der Plattform: Aufbewahrung und Aufräumen (Plan 6.6)."""

from datetime import timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import audit
from app.platform.jobs import JobContext, job, periodic

FINISHED_JOB_RETENTION_DAYS = 14


def _delete(session: Session, sql: str, params: dict[str, Any] | None = None) -> int:
    result = cast(CursorResult[Any], session.execute(text(sql), params or {}))
    return result.rowcount


@job("retention_cleanup", timeout_seconds=1800, max_attempts=1)
def retention_cleanup(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Löscht anonyme Projekte 90 Tage nach der letzten Aktivität (Spez. 10.2).

    Modul A erweitert die Bedingung um Projekte ohne Kontakt; Projekte mit Anfrage bleiben. Projekte
    mit Eigentümer (Architektenkonto, AN1) oder Organisation (auch per API-Schlüssel angelegt, AN6) sind
    keine Kundenprojekte und bleiben ebenfalls (UP06).
    """
    days = get_settings().project_retention_days
    with ctx.session() as session:
        deleted = _delete(
            session,
            "DELETE FROM project WHERE status = 'draft' AND owner_staff_user_id IS NULL "
            "AND organisation_id IS NULL "
            "AND last_activity_at < now() - make_interval(days => :days)",
            {"days": days},
        )
        if deleted:
            audit.record(
                session,
                actor_type="system",
                actor_id="retention_cleanup",
                action="project.retention_delete",
                entity_type="project",
                after={"deleted": deleted, "retention_days": days},
            )
        session.commit()
    return {"projects_deleted": deleted}


@job("housekeeping", timeout_seconds=300, max_attempts=1)
def housekeeping(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Erledigte Jobs, abgelaufene Sitzungen und alte Zählfenster entfernen."""
    with ctx.session() as session:
        jobs = _delete(
            session,
            "DELETE FROM job WHERE status IN ('succeeded','failed') "
            "AND finished_at < now() - make_interval(days => :days)",
            {"days": FINISHED_JOB_RETENTION_DAYS},
        )
        sessions = _delete(session, "DELETE FROM staff_session WHERE expires_at < now() - interval '30 days'")
        counters = _delete(
            session, "DELETE FROM rate_limit_counter WHERE window_start < now() - interval '1 day'"
        )
        session.commit()
    return {"jobs_deleted": jobs, "sessions_deleted": sessions, "rate_limit_rows_deleted": counters}


periodic("retention_cleanup", kind="retention_cleanup", every=timedelta(days=1))
periodic("housekeeping", kind="housekeeping", every=timedelta(hours=1))
