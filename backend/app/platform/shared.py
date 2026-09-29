"""Gemeinsame Datenbank beider Produkte (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.9).

Konfigurator und Analyse teilen programmweite Daten: das KI-Modell der Auswertung, Referenzlisten und ihr
Audit. Eigene Basisklasse, eigene Migrationen (`migrations_shared`, Versionstabelle
`alembic_version_shared`), eigene Verbindung (`EMPRISE_SHARED_DATABASE_URL`). Ohne eigene Verbindung liegen
die Tabellen in der Datenbank der Instanz – so laufen Tests und eine Instanz allein ohne zweite Datenbank.

Konten liegen je Instanz: Wer etwas ändert, steht als Produkt, Kennung und Anzeigename, ohne Fremdschlüssel.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import DateTime, Engine, MetaData, String, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import Settings, get_settings
from app.platform.db import NAMING


class SharedBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def shared_url(settings: Settings) -> str:
    return settings.shared_database_url or settings.database_url


def shared_migration_url(settings: Settings) -> str:
    """Migrationen mit der Rolle `migrator` wie bei der Instanz (Plan 6.6)."""
    if settings.shared_database_url:
        return settings.shared_migration_database_url or settings.shared_database_url
    return settings.migration_database_url or settings.database_url


@lru_cache
def get_shared_engine() -> Engine:
    return create_engine(shared_url(get_settings()), pool_pre_ping=True, pool_size=3, max_overflow=3)


@lru_cache
def get_shared_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_shared_engine(), expire_on_commit=False)


def get_shared_db() -> Iterator[Session]:
    session = get_shared_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def shared_session() -> Iterator[Session]:
    session = get_shared_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


class SharedSetting(SharedBase):
    """Programmweite Einstellung, die der Betrieb in der Verwaltung ändert – zuerst das KI-Modell der
    Auswertung (PU11, VA09). Ohne Zeile gilt die Umgebung der jeweiligen Instanz."""

    __tablename__ = "shared_setting"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))
    """`<Produkt>:<Kennung>` des Kontos in seiner Instanz."""
    updated_by_name: Mapped[str | None] = mapped_column(String(200))


class SharedAudit(SharedBase):
    """Änderungen an gemeinsamen Daten; das Audit-Log der Instanz sieht nur deren eigene."""

    __tablename__ = "shared_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    product: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(200))
    actor_name: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


INSTANCE = "emprise"
"""Kennung im gemeinsamen Audit, seit Konfigurator und Analyse eine Anwendung sind (bis zur Übernahme in
`audit_log`, REFACTORING_PLAN S4)."""


def actor(settings: Settings, actor_id: str) -> str:
    return f"{INSTANCE}:{actor_id}"


def record(
    session: Session,
    settings: Settings,
    *,
    actor_id: str,
    actor_name: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Eintrag im gemeinsamen Audit; der Aufrufer bestätigt die Sitzung."""
    session.add(
        SharedAudit(
            product=INSTANCE,
            actor_id=actor(settings, actor_id),
            actor_name=actor_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
