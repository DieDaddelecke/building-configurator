"""Endpunkte des Moduls G3 (Spez. 6.3; Plan 3.5).

Kunden sehen den Baurahmen ihres Grundstücks hinter dem Feature-Flag `envelope_simulation`; er setzt die
Flags von G1 und G2 nicht voraus, braucht aber deren Daten. Das Büro liest denselben Baurahmen beim Prüfen
einer Anfrage (Modul A). Keine Büroaktion ist Voraussetzung für die Simulation (D11).
"""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.envelope import service
from app.envelope.schemas import EnvelopeOut, SheetOut
from app.platform import flags, projects, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.problems import Problem

router = APIRouter(tags=["envelope"])


def require_envelope_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


Feature = Depends(require_envelope_feature)
Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))


@router.get("/projects/{project_id}/envelope", response_model=EnvelopeOut, dependencies=[Feature])
def get_envelope(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> EnvelopeOut:
    """Bebaubare Fläche, Grenzwerte, Abstände und Hinweise – als Simulation (Plan 3.5, D11)."""
    rate_limit.check(request, "envelope_read", get_settings().envelope_limit_per_minute, 60)
    return service.project_envelope(db, project_id)


@router.post("/projects/{project_id}/envelope/sheet", response_model=SheetOut, dependencies=[Feature])
def create_sheet(
    request: Request,
    response: Response,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> SheetOut:
    """Steckbrief als PDF anfordern. Liegt er für diesen Eingabestand vor, kommt er sofort (`ready`)."""
    rate_limit.check(request, "envelope_sheet", get_settings().envelope_sheet_limit_per_hour, 3600)
    result = service.request_sheet(db, project_id)
    if result.status == "pending":
        response.status_code = 202
    return result


@router.get("/projects/{project_id}/envelope/sheet", dependencies=[Feature])
def download_sheet(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> Response:
    """Fertiger Steckbrief zum aktuellen Eingabestand; sonst 409 mit dem Auftrag als Hinweis."""
    content, input_hash = service.sheet_bytes(db, project_id)
    name = f"emprise-baurahmen-{input_hash.removeprefix('sha256:')[:8]}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/admin/projects/{project_id}/envelope", response_model=EnvelopeOut)
def get_envelope_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> EnvelopeOut:
    """Baurahmen für die Prüfung einer Anfrage (Modul A); ohne Feature-Flag, nur mit Rolle."""
    return service.project_envelope(db, project_id)


@router.post("/admin/projects/{project_id}/envelope/sheet", response_model=SheetOut)
def create_sheet_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> SheetOut:
    """Steckbrief zur Anfrage anfordern (Modul A, docs/PLAN_A_ANFRAGE.md 4.3): wie die Kundenroute, aber
    ohne Feature-Flag, nur mit Rolle."""
    return service.request_sheet(db, project_id, actor=staff.actor_id)


@router.get("/admin/projects/{project_id}/envelope/sheet")
def download_sheet_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> Response:
    content, input_hash = service.sheet_bytes(db, project_id)
    name = f"emprise-baurahmen-{input_hash.removeprefix('sha256:')[:8]}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


projects.register_storage_keys(service.sheet_storage_keys)
