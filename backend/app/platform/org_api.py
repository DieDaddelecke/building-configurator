"""Seite „Organisation“ (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1, 3.7): Name und Mitglieder der eigenen
Organisation.

Nur mit Konto. Verwalten darf die Rolle `admin` der Organisation; den Namen sehen alle Mitglieder.
Erscheinungsbild, Verbrauch und API-Schlüssel sind seit dem 29.09.2026 zurückgebaut (REFACTORING_PLAN S8).
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.platform import audit, organisations
from app.platform.auth.context import StaffPrincipal, require_org_admin, require_org_member
from app.platform.db import get_db, utcnow
from app.platform.models import Organisation, OrganisationMember, StaffSession, StaffUser
from app.platform.problems import Problem

router = APIRouter(tags=["organisation"])


class OrganisationOut(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    kind: Literal["operator", "customer"]


class OrganisationIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=200)


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
    """Anzeigename der Organisation (Kopf der Seiten, Sitzung)."""
    org = _organisation(db, staff, lock=True)
    name = body.display_name.strip()
    if name != org.display_name:
        audit.record(
            db,
            actor_type="staff",
            actor_id=staff.actor_id,
            action="organisation.update",
            entity_type="organisation",
            entity_id=str(org.id),
            before={"display_name": org.display_name},
            after={"display_name": name},
        )
        org.display_name, org.updated_at = name, utcnow()
    db.commit()
    return _out(org)


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
