"""Wer fragt an: Mitarbeitende (Sitzung nach OIDC) oder Kunde (anonymes Projekt-Cookie). Den Zugang über
API-Schlüssel einer Organisation (AN6) gibt es seit dem 29.09.2026 nicht mehr (REFACTORING_PLAN S8).

Jeder Endpunkt MUSS genau eine Zugriffsregel aus diesem Modul als Abhängigkeit tragen.
`tests/integration/test_access_policies.py` prüft das für alle Routen,
`tests/integration/test_organisations.py` die Trennung der Organisationen (docs/PLAN_AN6_MANDANTEN.md 3.2):
Projekte einer Organisation sehen nur ihre Mitglieder, und die Rollen des Betriebs wirken nur in der
Organisation `operator`.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any, Literal

from fastapi import Depends, Request
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.platform.auth.tokens import PROJECT_COOKIE, STAFF_COOKIE, hash_token
from app.platform.db import get_db, get_engine, utcnow
from app.platform.models import Organisation, OrganisationMember, Project, StaffSession, StaffUser
from app.platform.problems import Problem

ACTIVITY_WRITE_INTERVAL = timedelta(minutes=10)


class Role(StrEnum):
    architect = "architect"
    rules_admin = "rules_admin"
    catalog_admin = "catalog_admin"
    ops = "ops"


OrganisationKind = Literal["operator", "customer"]


def effective_roles(roles: frozenset[Role], kind: str | None) -> frozenset[Role]:
    """Rollen, die für ein Konto wirken (3.2): alle in der Organisation `operator`, nur `architect` in einer
    fremden, keine ohne Organisation."""
    if kind == "operator":
        return roles
    if kind == "customer":
        return roles & {Role.architect}
    return frozenset()


@dataclass(frozen=True)
class StaffPrincipal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    display_name: str | None
    roles: frozenset[Role]
    """Wirksame Rollen (`effective_roles`), nicht die gespeicherten."""
    organisation_id: uuid.UUID | None = None
    organisation_kind: OrganisationKind | None = None
    org_role: Literal["admin", "member"] | None = None

    @property
    def actor_id(self) -> str:
        return str(self.user_id)

    @property
    def actor_type(self) -> Literal["staff"]:
        return "staff"

    @property
    def is_operator(self) -> bool:
        return self.organisation_kind == "operator"


Principal = StaffPrincipal
"""Wer Projekte einer Organisation bearbeitet: ein Architekt mit Organisation (`RequestAuth.principal`)."""


@dataclass(frozen=True)
class RequestAuth:
    staff: StaffPrincipal | None = None
    project_id: uuid.UUID | None = None

    @property
    def principal(self) -> Principal | None:
        staff = self.staff
        if staff is not None and staff.organisation_id is not None and Role.architect in staff.roles:
            return staff
        return None


def _touch(table: Any, row_id: uuid.UUID, column: str) -> None:
    """Aktivität außerhalb der Anfragetransaktion festhalten (zählt auch bei reinen Lesezugriffen)."""
    with get_engine().begin() as conn:
        conn.execute(update(table).where(table.id == row_id).values({column: utcnow()}))


def _resolve_staff(db: Session, token: str) -> StaffPrincipal | None:
    now = utcnow()
    row = db.execute(
        select(StaffSession, StaffUser, OrganisationMember.role, Organisation.id, Organisation.kind)
        .join(StaffUser, StaffUser.id == StaffSession.staff_user_id)
        .outerjoin(OrganisationMember, OrganisationMember.staff_user_id == StaffUser.id)
        .outerjoin(
            Organisation,
            and_(Organisation.id == OrganisationMember.organisation_id, Organisation.active.is_(True)),
        )
        .where(
            StaffSession.token_hash == hash_token(token),
            StaffSession.revoked_at.is_(None),
            StaffSession.expires_at > now,
            StaffUser.active.is_(True),
        )
    ).first()
    if row is None:
        return None
    staff_session, user, org_role, organisation_id, kind = row
    if now - staff_session.last_seen_at > ACTIVITY_WRITE_INTERVAL:
        _touch(StaffSession, staff_session.id, "last_seen_at")
    return StaffPrincipal(
        user_id=user.id,
        session_id=staff_session.id,
        email=user.email,
        display_name=user.display_name,
        roles=effective_roles(frozenset(Role(r) for r in user.roles), kind),
        organisation_id=organisation_id,
        organisation_kind=kind,
        org_role=org_role if organisation_id is not None else None,
    )


def _resolve_project(db: Session, token: str) -> uuid.UUID | None:
    row = db.execute(
        select(Project.id, Project.last_activity_at).where(Project.access_token_hash == hash_token(token))
    ).first()
    if row is None:
        return None
    if utcnow() - row.last_activity_at > ACTIVITY_WRITE_INTERVAL:
        _touch(Project, row.id, "last_activity_at")
    project_id: uuid.UUID = row.id
    return project_id


def get_auth(request: Request, db: Session = Depends(get_db)) -> RequestAuth:
    cached = getattr(request.state, "auth", None)
    if isinstance(cached, RequestAuth):
        return cached
    staff_token = request.cookies.get(STAFF_COOKIE)
    project_token = request.cookies.get(PROJECT_COOKIE)
    auth = RequestAuth(
        staff=_resolve_staff(db, staff_token) if staff_token else None,
        project_id=_resolve_project(db, project_token) if project_token else None,
    )
    request.state.auth = auth
    return auth


def project_organisation(db: Session, project_id: uuid.UUID) -> uuid.UUID | None:
    """Organisation des Projekts; None für Kundenprojekte und unbekannte Projekte."""
    return db.execute(select(Project.organisation_id).where(Project.id == project_id)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Zugriffsregeln. Das Attribut __access_policy__ kennzeichnet sie für den Routentest.
# ---------------------------------------------------------------------------


def _policy(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def mark(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__access_policy__ = name  # type: ignore[attr-defined]
        return func

    return mark


@_policy("public")
def public() -> None:
    """Ohne Anmeldung erreichbar. Öffentliche Endpunkte mit Last brauchen zusätzlich ein Rate-Limit."""


@_policy("checked_in_handler")
def checked_in_handler(auth: RequestAuth = Depends(get_auth)) -> RequestAuth:
    """Der Endpunkt prüft den Zugriff selbst, weil er vom gelesenen Datensatz abhängt."""
    return auth


@_policy("staff")
def require_staff(auth: RequestAuth = Depends(get_auth)) -> StaffPrincipal:
    if auth.staff is None:
        raise Problem(401, "authentication_required")
    return auth.staff


def _check_staff_project(db: Session, staff: StaffPrincipal, raw: object) -> None:
    """`/admin`-Route mit Projekt: nur Projekte der eigenen Organisation, Kundenprojekte ohne Organisation
    nur für `operator` (3.2). Kein Durchgriff auf fremde Organisationen, auch nicht für den Betrieb."""
    try:
        project_id = uuid.UUID(str(raw))
    except ValueError:
        return  # FastAPI lehnt die Kennung danach ab (422)
    row = db.execute(select(Project.organisation_id).where(Project.id == project_id)).first()
    if row is None:
        return  # Der Endpunkt antwortet 404
    organisation_id = row.organisation_id
    if organisation_id is None and staff.is_operator:
        return
    if organisation_id is not None and organisation_id == staff.organisation_id:
        return
    raise Problem(404, "not_found")


def require_roles(*roles: Role, organisations: bool = False) -> Callable[..., StaffPrincipal]:
    """Rolle wie bisher; dazu die Organisation (3.2): Trägt der Pfad eine `project_id`, muss das Projekt zur
    Organisation des Kontos gehören. Sonst ist die Route nur für die Organisation `operator`, außer
    `organisations=True` öffnet sie für alle."""
    allowed = frozenset(roles)

    @_policy("roles:" + ",".join(sorted(allowed)))
    def dependency(
        request: Request, staff: StaffPrincipal = Depends(require_staff), db: Session = Depends(get_db)
    ) -> StaffPrincipal:
        if not staff.roles & allowed:
            raise Problem(403, "forbidden")
        raw = request.path_params.get("project_id")
        if raw is not None:
            _check_staff_project(db, staff, raw)
        elif not (organisations or staff.is_operator):
            raise Problem(403, "forbidden")
        return staff

    # Für `test_access_policies`: Offene Routen ohne `project_id` müssen dort begründet sein (B-23)
    dependency.__open_to_organisations__ = organisations  # type: ignore[attr-defined]
    return dependency


@_policy("organisation")
def require_organisation(auth: RequestAuth = Depends(get_auth)) -> Principal:
    """Architekt mit Organisation: Liste und Anlage der Projekte der Organisation (3.2)."""
    principal = auth.principal
    if principal is None and auth.staff is None:
        raise Problem(401, "authentication_required")
    if principal is None:
        raise Problem(403, "forbidden")
    return principal


@_policy("org_member")
def require_org_member(staff: StaffPrincipal = Depends(require_staff)) -> StaffPrincipal:
    """Jedes Mitglied einer Organisation, auch ohne Rolle (Seite Organisation, Verbrauch)."""
    if staff.organisation_id is None:
        raise Problem(403, "forbidden")
    return staff


@_policy("org_admin")
def require_org_admin(staff: StaffPrincipal = Depends(require_staff)) -> StaffPrincipal:
    """Verwaltung der eigenen Organisation: Name und Mitglieder (3.1)."""
    if staff.organisation_id is None or staff.org_role != "admin":
        raise Problem(403, "forbidden")
    return staff


@_policy("project")
def require_project_access(
    project_id: uuid.UUID, auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)
) -> uuid.UUID:
    """Das Projekt aus dem eigenen Cookie – oder ein Projekt der eigenen Organisation für einen Architekten
    (AN1, UP05, AN6). Fremde Projekte erscheinen als nicht vorhanden.

    Kundenprojekte haben keine Organisation und bleiben für Mitarbeitende über diesen Weg unerreichbar; das
    Büro sieht sie über die eigenen `/admin`-Endpunkte.
    """
    if auth.project_id == project_id:
        return project_id
    principal = auth.principal
    if principal is not None and project_organisation(db, project_id) == principal.organisation_id:
        return project_id
    raise Problem(404, "not_found")


@_policy("owned_project")
def require_owned_project(
    project_id: uuid.UUID, auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)
) -> Principal:
    """Nur ein Architekt der Organisation des Projekts (AN2, docs/PLAN_AN2_PLU.md 3.7; AN6).
    Für Aktionen, die Kosten auslösen (Auswertung eines hochgeladenen Reglements): Das Projekt-Cookie eines
    Kunden reicht nicht. Sonst `404` wie bei fremden Projekten."""
    principal = auth.principal
    if principal is None or project_organisation(db, project_id) != principal.organisation_id:
        raise Problem(404, "not_found")
    return principal
