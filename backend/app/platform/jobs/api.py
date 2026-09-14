import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.platform.auth.context import RequestAuth, Role, checked_in_handler
from app.platform.db import get_db
from app.platform.models import Job
from app.platform.problems import Problem

router = APIRouter(tags=["jobs"])


class JobStatus(BaseModel):
    id: uuid.UUID
    kind: str
    status: Literal["queued", "running", "succeeded", "failed"]
    attempts: int
    created_at: datetime
    finished_at: datetime | None


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(
    job_id: uuid.UUID, auth: RequestAuth = Depends(checked_in_handler), db: Session = Depends(get_db)
) -> JobStatus:
    """Status eines Hintergrundjobs (Spez. 6.1). Kunden sehen nur Jobs ihres Projekts, `ops` alle."""
    job = db.get(Job, job_id)
    is_ops = auth.staff is not None and Role.ops in auth.staff.roles
    if job is None or not (is_ops or (job.project_id is not None and job.project_id == auth.project_id)):
        raise Problem(404, "not_found")
    return JobStatus(
        id=job.id,
        kind=job.kind,
        status=job.status,
        attempts=job.attempts,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )
