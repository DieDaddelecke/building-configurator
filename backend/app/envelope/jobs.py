"""Hintergrundjobs des Moduls G3 (Spez. 7, Plan 3.5).

`envelope_sheet`: Steckbrief als PDF im Worker (WeasyPrint). Der Job setzt den Steckbrief immer zum
**aktuellen** Stand und legt ihn unter dessen Prüfsumme ab. Hat sich seit dem Auftrag etwas geändert
(Gelände eingetroffen, Kante korrigiert, neue Regeln), entsteht also kein PDF zu einem überholten Stand,
und der nächste Abruf findet den neuen sofort. Ein Job, der einen überholten Stand nur überspränge, käme
nie zum Ziel, solange eine Eingabe noch eintrifft.
"""

import uuid
from typing import Any

from app.envelope import service, sheet
from app.envelope.models import EnvelopeSheet
from app.platform import storage
from app.platform.i18n import DEFAULT_LOCALE, SUPPORTED, Locale
from app.platform.jobs import JobContext, job
from app.platform.logging import get_logger

log = get_logger("envelope_jobs")


@job("envelope_sheet", max_attempts=2, timeout_seconds=120)
def envelope_sheet(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = uuid.UUID(payload["project_id"])
    requested = str(payload["input_hash"])
    wanted = payload.get("locale")
    locale: Locale = wanted if wanted in SUPPORTED else DEFAULT_LOCALE
    with ctx.session() as session:
        if service.stored_sheet(session, project_id, requested) is not None:
            return {"skipped": "already_generated", "input_hash": requested}
        envelope, data = service.build_envelope(session, project_id)
        current = envelope.input_hash
        if current != requested:
            log.info(
                "envelope_sheet_input_changed",
                project_id=str(project_id),
                requested=requested[7:19],
                current=current[7:19],
            )
            if service.stored_sheet(session, project_id, current) is not None:
                return {"skipped": "already_generated", "input_hash": current}
        pdf = sheet.render_pdf(envelope, reference=", ".join(data.site.parcels), locale=locale)
        key = service.sheet_key(project_id, current)
        storage.put_bytes(key, pdf, "application/pdf")
        session.add(
            EnvelopeSheet(
                project_id=project_id,
                input_hash=current,
                engine_version=envelope.engine_version,
                storage_key=key,
                size_bytes=len(pdf),
            )
        )
        session.commit()
        return {"input_hash": current, "matched_request": current == requested, "size_bytes": len(pdf)}
