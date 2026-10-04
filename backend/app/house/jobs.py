"""Hintergrundjob des Hausmodells (docs/PLAN_HAUSMODELL.md 3.6).

`house_ifc_import`: eine hochgeladene IFC-Datei im Kindprozess lesen (E-HM-19) und daraus Entwurf und
Importbericht bilden; einmal je Templateversion. Warteschlange `long`, weil eine große Datei Minuten braucht.
"""

import uuid
from typing import Any

from app.config import get_settings
from app.house import service
from app.platform.jobs import LONG, JobContext, job
from app.platform.jobs.registry import get_job_spec


@job("house_ifc_import", queue=LONG, max_attempts=3, timeout_seconds=600)
def house_ifc_import(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    version_id = uuid.UUID(payload["version_id"])
    try:
        return service.run_import(ctx.session, get_settings(), version_id)
    except Exception as exc:
        if ctx.attempt >= get_job_spec("house_ifc_import").max_attempts:
            service.mark_import_failed(ctx.session, version_id, f"{type(exc).__name__}: {exc}")
        raise
