"""Betriebsfunktionen für die Rolle `ops`: Zustand und Probeversand (Proof of Concept, Plan 6.4)."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import storage
from app.platform.auth.context import Role, StaffPrincipal, require_roles
from app.platform.db import get_db
from app.platform.i18n import request_locale
from app.platform.jobs import queue
from app.platform.logging import get_logger
from app.platform.mail import queue_mail

router = APIRouter(tags=["ops"])
log = get_logger(__name__)


class OpsStatus(BaseModel):
    env: str
    release: str
    jobs_by_status: dict[str, int]
    jobs_failed_last_24h: int
    oldest_waiting_seconds: float | None
    storage_ok: bool


@router.get("/admin/ops/status", response_model=OpsStatus)
def ops_status(
    staff: StaffPrincipal = Depends(require_roles(Role.ops)), db: Session = Depends(get_db)
) -> OpsStatus:
    settings = get_settings()
    counts = {
        row.status: row.n for row in db.execute(text("SELECT status, count(*) AS n FROM job GROUP BY status"))
    }
    failed = db.execute(
        text("SELECT count(*) FROM job WHERE status = 'failed' AND finished_at > now() - interval '24 hours'")
    ).scalar_one()
    try:
        storage_ok = storage.roundtrip_check(f"ops-check/{uuid.uuid4()}")
    except Exception as exc:
        log.warning("storage_check_failed", error_type=type(exc).__name__)
        storage_ok = False
    return OpsStatus(
        env=settings.env,
        release=settings.release,
        jobs_by_status=counts,
        jobs_failed_last_24h=failed,
        oldest_waiting_seconds=queue.oldest_waiting_seconds(db.connection()),
        storage_ok=storage_ok,
    )


class JobCreated(BaseModel):
    job_id: uuid.UUID


@router.post("/admin/ops/test-mail", response_model=JobCreated, status_code=202)
def send_test_mail(
    request: Request,
    staff: StaffPrincipal = Depends(require_roles(Role.ops)),
    db: Session = Depends(get_db),
) -> JobCreated:
    """Testmail an die eigene Adresse der angemeldeten Person."""
    job_id = queue_mail(
        db,
        to=staff.email,
        template="platform_test",
        locale=request_locale(request),
        params={"env": get_settings().env},
        created_by=staff.actor_id,
    )
    db.commit()
    return JobCreated(job_id=job_id)
