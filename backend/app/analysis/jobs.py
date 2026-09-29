"""Hintergrundjob des Moduls AN5 (docs/PLAN_AN5_AUSGABE.md 3.6, E-AN5-10).

`analysis_report`: Bericht als PDF im Worker (WeasyPrint), wie der Steckbrief (`envelope/jobs.py`): Der Job
setzt den Bericht immer zum **aktuellen** Stand und legt ihn unter dessen Prüfsumme ab. Hat sich seit dem
Auftrag etwas geändert, entsteht kein Bericht zu einem überholten Stand.
"""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.analysis import report, service
from app.analysis.domain import ENGINE_VERSION
from app.analysis.models import AnalysisReport
from app.platform import storage
from app.platform.db import utcnow
from app.platform.i18n import DEFAULT_LOCALE, SUPPORTED, Locale
from app.platform.jobs import JobContext, job
from app.platform.logging import get_logger

log = get_logger("analysis_jobs")


@job(service.REPORT_JOB, max_attempts=2, timeout_seconds=180)
def analysis_report(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = uuid.UUID(payload["project_id"])
    requested = str(payload["input_hash"])
    wanted = payload.get("locale")
    locale: Locale = wanted if wanted in SUPPORTED else DEFAULT_LOCALE
    with ctx.session() as session:
        if service.stored_report(session, project_id, requested, locale) is not None:
            return {"skipped": "already_generated", "input_hash": requested}
        data = service.report_data(session, project_id, with_logo=True)
        current = report.report_hash(data)
        if current != requested:
            log.info(
                "analysis_report_input_changed",
                project_id=str(project_id),
                requested=requested[7:19],
                current=current[7:19],
            )
            if service.stored_report(session, project_id, current, locale) is not None:
                return {"skipped": "already_generated", "input_hash": current}
        generated_at = utcnow()
        pdf = report.render_pdf(data, locale=locale, generated_at=generated_at, report=current)
        key = service.report_key(project_id, current, locale)
        storage.put_bytes(key, pdf, "application/pdf")
        session.add(
            AnalysisReport(
                project_id=project_id,
                input_hash=current,
                locale=locale,
                engine_version=ENGINE_VERSION,
                storage_key=key,
                size_bytes=len(pdf),
                generated_at=generated_at,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            # Ein zweiter Auftrag hat denselben Stand gleichzeitig abgelegt; die Datei ist dieselbe
            session.rollback()
            return {"skipped": "already_generated", "input_hash": current}
        return {"input_hash": current, "matched_request": current == requested, "size_bytes": len(pdf)}
