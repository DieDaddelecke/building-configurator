"""Endpunkte des Moduls A (Plan 3.6; docs/PLAN_A_ANFRAGE.md 4.3).

Kunde: Kontaktformular und Codebestätigung hinter dem Feature-Flag `inquiry`, Export und Löschung ohne
Flag (Betroffenenrechte gelten unabhängig von der Freischaltung). Büro: Anfragenliste und -Detail für
`architect`, `rules_admin`, `ops` – dieselben Rollen, die auch Regeln und Baurahmen lesen (Plan 4.2).
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inquiry import service
from app.inquiry.schemas import (
    ConfirmIn,
    ConfirmOut,
    ContactIn,
    ContactOut,
    ExportOut,
    InquiryDetailOut,
    InquiryListItem,
    InquiryPatchIn,
    MyInquiryOut,
)
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.i18n import request_locale
from app.platform.problems import Problem

router = APIRouter(tags=["inquiry"])


def require_inquiry_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


Feature = Depends(require_inquiry_feature)
Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))


@router.post(
    "/projects/{project_id}/inquiry/contact",
    response_model=ContactOut,
    status_code=202,
    dependencies=[Feature],
)
def submit_contact(
    request: Request,
    body: ContactIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ContactOut:
    rate_limit.check(request, "inquiry_contact", get_settings().inquiry_contact_limit_per_hour_ip, 3600)
    return service.submit_contact(db, project_id, body, request_locale(request))


@router.post(
    "/projects/{project_id}/inquiry/confirm",
    response_model=ConfirmOut,
    status_code=201,
    dependencies=[Feature],
)
def confirm_contact(
    request: Request,
    body: ConfirmIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ConfirmOut:
    rate_limit.check(request, "inquiry_confirm", get_settings().inquiry_confirm_limit_per_hour_ip, 3600)
    return service.confirm_contact(db, project_id, body, request_locale(request))


@router.get("/projects/{project_id}/inquiry", response_model=MyInquiryOut, dependencies=[Feature])
def get_my_inquiry(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> MyInquiryOut:
    return service.my_inquiry(db, project_id)


@router.get("/projects/{project_id}/export", response_model=ExportOut)
def export_project(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> ExportOut:
    """Betroffenenrechte (Spez. 10.2), unabhängig vom Feature-Flag."""
    return service.export(db, project_id)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> Response:
    service.delete_project(db, project_id, actor=f"project:{project_id}")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


@router.get("/admin/inquiries", response_model=list[InquiryListItem])
def list_inquiries(
    status: Annotated[Literal["neu", "in_bearbeitung", "beantwortet", "geschlossen"] | None, Query()] = None,
    staff: StaffPrincipal = Reader,
    db: Session = Depends(get_db),
) -> list[InquiryListItem]:
    return service.list_inquiries(db, status)


@router.get("/admin/projects/{project_id}/inquiry", response_model=InquiryDetailOut)
def get_inquiry_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> InquiryDetailOut:
    return service.inquiry_detail(db, project_id)


@router.patch("/admin/projects/{project_id}/inquiry", response_model=InquiryDetailOut)
def patch_inquiry_status(
    project_id: uuid.UUID,
    body: InquiryPatchIn,
    staff: StaffPrincipal = Reader,
    db: Session = Depends(get_db),
) -> InquiryDetailOut:
    return service.set_status(db, project_id, body.status, staff.actor_id)
