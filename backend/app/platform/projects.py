"""Projekt: anonym mit Zugangscookie (Kunde, Spez. 6.2) oder in einer Organisation (AN1, AN6).

Vor der Kontaktaufnahme gibt es keine personenbezogenen Daten. Ein Kundenprojekt ohne Aktivität löscht
`retention_cleanup` nach 90 Tagen; Projekte einer Organisation bleiben (UP06). Kosten auslösende
Analyse-Funktionen verlangen ein Projekt der eigenen Organisation (`require_owned_project`); das Cookie
eines Kundenprojekts reicht dafür nicht.
"""

import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import audit, rate_limit, storage
from app.platform.auth.context import (
    Principal,
    RequestAuth,
    StaffPrincipal,
    get_auth,
    public,
    require_organisation,
    require_owned_project,
    require_project_access,
)
from app.platform.auth.tokens import PROJECT_COOKIE, hash_token, new_token
from app.platform.db import get_db, utcnow
from app.platform.logging import get_logger
from app.platform.models import Project
from app.platform.problems import Problem

router = APIRouter(tags=["projects"])
log = get_logger("projects")

DeleteGuard = Callable[[Session, uuid.UUID], None]
_delete_guards: list[DeleteGuard] = []

StorageKeys = Callable[[Session, uuid.UUID], list[str]]
_storage_keys: list[StorageKeys] = []


def register_storage_keys(provider: StorageKeys) -> None:
    """Ein Fachmodul nennt die Dateien eines Projekts im Objektspeicher (Steckbrief, Bericht), damit das
    Löschen sie mitnimmt. Die Zeilen löscht die Datenbank über `ON DELETE CASCADE` (AN5, 7.1 Nr. 13)."""
    if provider not in _storage_keys:
        _storage_keys.append(provider)


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


NOTE_PREVIEW = 200
"""Länge der Notiz in der Liste; ganz steht sie nur am Projekt."""


class ArchitectProjectOut(BaseModel):
    """Projekt am Konto des Architekten (AN1), mit Name, Notiz und Archiv (AN5, PLAN_AN5_AUSGABE 3.1)."""

    id: uuid.UUID
    status: str
    created_at: datetime
    last_activity_at: datetime
    name: str | None = None
    note: str | None = None
    archived_at: datetime | None = None
    address_label: str | None
    site_origin: str | None
    area_m2: float | None


class ProjectUpdateIn(BaseModel):
    """Nur die genannten Felder ändern sich; ein leerer Name oder eine leere Notiz löscht sie."""

    name: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


