"""Seite „Organisation“ (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1, 3.5–3.7): Mitglieder, Erscheinungsbild,
Verbrauch und API-Schlüssel der eigenen Organisation.

Nur mit Konto, nie mit API-Schlüssel (die Schlüssel reichen nur für `/projects`). Verwalten darf die Rolle
`admin` der Organisation; den Verbrauch sehen alle Mitglieder. Budget und Kontingent ändert nur der Betreiber
über die Kommandozeile (`org-set-budget`), weil sie Teil des Abos sind.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import audit, organisations, storage
from app.platform.auth.context import StaffPrincipal, require_org_admin, require_org_member
from app.platform.db import get_db, utcnow
from app.platform.models import ApiKey, Organisation, OrganisationMember, StaffSession, StaffUser
from app.platform.problems import Problem

router = APIRouter(tags=["organisation"])


class OrganisationOut(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    kind: Literal["operator", "customer"]
    address_lines: list[str]
    phone: str | None
    email: str | None
    website: str | None
    registration: str | None
    accent_color: str | None
    has_logo: bool
    branding_revision: int


class OrganisationIn(BaseModel):
    """Nur die genannten Felder ändern sich; ein leerer Text löscht die Angabe."""

    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    address_lines: list[str] | None = Field(default=None, max_length=4)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=200)
    registration: str | None = Field(default=None, max_length=120)
    accent_color: str | None = Field(default=None, max_length=7)


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    role: Literal["admin", "member"]
    active: bool
    last_login_at: datetime | None
    signed_in: bool
    """Hat sich schon angemeldet (Konto beim Identitätsdienst verbunden)."""


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class MemberRoleIn(BaseModel):
    role: Literal["admin", "member"]


class MonthUsageOut(BaseModel):
    month: str
    cost_usd: float
    ocr_pages: int


class UsageOut(BaseModel):
    budget_month_usd: float | None
    """None: keine eigene Grenze (Organisation des Betreibers)."""
    ocr_pages_month: int | None
    months: list[MonthUsageOut]
    """Neuester Monat zuerst."""


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[Literal["read", "write"]]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    scopes: list[Literal["read", "write"]] = Field(min_length=1)
    days: int = Field(default=organisations.API_KEY_DEFAULT_DAYS, ge=1, le=organisations.API_KEY_MAX_DAYS)


class ApiKeyCreatedOut(ApiKeyOut):
    token: str
    """Der Schlüssel im Klartext – nur in dieser Antwort; gespeichert wird nur sein Hash."""


def _organisation(db: Session, staff: StaffPrincipal, *, lock: bool = False) -> Organisation:
    query = select(Organisation).where(Organisation.id == staff.organisation_id)
    org = db.execute(query.with_for_update() if lock else query).scalar_one_or_none()
    if org is None:
        raise Problem(404, "not_found")
    return org


def _out(org: Organisation) -> OrganisationOut:
    return OrganisationOut(
        id=org.id,
        name=org.name,
        display_name=org.display_name,
        kind="operator" if org.kind == "operator" else "customer",
        address_lines=list(org.address_lines or []),
        phone=org.phone,
        email=org.email,
        website=org.website,
        registration=org.registration,
        accent_color=org.accent_color,
        has_logo=org.logo_key is not None,
        branding_revision=org.branding_revision,
    )


@router.get("/organisation", response_model=OrganisationOut)
def get_organisation(
    staff: StaffPrincipal = Depends(require_org_member), db: Session = Depends(get_db)
) -> OrganisationOut:
    return _out(_organisation(db, staff))


@router.patch("/organisation", response_model=OrganisationOut)
def update_organisation(
    body: OrganisationIn, staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> OrganisationOut:
    """Anzeigename und Schriftfeld für Bericht und DXF (3.5). Jede Änderung zählt `branding_revision` hoch:
    Der nächste Bericht entsteht neu."""
    org = _organisation(db, staff, lock=True)
    changes = body.model_fields_set
    before = _out(org).model_dump(mode="json", exclude={"branding_revision"})
    if "display_name" in changes and body.display_name:
        org.display_name = body.display_name.strip()
    if "address_lines" in changes:
        org.address_lines = [line.strip()[:120] for line in body.address_lines or [] if line.strip()]
    for field in ("phone", "email", "website", "registration"):
        if field in changes:
            setattr(org, field, (getattr(body, field) or "").strip() or None)
    if "accent_color" in changes:
        org.accent_color = organisations.check_accent_color(body.accent_color) if body.accent_color else None
    after = _out(org).model_dump(mode="json", exclude={"branding_revision"})
    if before != after:
        org.branding_revision += 1
        org.updated_at = utcnow()
        audit.record(
            db,
            actor_type="staff",
            actor_id=staff.actor_id,
            action="organisation.update",
            entity_type="organisation",
            entity_id=str(org.id),
            before={k: v for k, v in before.items() if before[k] != after[k]},
            after={k: v for k, v in after.items() if before[k] != after[k]},
        )
    db.commit()
    return _out(org)


@router.put("/organisation/logo", response_model=OrganisationOut)
def put_organisation_logo(
    file: UploadFile = File(...),
    staff: StaffPrincipal = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrganisationOut:
    """Logo als PNG oder JPEG, höchstens 1 MB und 2000 Pixel; wird verkleinert und als PNG neu geschrieben
    (3.5, E-AN6-6: kein SVG)."""
    data = file.file.read(organisations.LOGO_MAX_BYTES + 1)
    org = _organisation(db, staff, lock=True)
    old = organisations.store_logo(db, org, data, staff.actor_id)
    db.commit()
    organisations.delete_file_quietly(old)
    return _out(org)


@router.delete("/organisation/logo", response_model=OrganisationOut)
def delete_organisation_logo(
    staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> OrganisationOut:
    org = _organisation(db, staff, lock=True)
    old = organisations.remove_logo(db, org, staff.actor_id)
    db.commit()
    organisations.delete_file_quietly(old)
    return _out(org)


@router.get(
    "/organisation/logo",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def get_organisation_logo(
    staff: StaffPrincipal = Depends(require_org_member), db: Session = Depends(get_db)
) -> Response:
    """Logo für die Vorschau des Berichtskopfs."""
    org = _organisation(db, staff)
    if org.logo_key is None:
        raise Problem(404, "not_found")
    return Response(
        content=storage.get_bytes(org.logo_key),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# Mitglieder (3.1)
# ---------------------------------------------------------------------------


def _members(db: Session, organisation_id: uuid.UUID) -> list[MemberOut]:
    rows = db.execute(
        select(StaffUser, OrganisationMember.role)
        .join(OrganisationMember, OrganisationMember.staff_user_id == StaffUser.id)
        .where(OrganisationMember.organisation_id == organisation_id)
        .order_by(StaffUser.active.desc(), func.lower(StaffUser.email))
    ).all()
    return [
        MemberOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role="admin" if role == "admin" else "member",
            active=user.active,
            last_login_at=user.last_login_at,
            signed_in=user.oidc_subject is not None,
        )
        for user, role in rows
    ]


@router.get("/organisation/members", response_model=list[MemberOut])
def list_members(
    staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> list[MemberOut]:
    assert staff.organisation_id is not None
    return _members(db, staff.organisation_id)


@router.post("/organisation/members", response_model=list[MemberOut], status_code=201)
def add_member(
    body: MemberIn, staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> list[MemberOut]:
    """Konto mit Rolle `architect` anlegen oder ein Konto ohne Organisation aufnehmen (E-AN6-9). Anmelden
    kann es sich, sobald der Betreiber es beim Identitätsdienst eingerichtet hat; die erste Anmeldung bindet
    es über die bestätigte Adresse."""
    org = _organisation(db, staff, lock=True)
    email = str(body.email).strip().lower()
    user = db.execute(
        select(StaffUser).where(func.lower(StaffUser.email) == email).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        user = StaffUser(email=email, roles=["architect"], created_by=staff.actor_id)
        db.add(user)
        db.flush()
    else:
        membership = db.get(OrganisationMember, user.id)
        if membership is not None:
            raise Problem(
                409,
                "member_exists" if membership.organisation_id == org.id else "member_of_other_organisation",
            )
        if "architect" not in user.roles:
            user.roles = sorted({*user.roles, "architect"})
        user.active = True
    try:
        organisations.set_membership(db, org, user, body.role, staff.actor_id)
    except organisations.OrganisationError as exc:
        raise Problem(409, exc.code) from None
    db.commit()
    return _members(db, org.id)


def _membership(db: Session, organisation_id: uuid.UUID, user_id: uuid.UUID) -> OrganisationMember:
    membership = db.execute(
        select(OrganisationMember)
        .where(
            OrganisationMember.staff_user_id == user_id, OrganisationMember.organisation_id == organisation_id
        )
        .with_for_update()
    ).scalar_one_or_none()
    if membership is None:
        raise Problem(404, "not_found")
    return membership


@router.patch("/organisation/members/{user_id}", response_model=list[MemberOut])
def change_member_role(
    user_id: uuid.UUID,
    body: MemberRoleIn,
    staff: StaffPrincipal = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    org = _organisation(db, staff, lock=True)
    membership = _membership(db, org.id, user_id)
    if membership.role == "admin" and body.role != "admin" and organisations.admin_count(db, org.id) <= 1:
        raise Problem(409, "last_admin")
    user = db.get(StaffUser, user_id)
    assert user is not None
    try:
        organisations.set_membership(db, org, user, body.role, staff.actor_id)
    except organisations.OrganisationError as exc:
        raise Problem(409, exc.code) from None
    db.commit()
    return _members(db, org.id)


@router.delete("/organisation/members/{user_id}", response_model=list[MemberOut])
def remove_member(
    user_id: uuid.UUID, staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> list[MemberOut]:
    """Mitgliedschaft beenden und das Konto sperren; die Projekte bleiben bei der Organisation (3.1)."""
    org = _organisation(db, staff, lock=True)
    if user_id == staff.user_id:
        raise Problem(409, "cannot_remove_self")
    membership = _membership(db, org.id, user_id)
    if membership.role == "admin" and organisations.admin_count(db, org.id) <= 1:
        raise Problem(409, "last_admin")
    user = db.get(StaffUser, user_id)
    assert user is not None
    db.delete(membership)
    user.active = False
    db.execute(
        update(StaffSession)
        .where(StaffSession.staff_user_id == user_id, StaffSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    audit.record(
        db,
        actor_type="staff",
        actor_id=staff.actor_id,
        action="organisation_member.remove",
        entity_type="organisation",
        entity_id=str(org.id),
        after={"staff_user": str(user_id)},
    )
    db.commit()
    return _members(db, org.id)


# ---------------------------------------------------------------------------
# Verbrauch (3.4)
# ---------------------------------------------------------------------------


@router.get("/organisation/usage", response_model=UsageOut)
def get_usage(staff: StaffPrincipal = Depends(require_org_member), db: Session = Depends(get_db)) -> UsageOut:
    """Kosten der Auswertung und erkannte Seiten der letzten sechs Monate mit den Grenzen der Organisation."""
    org = _organisation(db, staff)
    settings = get_settings()
    return UsageOut(
        budget_month_usd=organisations.budget_limit(settings, org),
        ocr_pages_month=organisations.ocr_limit(settings, org),
        months=[
            MonthUsageOut(month=m.month, cost_usd=m.cost_usd, ocr_pages=m.ocr_pages)
            for m in organisations.usage(db, org.id)
        ],
    )


# ---------------------------------------------------------------------------
# API-Schlüssel (3.6)
# ---------------------------------------------------------------------------


def _key_out(key: ApiKey) -> ApiKeyOut:
    scopes: list[Literal["read", "write"]] = ["read"]
    if "write" in key.scopes:
        scopes.append("write")
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        scopes=scopes,
        created_at=key.created_at,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
    )


@router.get("/organisation/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> list[ApiKeyOut]:
    keys = db.execute(
        select(ApiKey)
        .where(ApiKey.organisation_id == staff.organisation_id)
        .order_by(ApiKey.created_at.desc())
    ).scalars()
    return [_key_out(key) for key in keys]


@router.post("/organisation/api-keys", response_model=ApiKeyCreatedOut, status_code=201)
def create_api_key(
    body: ApiKeyIn, staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> ApiKeyCreatedOut:
    """Neuer Schlüssel; er erscheint nur in dieser Antwort. `write` schließt `read` ein."""
    org = _organisation(db, staff, lock=True)
    scopes = ["read", "write"] if "write" in body.scopes else ["read"]
    key, token = organisations.create_api_key(
        db, org.id, name=body.name, scopes=scopes, days=body.days, actor=staff.actor_id
    )
    db.commit()
    return ApiKeyCreatedOut(**_key_out(key).model_dump(), token=token)


@router.delete("/organisation/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: uuid.UUID, staff: StaffPrincipal = Depends(require_org_admin), db: Session = Depends(get_db)
) -> Response:
    assert staff.organisation_id is not None
    organisations.revoke_api_key(db, staff.organisation_id, key_id, staff.actor_id)
    db.commit()
    return Response(status_code=204)
