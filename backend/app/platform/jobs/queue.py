"""Anlegen, Abholen und Abschließen von Jobs mit `SELECT … FOR UPDATE SKIP LOCKED`.

Abholen und Abschließen laufen in kurzen eigenen Transaktionen; die Ausführung dazwischen hält
keine Sperre. Bleibt ein Job länger als sein Zeitlimit auf `running` (Worker abgestürzt), stellt
`requeue_stale` ihn zurück.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.platform.jobs.registry import get_job_spec
from app.platform.models import Job

MAX_BACKOFF_SECONDS = 3600
BASE_BACKOFF_SECONDS = 30
STALE_GRACE_SECONDS = 60


def enqueue(
    session: Session,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    run_after: datetime | None = None,
    idempotency_key: str | None = None,
    project_id: uuid.UUID | None = None,
    created_by: str | None = None,
) -> uuid.UUID:
    """Legt den Job in der Transaktion von `session` an. Er wird erst mit deren Commit sichtbar."""
    spec = get_job_spec(kind)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "queue": spec.queue,
        "kind": kind,
        "payload": payload or {},
        "max_attempts": spec.max_attempts,
        "timeout_seconds": spec.timeout_seconds,
        "idempotency_key": idempotency_key,
        "project_id": project_id,
        "created_by": created_by,
    }
    if run_after is not None:
        values["run_after"] = run_after
    stmt = (
        insert(Job)
        .values(values)
        .on_conflict_do_nothing(
            index_elements=["idempotency_key"], index_where=text("idempotency_key IS NOT NULL")
        )
        .returning(Job.id)
    )
    job_id = session.execute(stmt).scalar_one_or_none()
    if job_id is None:
        job_id = session.execute(select(Job.id).where(Job.idempotency_key == idempotency_key)).scalar_one()
    return job_id


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    timeout_seconds: int
    project_id: uuid.UUID | None


_CLAIM = text(
    """
    UPDATE job SET status = 'running', attempts = attempts + 1, locked_at = now(),
                   locked_by = :worker, started_at = now()
    WHERE id = (
        SELECT id FROM job
        WHERE status = 'queued' AND queue = ANY(:queues) AND run_after <= now()
        ORDER BY run_after, created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, kind, payload, attempts, max_attempts, timeout_seconds, project_id
    """
)


def claim(conn: Connection, worker: str, queues: list[str]) -> ClaimedJob | None:
    row = conn.execute(_CLAIM, {"worker": worker, "queues": queues}).first()
    return ClaimedJob(**row._mapping) if row else None


def complete(conn: Connection, job_id: uuid.UUID, worker: str, result: dict[str, Any] | None) -> None:
    conn.execute(
        text(
            """
            UPDATE job SET status = 'succeeded', finished_at = now(), locked_at = NULL,
                           last_error = NULL, result = CAST(:result AS jsonb)
            WHERE id = :id AND status = 'running' AND locked_by = :worker
            """
        ),
        {"id": job_id, "worker": worker, "result": _json(result)},
    )


def fail(conn: Connection, job: ClaimedJob, worker: str, error: str) -> str:
    """Wiederholung mit exponentiellem Backoff oder endgültig `failed`. Liefert den neuen Status."""
    final = job.attempts >= job.max_attempts
    backoff = min(BASE_BACKOFF_SECONDS * 2 ** (job.attempts - 1), MAX_BACKOFF_SECONDS)
    conn.execute(
        text(
            """
            UPDATE job SET status = :status, locked_at = NULL, last_error = :error,
                           finished_at = CASE WHEN :final THEN now() ELSE NULL END,
                           run_after = CASE WHEN :final THEN run_after
                                            ELSE now() + make_interval(secs => :backoff) END
            WHERE id = :id AND status = 'running' AND locked_by = :worker
            """
        ),
        {
            "status": "failed" if final else "queued",
            "error": error[:2000],
            "final": final,
            "backoff": backoff,
            "id": job.id,
            "worker": worker,
        },
    )
    return "failed" if final else "queued"


def requeue_stale(conn: Connection) -> int:
    rows = conn.execute(
        text(
            """
            UPDATE job SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
                           finished_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END,
                           locked_at = NULL, run_after = now(),
                           last_error = 'worker_lost: not completed within timeout'
            WHERE status = 'running'
              AND locked_at < now() - make_interval(secs => timeout_seconds + :grace)
            RETURNING id
            """
        ),
        {"grace": STALE_GRACE_SECONDS},
    ).all()
    return len(rows)


def oldest_waiting_seconds(conn: Connection, queues: list[str] | None = None) -> float | None:
    """Alter des ältesten fälligen, nicht abgeholten Jobs (Kennzahl und Alarm, Plan 6.8)."""
    query = (
        "SELECT EXTRACT(EPOCH FROM now() - min(run_after)) FROM job "
        "WHERE status = 'queued' AND run_after <= now()"
    )
    params: dict[str, Any] = {}
    if queues:
        query += " AND queue = ANY(:queues)"
        params["queues"] = queues
    value = conn.execute(text(query), params).scalar()
    return float(value) if value is not None else None


def _json(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value) if value is not None else None