@router.post("/projects", response_model=ProjectOut, status_code=201, dependencies=[Depends(public)])
def create_project(
    request: Request,
    response: Response,
    auth: RequestAuth = Depends(get_auth),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Neues Projekt. Ein Architekt oder API-Schlüssel legt es in seiner Organisation an; der Architekt wird
    Eigentümer. Beide bekommen **kein** Cookie – sonst verdrängte jedes neue Projekt das vorige (AN1, UP05,
    AN6). Ohne Anmeldung entsteht ein Kundenprojekt mit Cookie; die Analyse legt Projekte nur angemeldet
    an."""
    settings = get_settings()
    rate_limit.check(request, "project_create", settings.project_create_limit_per_hour, 3600)
    principal = auth.principal
    token = new_token()
    project = Project(
        access_token_hash=hash_token(token),
        created_by=principal.actor_id if principal else "customer",
        owner_staff_user_id=principal.user_id if isinstance(principal, StaffPrincipal) else None,
        organisation_id=principal.organisation_id if principal else None,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    if principal is None:
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


def _architect_out(
    project: Project, summary: ProjectSummary, *, full_note: bool = False
) -> ArchitectProjectOut:
    note = project.note
    if note is not None and not full_note and len(note) > NOTE_PREVIEW:
        note = note[: NOTE_PREVIEW - 1].rstrip() + "…"
    return ArchitectProjectOut(
        id=project.id,
        status=project.status,
        created_at=project.created_at,
        last_activity_at=project.last_activity_at,
        name=project.name,
        note=note,
        archived_at=project.archived_at,
        address_label=summary.address_label,
        site_origin=summary.site_origin,
        area_m2=summary.area_m2,
    )


def _summaries(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, ProjectSummary]:
    summaries: dict[uuid.UUID, ProjectSummary] = {}
    for provider in _summary_providers:
        summaries.update(provider(db, ids))
    return summaries


@router.get("/projects", response_model=list[ArchitectProjectOut])
def list_own_projects(
    archived: bool = Query(default=False),
    principal: Principal = Depends(require_organisation),
    db: Session = Depends(get_db),
) -> list[ArchitectProjectOut]:
    """Projekte der eigenen Organisation, neueste zuerst (AN1, AN6); `archived=true` zeigt das Archiv (AN5).
    Alle Mitglieder einer Organisation sehen dieselben Projekte (E-AN1-4)."""
    in_archive = Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None)
    projects = list(
        db.execute(
            select(Project)
            .where(Project.organisation_id == principal.organisation_id, in_archive)
            .order_by(Project.last_activity_at.desc())
            .limit(500)
        ).scalars()
    )
    summaries = _summaries(db, [p.id for p in projects])
    return [_architect_out(p, summaries.get(p.id, ProjectSummary())) for p in projects]


@router.get("/projects/{project_id}/details", response_model=ArchitectProjectOut)
def get_own_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ArchitectProjectOut:
    """Name, ganze Notiz und Archiv eines Projekts der Organisation (AN5)."""
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    summary = _summaries(db, [project_id]).get(project_id, ProjectSummary())
    return _architect_out(project, summary, full_note=True)


@router.patch("/projects/{project_id}", response_model=ArchitectProjectOut)
def update_own_project(
    project_id: uuid.UUID,
    body: ProjectUpdateIn,
    principal: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ArchitectProjectOut:
    """Name, Notiz und Archiv ändern (AN5, E-AN5-7: archivieren blendet nur aus). Das Audit nennt den Namen
    und ob sich die Notiz geändert hat, nicht ihren Inhalt."""
    project = db.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise Problem(404, "not_found")
    before = {"name": project.name, "archived": project.archived_at is not None}
    changes = body.model_fields_set
    if "name" in changes:
        project.name = (body.name or "").strip() or None
    note_changed = False
    if "note" in changes:
        note = (body.note or "").strip() or None
        note_changed = note != project.note
        project.note = note
    if "archived" in changes and body.archived is not None:
        if body.archived and project.archived_at is None:
            project.archived_at = utcnow()
        elif not body.archived:
            project.archived_at = None
    after = {"name": project.name, "archived": project.archived_at is not None}
    if before != after or note_changed:
        audit.record(
            db,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="project.update",
            entity_type="project",
            entity_id=str(project_id),
            before=before,
            after={**after, "note_changed": note_changed},
        )
    db.commit()
    db.refresh(project)
    summary = _summaries(db, [project_id]).get(project_id, ProjectSummary())
    return _architect_out(project, summary, full_note=True)


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
    keys = [key for provider in _storage_keys for key in provider(db, project_id)]
    principal = auth.principal
    audit.record(
        db,
        actor_type=principal.actor_type if principal else "customer",
        actor_id=principal.actor_id if principal else f"project:{project_id}",
        action="project.delete",
        entity_type="project",
        entity_id=str(project_id),
    )
    db.delete(project)
    db.commit()
    for key in keys:
        # Nach dem Commit: Eine verwaiste Datei ist harmlos, eine fehlende Datei zu einer Zeile nicht
        try:
            storage.delete(key)
        except Exception:
            log.warning("project_file_delete_failed", project_id=str(project_id), key=key)
    return Response(status_code=204)
