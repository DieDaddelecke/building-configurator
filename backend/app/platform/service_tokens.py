"""Service-Token für andere Dienste anlegen, widerrufen, auflisten (ADR-12, docs/PLAN_REGELDIENST.md 4.1).

Das Token erscheint nur beim Anlegen; gespeichert wird der SHA-256. Angelegt und widerrufen wird über die
Kommandozeile, mit Eintrag im Audit-Log. Geprüft wird es in `auth.context.require_service_token`.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.auth.context import SERVICE_TOKEN_PREFIX
from app.platform.auth.tokens import hash_token, new_token
from app.platform.db import utcnow
from app.platform.models import ServiceToken
from app.platform.problems import Problem

SERVICE_SCOPES: tuple[str, ...] = ("rules:read",)
"""Rechte, die ein Token tragen kann; jede Route nennt genau eines (`require_service_token`)."""


@dataclass(frozen=True)
class CreatedToken:
    name: str
    token: str
    """Klartext, nur jetzt sichtbar."""


def create(
    db: Session, name: str, scopes: list[str], *, days: int | None, actor_id: str = "cli"
) -> CreatedToken:
    name = name.strip()
    if not name or len(name) > 80:
        raise Problem(422, "service_token_name_invalid")
    unknown = sorted(set(scopes) - set(SERVICE_SCOPES))
    if unknown or not scopes:
        raise Problem(422, "service_token_scope_unknown", scopes=unknown)
    if db.execute(select(ServiceToken.id).where(ServiceToken.name == name)).first() is not None:
        raise Problem(409, "service_token_exists")
    token = SERVICE_TOKEN_PREFIX + new_token()
    row = ServiceToken(
        name=name,
        token_hash=hash_token(token),
        scopes=sorted(set(scopes)),
        expires_at=utcnow() + timedelta(days=days) if days else None,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor_type="system",
        actor_id=actor_id,
        action="service_token.create",
        entity_type="service_token",
        entity_id=str(row.id),
        after={
            "name": name,
            "scopes": row.scopes,
            "expires_at": str(row.expires_at) if row.expires_at else None,
        },
    )
    db.commit()
    return CreatedToken(name, token)


def revoke(db: Session, name: str, *, actor_id: str = "cli") -> bool:
    """Widerrufen; `False`, wenn es kein aktives Token dieses Namens gibt."""
    row = db.execute(
        select(ServiceToken).where(ServiceToken.name == name.strip(), ServiceToken.revoked_at.is_(None))
    ).scalar_one_or_none()
    if row is None:
        return False
    row.revoked_at = utcnow()
    audit.record(
        db,
        actor_type="system",
        actor_id=actor_id,
        action="service_token.revoke",
        entity_type="service_token",
        entity_id=str(row.id),
        after={"name": row.name},
    )
    db.commit()
    return True


def listing(db: Session) -> list[ServiceToken]:
    return list(db.execute(select(ServiceToken).order_by(ServiceToken.name)).scalars())
