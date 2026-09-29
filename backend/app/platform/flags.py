"""Feature-Flags: neue Funktionen laufen in Produktion hinter einem Flag (Plan 4.2, 6.5).

Unbekannte Flags sind aus. Die Einführung läuft intern (Rolle) → Beta (Projekte) → öffentlich (alle).
"""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.auth.context import RequestAuth, Role, StaffPrincipal, get_auth, public, require_roles
from app.platform.db import get_db, utcnow
from app.platform.models import FeatureFlag
from app.platform.problems import Problem

router = APIRouter(tags=["flags"])
FLAG_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")


def flag_enabled(flag: FeatureFlag, auth: RequestAuth) -> bool:
    if flag.enabled_for_all:
        return True
    if auth.staff is not None and auth.staff.roles & set(flag.enabled_roles):
        return True
    if auth.api is not None and Role.architect in flag.enabled_roles:
        # Ein API-Schlüssel handelt für die Architekten seiner Organisation (AN6, PLAN_AN6_MANDANTEN 3.6)
        return True
    return auth.project_id is not None and auth.project_id in (flag.enabled_project_ids or [])


def is_enabled(db: Session, key: str, auth: RequestAuth) -> bool:
    flag = db.get(FeatureFlag, key)
    return flag is not None and flag_enabled(flag, auth)


@router.get("/flags", response_model=dict[str, bool], dependencies=[Depends(public)])
def my_flags(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> dict[str, bool]:
    """Nur die für die anfragende Person eingeschalteten Flags; ausgeschaltete bleiben unsichtbar."""
    flags = db.execute(select(FeatureFlag)).scalars()
    return {flag.key: True for flag in flags if flag_enabled(flag, auth)}


class FlagIn(BaseModel):
    description: str = ""
    enabled_for_all: bool = False
    enabled_roles: list[Role] = Field(default_factory=list)
    enabled_project_ids: list[uuid.UUID] = Field(default_factory=list)


class FlagOut(FlagIn):
    key: str
    updated_at: datetime
    updated_by: str | None


def _out(flag: FeatureFlag) -> FlagOut:
    return FlagOut(
        key=flag.key,
        description=flag.description,
        enabled_for_all=flag.enabled_for_all,
        enabled_roles=[Role(r) for r in flag.enabled_roles],
        enabled_project_ids=flag.enabled_project_ids,
        updated_at=flag.updated_at,
        updated_by=flag.updated_by,
    )


@router.get("/admin/flags", response_model=list[FlagOut])
def list_flags(
    staff: StaffPrincipal = Depends(require_roles(Role.ops)), db: Session = Depends(get_db)
) -> list[FlagOut]:
    return [_out(f) for f in db.execute(select(FeatureFlag).order_by(FeatureFlag.key)).scalars()]


@router.put("/admin/flags/{key}", response_model=FlagOut)
def put_flag(
    key: str,
    body: FlagIn,
    staff: StaffPrincipal = Depends(require_roles(Role.ops)),
    db: Session = Depends(get_db),
) -> FlagOut:
    if not FLAG_KEY.match(key):
        raise Problem(422, "validation_error", detail="flag key must match ^[a-z][a-z0-9_]{1,79}$")
    flag = db.get(FeatureFlag, key)
    before = _out(flag).model_dump(mode="json") if flag else None
    if flag is None:
        flag = FeatureFlag(key=key, created_by=staff.actor_id)
        db.add(flag)
    flag.description = body.description
    flag.enabled_for_all = body.enabled_for_all
    flag.enabled_roles = [r.value for r in body.enabled_roles]
    flag.enabled_project_ids = list(body.enabled_project_ids)
    flag.updated_at = utcnow()
    flag.updated_by = staff.actor_id
    db.flush()
    after = _out(flag)
    audit.record(
        db,
        actor_type="staff",
        actor_id=staff.actor_id,
        action="feature_flag.put",
        entity_type="feature_flag",
        entity_id=key,
        before=before,
        after=after.model_dump(mode="json"),
    )
    db.commit()
    return after
