"""Hintergrundjob des Moduls V (Spez. 7, V 3.7).

`dossier_generate`: PDFs und DXF einer Fassung aus ihrem Snapshot setzen und im Objektspeicher ablegen. Der
Job ist idempotent: Eine fertige Fassung wird übersprungen, Dateien werden unter festen Schlüsseln
überschrieben. Scheitert der letzte Versuch, steht die Fassung auf `failed` (Log `dossier_failed`, Alarm in
BETRIEB); das Büro kann sie neu erzeugen lassen.
"""

import hashlib
import uuid
from typing import Any

from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import JobContext, job
from app.platform.jobs.registry import get_job_spec
from app.platform.logging import get_logger
from app.submission import dossier
from app.submission.models import Submission

log = get_logger("submission_jobs")
KIND = "dossier_generate"


def storage_key(row: Submission, name: str) -> str:
    return f"dossiers/{row.project_id}/{row.id}/{name}"


@job(KIND, max_attempts=3, timeout_seconds=300)
def dossier_generate(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    submission_id = uuid.UUID(payload["submission_id"])
    with ctx.session() as session:
        row = session.get(Submission, submission_id)
        if row is None:
            return {"skipped": "missing"}
        if row.dossier_status == "ready":
            return {"skipped": "ready"}
        try:
            files = dossier.build(row.snapshot)
            stored = []
            for item in files:
                key = storage_key(row, item.name)
                storage.put_bytes(key, item.data, item.content_type)
                stored.append(
                    {
                        "name": item.name,
                        "kind": item.kind,
                        "locale": item.locale,
                        "variant": item.variant,
                        "content_type": item.content_type,
                        "size_bytes": len(item.data),
                        "sha256": hashlib.sha256(item.data).hexdigest(),
                        "storage_key": key,
                    }
                )
        except Exception as exc:
            if ctx.attempt >= get_job_spec(KIND).max_attempts:
                session.rollback()
                failed = session.get(Submission, submission_id)
                if failed is not None:
                    failed.dossier_status = "failed"
                    failed.dossier_error = f"{type(exc).__name__}: {exc}"[:500]
                    failed.updated_at = utcnow()
                    session.commit()
                log.error("dossier_failed", submission_id=str(submission_id), error=type(exc).__name__)
            raise
        row.dossier_files = stored
        row.dossier_status = "ready"
        row.dossier_error = None
        row.updated_at = utcnow()
        session.commit()
        return {"files": len(stored), "bytes": sum(f["size_bytes"] for f in stored)}
