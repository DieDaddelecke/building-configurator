"""Wer fragt an: Mitarbeitende (Sitzung nach OIDC) und/oder Kunde (anonymes Projekt-Cookie).

Jeder Endpunkt MUSS genau eine Zugriffsregel aus diesem Modul als Abhängigkeit tragen.
`tests/integration/test_access_policies.py` prüft das für alle Routen.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.platform.auth.tokens import PROJECT_COOKIE, STAFF_COOKIE, hash_token
from app.platform.db import get_db, get_engine, utcnow
from app.platform.models import Project, StaffSession, StaffUser
from app.platform.problems import Problem

ACTIVITY_WRITE_INTERVAL = timedelta(minutes=10)


class Role(StrEnum):
    architect = "architect"
    rules_admin = "rules_admin"
    catalog_admin = "catalog_admin"
    ops = "ops"


@dataclass(frozen=True)
class StaffPrincipal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    display_name: str | None
    roles: frozenset[Role]

    @property
    def actor_id(self) -> str:
        return str(self.user_id)


@dataclass(frozen=True)
class RequestAuth:
    staff: StaffPrincipal | None = None
    project_id: uuid.UUID | None = None


def _touch(table: Any, row_id: uuid.UUID, column: str) -> None:
    """Aktivität außerhalb der Anfragetransaktion festhalten (zählt auch bei reinen Lesezugriffen)."""
    with get_engine().begin() as conn:
        conn.execute(update(table).where(table.id == row_id).values({column: utcnow()}))


def _resolve_staff(db: Session, token: str) -> StaffPrincipal | None:
    now = utcnow()
    row = db.execute(
        select(StaffSession, StaffUser)
        .join(StaffUser, StaffUser.id == StaffSession.staff_user_id)
        .where(
            StaffSession.token_hash == hash_token(token),
            StaffSession.revoked_at.is_(None),
            StaffSession.expires_at > now,
            StaffUser.active.is_(True),
        )
    ).first()
    if row is None:
        return None
    staff_session, user = row
    if now - staff_session.last_seen_at > ACTIVITY_WRITE_INTERVAL:
        _touch(StaffSession, staff_session.id, "last_seen_at")
    return StaffPrincipal(
        user_id=user.id,
        session_id=staff_session.id,
        email=user.email,
        display_name=user.display_name,
        roles=frozenset(Role(r) for r in user.roles),
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


def require_roles(*roles: Role) -> Callable[..., StaffPrincipal]:
    allowed = frozenset(roles)

    @_policy("roles:" + ",".join(sorted(allowed)))
    def dependency(staff: StaffPrincipal = Depends(require_staff)) -> StaffPrincipal:
        if not staff.roles & allowed:
            raise Problem(403, "forbidden")
        return staff

    return dependency


@_policy("project")
def require_project_access(
    project_id: uuid.UUID, auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)
) -> uuid.UUID:
    """Das Projekt aus dem eigenen Cookie – oder ein Projekt des eigenen Büros, wenn ein Architekt
    angemeldet ist (AN1, UP05). Fremde Projekte erscheinen als nicht vorhanden.

    Kundenprojekte haben keinen Eigentümer und bleiben auch für Mitarbeitende über diesen Weg
    unerreichbar; das Büro sieht sie über die eigenen `/admin`-Endpunkte.
    """
    if auth.project_id == project_id:
        return project_id
    if auth.staff is not None and Role.architect in auth.staff.roles and _has_owner(db, project_id):
        return project_id
    raise Problem(404, "not_found")


def _has_owner(db: Session, project_id: uuid.UUID) -> bool:
    owner = db.execute(
        select(Project.owner_staff_user_id).where(Project.id == project_id)
    ).scalar_one_or_none()
    return owner is not None


@_policy("owned_project")
def require_owned_project(
    project_id: uuid.UUID, auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)
) -> StaffPrincipal:
    """Nur ein angemeldeter Architekt und nur ein Projekt **mit** Eigentümer (AN2, docs/PLAN_AN2_PLU.md
    3.7). Für Aktionen, die Kosten auslösen (Auswertung eines hochgeladenen Reglements): Das
    Projekt-Cookie eines Kunden reicht nicht. Sonst `404` wie bei fremden Projekten."""
    if auth.staff is None or Role.architect not in auth.staff.roles or not _has_owner(db, project_id):
        raise Problem(404, "not_found")
    return auth.staff
