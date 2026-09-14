"""Datenbankverbindung, Basisklasse und Sitzungen.

Schreibende Endpunkte rufen `session.commit()` selbst auf. Die Abhängigkeit `get_db`
schließt nur und rollt nicht bestätigte Änderungen zurück.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import DateTime, Engine, MetaData, String, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Created:
    """Pflichtspalten jeder Tabelle (Spez. 4.1)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(200))


def utcnow() -> datetime:
    return datetime.now(UTC)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
