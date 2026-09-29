"""Organisationen (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1): anlegen und Mitglieder zuordnen.

Kern, weil `rules`, `analysis` und `plan` es brauchen. API-Schlüssel, Budget und Scan-Kontingent je
Organisation und das Erscheinungsbild sind seit dem 29.09.2026 zurückgebaut (REFACTORING_PLAN S8); es gilt
das Monatsbudget der Instanz (`EMPRISE_RULES_BUDGET_MONTH_USD`).
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit
from app.platform.auth.context import Role
from app.platform.models import Organisation, OrganisationMember, StaffUser

OPERATOR_NAME = "eigenes-buero"
OPERATOR_DISPLAY_NAME = "Eigenes Büro"
OPERATOR_ONLY_ROLES = frozenset({Role.ops, Role.rules_admin, Role.catalog_admin})
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")


class OrganisationError(Exception):
    """Fehler beim Anlegen oder Zuordnen; die CLI zeigt `code`, die API antwortet mit einem Problem."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Anlegen und Mitglieder (3.1)
# ---------------------------------------------------------------------------


def operator_organisation(db: Session, *, create: bool = False, actor: str = "cli") -> Organisation | None:
    """Die Organisation des Betreibers; mit `create` wird sie beim ersten Konto angelegt."""
    org = db.execute(select(Organisation).where(Organisation.kind == "operator")).scalar_one_or_none()
    if org is None and create:
        org = Organisation(
            name=OPERATOR_NAME, display_name=OPERATOR_DISPLAY_NAME, kind="operator", created_by=actor
        )
        db.add(org)
        db.flush()
    return org


def create_organisation(
    db: Session, settings: Settings, *, name: str, display_name: str, kind: str, actor: str
) -> Organisation:
    if not NAME.match(name):
        raise OrganisationError("invalid_name")
    if kind not in ("operator", "customer"):
        raise OrganisationError("invalid_kind")
    if kind == "customer" and not settings.external_organisations:
        # Fremde Büros erst nach juristischer Prüfung (E-A5, E-AN6-8)
        raise OrganisationError("external_organisations_disabled")
    if kind == "operator" and operator_organisation(db) is not None:
        raise OrganisationError("operator_exists")
    if db.execute(select(Organisation.id).where(Organisation.name == name)).first() is not None:
        raise OrganisationError("name_taken")
    org = Organisation(name=name, display_name=display_name.strip()[:200], kind=kind, created_by=actor)
    db.add(org)
    db.flush()
    audit.record(
        db,
        actor_type="system" if actor == "cli" else "staff",
        actor_id=actor,
        action="organisation.create",
        entity_type="organisation",
        entity_id=str(org.id),
        after={"name": name, "kind": kind},
    )
    return org


def check_roles_allowed(org: Organisation, roles: list[str]) -> None:
    """Rollen des Betriebs nur in der Organisation `operator` (3.1, 7.1 Nr. 11)."""
    if org.kind != "operator" and set(roles) & OPERATOR_ONLY_ROLES:
        raise OrganisationError("operator_roles_outside_operator")


def set_membership(db: Session, org: Organisation, user: StaffUser, role: str, actor: str) -> None:
    """Konto einer Organisation zuordnen oder die Rolle ändern. Ein Konto gehört zu einer Organisation
    (E-AN6-1): Ein Wechsel muss vorher die alte Mitgliedschaft beenden."""
    if role not in ("admin", "member"):
        raise OrganisationError("invalid_role")
    check_roles_allowed(org, user.roles)
    membership = db.get(OrganisationMember, user.id)
    if membership is not None and membership.organisation_id != org.id:
        raise OrganisationError("member_of_other_organisation")
    before = {"role": membership.role} if membership else None
    if membership is None:
        db.add(OrganisationMember(staff_user_id=user.id, organisation_id=org.id, role=role, created_by=actor))
    else:
        membership.role = role
    audit.record(
        db,
        actor_type="system" if actor == "cli" else "staff",
        actor_id=actor,
        action="organisation_member.put",
        entity_type="organisation",
        entity_id=str(org.id),
        before=before,
        after={"staff_user": str(user.id), "role": role},
    )


def admin_count(db: Session, organisation_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(OrganisationMember)
            .join(StaffUser, StaffUser.id == OrganisationMember.staff_user_id)
            .where(
                OrganisationMember.organisation_id == organisation_id,
                OrganisationMember.role == "admin",
                StaffUser.active.is_(True),
            )
        ).scalar_one()
    )
