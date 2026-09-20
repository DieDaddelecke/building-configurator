"""Endpunkte des Moduls V (docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.3).

Kunde: Übergabe hinter dem Flag `submission`, PDFs der eigenen Fassungen mit `inquiry` oder `submission`
(wie der Vorgang, V 3.11). Büro: alle Dateien einer Fassung und das Neuerzeugen eines gescheiterten Dossiers
für `architect`, `rules_admin`, `ops` (wie A).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inquiry.api import CaseFeature
from app.inquiry.schemas import InquiryDetailOut
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
from app.submission import service
from app.submission.schemas import SubmitIn, SubmitOut

router = APIRouter(tags=["submission"])
Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))
FileName = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.-]{1,120}$")]


def require_submission_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


def _file(content: bytes, content_type: str, name: str) -> Response:
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/projects/{project_id}/submission",
    response_model=SubmitOut,
    status_code=201,
    dependencies=[Depends(require_submission_feature)],
)
def submit(
    request: Request,
    body: SubmitIn,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> SubmitOut:
    """Vorentwurf übergeben (V 3.2). `409 review_changed`: Die Auswertung hat sich seit dem Anzeigen
    geändert (`changes`, neuer `review_stamp`); `409 deviations_not_acknowledged`: bindende Verstöße ohne
    Bestätigung; `409 submission_incomplete`: Typ, Lage oder Linie fehlen."""
    rate_limit.check(request, "submission", get_settings().submission_limit_per_hour_ip, 3600)
    return service.submit(db, project_id, body, request_locale(request))


@router.get("/projects/{project_id}/submissions/{sequence}/files/{name}", dependencies=[CaseFeature])
def download_own_file(
    sequence: int,
    name: FileName,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> Response:
    """PDF einer eigenen Fassung; DXF-Dateien gibt es nur für das Büro."""
    content, content_type = service.file_bytes(db, project_id, sequence, name, pdf_only=True)
    return _file(content, content_type, name)


@router.get("/admin/projects/{project_id}/submissions/{sequence}/files/{name}")
def download_file_staff(
    project_id: uuid.UUID,
    sequence: int,
    name: FileName,
    staff: StaffPrincipal = Reader,
    db: Session = Depends(get_db),
) -> Response:
    content, content_type = service.file_bytes(db, project_id, sequence, name, pdf_only=False)
    return _file(content, content_type, name)


@router.post(
    "/admin/projects/{project_id}/submissions/{sequence}/dossier",
    response_model=InquiryDetailOut,
    status_code=202,
)
def regenerate_dossier(
    project_id: uuid.UUID,
    sequence: int,
    staff: StaffPrincipal = Reader,
    db: Session = Depends(get_db),
) -> InquiryDetailOut:
    """Gescheitertes Dossier neu erzeugen lassen (V 3.7)."""
    return service.regenerate(db, project_id, sequence, staff.actor_id)
