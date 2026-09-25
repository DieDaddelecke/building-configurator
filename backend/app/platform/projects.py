"""Projekt: anonym mit Zugangscookie (Kunde, Spez. 6.2) oder am Konto eines Architekten (AN1).

Vor der Kontaktaufnahme gibt es keine personenbezogenen Daten. Ein Kundenprojekt ohne Aktivität löscht
`retention_cleanup` nach 90 Tagen; Projekte mit Eigentümer bleiben (UP06).
"""

import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import audit, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    get_auth,
    public,
    require_project_access,
    require_roles,
)
from app.platform.auth.tokens import PROJECT_COOKIE, hash_token, new_token
from app.platform.db import get_db
from app.platform.models import Project
from app.platform.problems import Problem

router = APIRouter(tags=["projects"])

DeleteGuard = Callable[[Session, uuid.UUID], None]
_delete_guards: list[DeleteGuard] = []


def register_delete_guard(guard: DeleteGuard) -> None:
    """Ein Fachmodul meldet einen Grund an, der einer Löschung entgegensteht (Modul A: offene Anfrage).

    So bleibt die Löschung im Kern und trotzdem vollständig, ohne dass der Kern Anfragen kennt (AN0).
    """
    if guard not in _delete_guards:
        _delete_guards.append(guard)


class ProjectSummary(BaseModel):
    """Was ein Fachmodul zur Projektliste beisteuert (G1: Bezeichnung, Herkunft und Fläche)."""

    address_label: str | None = None
    site_origin: str | None = None
    area_m2: float | None = None


SummaryProvider = Callable[[Session, list[uuid.UUID]], dict[uuid.UUID, ProjectSummary]]
_summary_providers: list[SummaryProvider] = []


def register_summary_provider(provider: SummaryProvider) -> None:
    """Ein Fachmodul füllt die Projektliste, ohne dass der Kern seine Tabellen kennt (G1 meldet sich an)."""
    if provider not in _summary_providers:
        _summary_providers.append(provider)


class ProjectOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime


class ArchitectProjectOut(BaseModel):
    """Projekt am Konto des Architekten (AN1). Benennung, Notiz und Archiv folgen mit AN5."""

    id: uuid.UUID
    status: str
    created_at: datetime
    last_activity_at: datetime
    address_label: str | None
    site_origin: str | None
    area_m2: float | None


@router.post("/projects", response_model=ProjectOut, status_code=201, dependencies=[Depends(public)])
def create_project(
    request: Request,
    response: Response,
    auth: RequestAuth = Depends(get_auth),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Neues Projekt. Ein angemeldeter Architekt wird Eigentümer und bekommt **kein** Cookie – sonst
    verdrängte jedes neue Projekt das vorige (AN1, UP05)."""
    settings = get_settings()
    rate_limit.check(request, "project_create", settings.project_create_limit_per_hour, 3600)
    staff = auth.staff if auth.staff and Role.architect in auth.staff.roles else None
    token = new_token()
    project = Project(
        access_token_hash=hash_token(token),
        created_by=staff.actor_id if staff else "customer",
        owner_staff_user_id=staff.user_id if staff else None,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    if staff is None:
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


@router.get("/projects", response_model=list[ArchitectProjectOut])
def list_own_projects(
    staff: object = Depends(require_roles(Role.architect)), db: Session = Depends(get_db)
) -> list[ArchitectProjectOut]:
    """Projekte mit Eigentümer, neueste zuerst (AN1). Alle Architekten des Büros sehen dieselben
    Projekte; nach Person und Organisation trennt erst AN6 (D15, E-AN1-4)."""
    projects = list(
        db.execute(
            select(Project)
            .where(Project.owner_staff_user_id.is_not(None))
            .order_by(Project.last_activity_at.desc())
            .limit(500)
        ).scalars()
    )
    summaries: dict[uuid.UUID, ProjectSummary] = {}
    ids = [p.id for p in projects]
    for provider in _summary_providers:
        summaries.update(provider(db, ids))
    return [
        ArchitectProjectOut(
            id=p.id,
            status=p.status,
            created_at=p.created_at,
            last_activity_at=p.last_activity_at,
            address_label=summaries.get(p.id, ProjectSummary()).address_label,
            site_origin=summaries.get(p.id, ProjectSummary()).site_origin,
            area_m2=summaries.get(p.id, ProjectSummary()).area_m2,
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    return ProjectOut(id=project.id, status=project.status, created_at=project.created_at)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID = Depends(require_project_access),
    auth: RequestAuth = Depends(get_auth),
    db: Session = Depends(get_db),
) -> Response:
    """Projekt mit allem daran löschen (Spez. 10.2), unabhängig vom Feature-Flag.

    Angemeldete Module können widersprechen: Modul A lässt nach einer Anfrage nur das Büro löschen.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    for guard in _delete_guards:
        guard(db, project_id)
    actor = auth.staff.actor_id if auth.staff else f"project:{project_id}"
    audit.record(
        db,
        actor_type="staff" if auth.staff else "customer",
        actor_id=actor,
        action="project.delete",
        entity_type="project",
        entity_id=str(project_id),
    )
    db.delete(project)
    db.commit()
    return Response(status_code=204)
