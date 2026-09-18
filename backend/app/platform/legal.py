"""Versionierte Hinweis-, Einwilligungs- und Rechtstexte (L7, Spez. 10.3, Plan 3.2).

Jede Änderung erzeugt eine neue Version; gespeicherte Versionen sind unveränderlich (Trigger).
Einwilligungen verweisen später auf `key` und `version`. Die Texte selbst entstehen in R1.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.auth.context import Role, StaffPrincipal, public, require_roles
from app.platform.db import get_db
from app.platform.i18n import DEFAULT_LOCALE, Locale, request_locale
from app.platform.models import LegalText

router = APIRouter(tags=["legal"])
KEY_PATTERN = r"^[a-z][a-z0-9_.]{1,79}$"


class LegalTextOut(BaseModel):
    key: str
    locale: Locale
    version: int
    title: str
    body: str
    published_at: datetime


def current_texts(db: Session, locale: Locale, keys: list[str] | None = None) -> list[LegalTextOut]:
    """Jüngste Version je Schlüssel in der Sprache, sonst auf Französisch."""
    latest = (
        select(LegalText.key, LegalText.locale, func.max(LegalText.version).label("version"))
        .group_by(LegalText.key, LegalText.locale)
        .subquery()
    )
    query = (
        select(LegalText)
        .join(
            latest,
            (LegalText.key == latest.c.key)
            & (LegalText.locale == latest.c.locale)
            & (LegalText.version == latest.c.version),
        )
        .where(LegalText.locale.in_({locale, DEFAULT_LOCALE}))
    )
    if keys:
        query = query.where(LegalText.key.in_(keys))
    chosen: dict[str, LegalText] = {}
    for text in db.execute(query).scalars():
        if text.key not in chosen or text.locale == locale:
            chosen[text.key] = text
    return [
        LegalTextOut(
            key=t.key,
            locale=t.locale,
            version=t.version,
            title=t.title,
            body=t.body,
            published_at=t.created_at,
        )
        for t in sorted(chosen.values(), key=lambda t: t.key)
    ]


@router.get("/legal/notices", response_model=list[LegalTextOut], dependencies=[Depends(public)])
def notices(
    request: Request,
    key: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[LegalTextOut]:
    return current_texts(db, request_locale(request), key)


class LegalTextIn(BaseModel):
    key: str = Field(pattern=KEY_PATTERN)
    locale: Locale
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)


def publish(
    db: Session,
    *,
    key: str,
    locale: Locale,
    title: str,
    body: str,
    actor_type: audit.ActorType,
    actor_id: str | None,
) -> LegalText:
    """Neue Version veröffentlichen (Endpunkt und CLI, z. B. `legal-seed` für Modul A, 3.10)."""
    # Sperre je Schlüssel und Sprache, damit parallele Veröffentlichungen nicht dieselbe Version belegen
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"legal:{key}:{locale}"))))
    current = db.execute(
        select(func.max(LegalText.version)).where(LegalText.key == key, LegalText.locale == locale)
    ).scalar()
    text = LegalText(
        key=key, locale=locale, version=(current or 0) + 1, title=title, body=body, created_by=actor_id
    )
    db.add(text)
    db.flush()
    audit.record(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="legal_text.publish",
        entity_type="legal_text",
        entity_id=str(text.id),
        after={"key": text.key, "locale": text.locale, "version": text.version},
    )
    return text


@router.post("/admin/legal-texts", response_model=LegalTextOut, status_code=201)
def publish_text(
    body: LegalTextIn,
    staff: StaffPrincipal = Depends(require_roles(Role.ops)),
    db: Session = Depends(get_db),
) -> LegalTextOut:
    text = publish(
        db,
        key=body.key,
        locale=body.locale,
        title=body.title,
        body=body.body,
        actor_type="staff",
        actor_id=staff.actor_id,
    )
    db.commit()
    db.refresh(text)
    return LegalTextOut(
        key=text.key,
        locale=text.locale,
        version=text.version,
        title=text.title,
        body=text.body,
        published_at=text.created_at,
    )
