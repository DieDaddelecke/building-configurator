"""Anonymes Kundenprojekt mit Zugangscookie (Spez. 6.2, Plan 3.2).

Vor der Kontaktaufnahme gibt es keine personenbezogenen Daten. Nach 90 Tagen ohne Aktivität
löscht `retention_cleanup` das Projekt.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import rate_limit
from app.platform.auth.context import public, require_project_access
from app.platform.auth.tokens import PROJECT_COOKIE, hash_token, new_token
from app.platform.db import get_db
from app.platform.models import Project
from app.platform.problems import Problem

router = APIRouter(tags=["projects"])


class ProjectOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime


@router.post("/projects", response_model=ProjectOut, status_code=201, dependencies=[Depends(public)])
def create_project(request: Request, response: Response, db: Session = Depends(get_db)) -> ProjectOut:
    settings = get_settings()
    rate_limit.check(request, "project_create", settings.project_create_limit_per_hour, 3600)
    token = new_token()
    project = Project(access_token_hash=hash_token(token), created_by="customer")
    db.add(project)
    db.commit()
    db.refresh(project)
    response.set_cookie(
        PROJECT_COOKIE,
        token,
        max_age=settings.project_retention_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return ProjectOut(id=project.id, status=project.status, created_at=project.created_at)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    return ProjectOut(id=project.id, status=project.status, created_at=project.created_at)
