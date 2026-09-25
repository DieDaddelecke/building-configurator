"""Endpunkte des Moduls A (Plan 3.6; docs/PLAN_A_ANFRAGE.md 4.3), erweitert durch V
(docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.3).

Kunde: Kontaktformular und Codebestätigung hinter dem Feature-Flag `inquiry`, Export und Löschung ohne
Flag (Betroffenenrechte gelten unabhängig von der Freischaltung). Büro: Anfragenliste und -Detail für
`architect`, `rules_admin`, `ops` – dieselben Rollen, die auch Regeln und Baurahmen lesen (Plan 4.2).
Den Vorgang (Status, Fassungen, Nachrichten, Zurückziehen) und das Kontaktformular erreicht der Kunde mit
`inquiry` **oder** `submission`, weil auch Vorgänge aus A Nachrichten bekommen und V das Kontaktformular
benutzt (V 3.11). Der Zugangslink ist öffentlich.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inquiry import access, service
from app.inquiry.schemas import (
    AccessRedeemIn,
    AccessRedeemOut,
    AccessRequestIn,
    AccessRequestOut,
    ConfirmIn,
    ConfirmOut,
    ContactIn,
    ContactOut,
    ExportOut,
    InquiryDetailOut,
    InquiryListItem,
    InquiryPatchIn,
    MessageIn,
    MyInquiryOut,
)
from app.platform import flags, projects, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    public,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.i18n import request_locale
from app.platform.problems import Problem

router = APIRouter(tags=["inquiry"])
SUBMISSION_FLAG = "submission"


def require_inquiry_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


def require_case_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not (flags.is_enabled(db, service.FEATURE_FLAG, auth) or flags.is_enabled(db, SUBMISSION_FLAG, auth)):
        raise Problem(403, "feature_disabled")


Feature = Depends(require_inquiry_feature)
CaseFeature = Depends(require_case_feature)
Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))


@router.post(
    "/projects/{project_id}/inquiry/contact",
    response_model=ContactOut,
    status_code=202,
    dependencies=[CaseFeature],
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


@router.get("/projects/{project_id}/inquiry", response_model=MyInquiryOut, dependencies=[CaseFeature])
def get_my_inquiry(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> MyInquiryOut:
    """Eigener Vorgang mit Fassungen und Nachrichten; `exists = false` ohne Vorgang."""
    return service.my_inquiry(db, project_id)


@router.post(
    "/projects/{project_id}/inquiry/messages",
    response_model=MyInquiryOut,
    status_code=201,
    dependencies=[CaseFeature],
)
def post_customer_message(
    request: Request,
    body: MessageIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> MyInquiryOut:
    rate_limit.check(request, "inquiry_message", get_settings().message_limit_per_hour_ip, 3600)
    return service.customer_message(db, project_id, body.body, request_locale(request))


@router.post(
    "/projects/{project_id}/inquiry/withdraw", response_model=MyInquiryOut, dependencies=[CaseFeature]
)
def withdraw_inquiry(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> MyInquiryOut:
    """Vorgang zurückziehen (V 3.8); es wird nichts gelöscht."""
    return service.withdraw(db, project_id, request_locale(request))


@router.post("/access/redeem", response_model=AccessRedeemOut, dependencies=[Depends(public)])
def redeem_access_link(
    request: Request, response: Response, body: AccessRedeemIn, db: Session = Depends(get_db)
) -> AccessRedeemOut:
    """Zugangslink aus einer Kundenmail einlösen; setzt ein neues Projekt-Cookie (V 3.9)."""
    rate_limit.check(request, "access_redeem", get_settings().access_redeem_limit_per_hour_ip, 3600)
    return AccessRedeemOut(project_id=access.redeem(db, body.token, response))


@router.post(
    "/access/request", response_model=AccessRequestOut, status_code=202, dependencies=[Depends(public)]
)
def request_access_link(
    request: Request, body: AccessRequestIn, db: Session = Depends(get_db)
) -> AccessRequestOut:
    """Neuen Zugangslink per Mail anfordern; die Antwort verrät nicht, ob die Adresse bekannt ist."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    rate_limit.check(request, "access_request", settings.access_request_limit_per_hour_ip, 3600)
    rate_limit.check_value("access_request_email", email, settings.access_request_limit_per_hour_email, 3600)
    access.request_links(db, email)
    return AccessRequestOut()


@router.get("/projects/{project_id}/export", response_model=ExportOut)
def export_project(
    project_id: uuid.UUID = Depends(require_project_access), db: Session = Depends(get_db)
) -> ExportOut:
    """Betroffenenrechte (Spez. 10.2), unabhängig vom Feature-Flag."""
    return service.export(db, project_id)


projects.register_delete_guard(service.guard_delete)
"""Die Löschung liegt seit AN1 im Kern (`app/platform/projects.py`); Modul A hängt nur seine Sperre ein."""


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


@router.get("/admin/inquiries", response_model=list[InquiryListItem])
def list_inquiries(
    status: Annotated[
        Literal["neu", "in_bearbeitung", "rueckfrage", "beantwortet", "geschlossen", "zurueckgezogen"] | None,
        Query(),
    ] = None,
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


@router.post(
    "/admin/projects/{project_id}/inquiry/messages", response_model=InquiryDetailOut, status_code=201
)
def post_office_message(
    project_id: uuid.UUID,
    body: MessageIn,
    staff: StaffPrincipal = Reader,
    db: Session = Depends(get_db),
) -> InquiryDetailOut:
    """Nachricht an den Kunden; ein offener Vorgang wechselt auf `rueckfrage` (V 3.8)."""
    return service.office_message(db, project_id, body.body, staff.actor_id)
