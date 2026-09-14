"""Tabellen der Plattform (Modul P). Fachmodule legen eigene `models.py` an."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk


class StaffUser(UuidPk, Created, Base):
    """Mitarbeitende von Büro und Emprise. Rollen werden hier gepflegt, nicht beim Identitätsdienst."""

    __tablename__ = "staff_user"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "roles <@ ARRAY['architect','rules_admin','catalog_admin','ops']::varchar[]", name="roles_known"
        ),
    )


class StaffSession(UuidPk, Created, Base):
    __tablename__ = "staff_session"

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amr: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))


class Project(UuidPk, Created, Base):
    """Anonymes Kundenprojekt. Modul A ergänzt Kontakt und Anfrage, G1 das Grundstück."""

    __tablename__ = "project"

    access_token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    status: Mapped[str] = mapped_column(String(30), server_default=text("'draft'"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Nur anfügen; ein Trigger verhindert Änderungen und Löschungen. Keine personenbezogenen Daten."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("actor_type IN ('staff','customer','system')", name="actor_type_known"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )


class Job(UuidPk, Created, Base):
    """Warteschlange in PostgreSQL (Plan 6.3). Anlage in derselben Transaktion wie die Fachänderung."""

    __tablename__ = "job"

    queue: Mapped[str] = mapped_column(String(40), server_default=text("'default'"))
    kind: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'queued'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    timeout_seconds: Mapped[int] = mapped_column(Integer, server_default=text("60"))
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), index=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed')", name="status_known"),
        Index("ix_job_claim", "queue", "run_after", postgresql_where=text("status = 'queued'")),
        Index("ix_job_running", "locked_at", postgresql_where=text("status = 'running'")),
        Index(
            "uq_job_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class PeriodicSchedule(Base):
    __tablename__ = "periodic_schedule"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeatureFlag(Created, Base):
    """Freischaltung je Rolle, Projekt oder für alle (Plan 4.2, 6.5)."""

    __tablename__ = "feature_flag"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    enabled_for_all: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    enabled_roles: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
    enabled_project_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=text("'{}'")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))


class LegalText(UuidPk, Created, Base):
    """Versionierte Hinweis-, Einwilligungs- und Rechtstexte (L7, Spez. 10.3). Unveränderlich."""

    __tablename__ = "legal_text"

    key: Mapped[str] = mapped_column(String(80))
    locale: Mapped[str] = mapped_column(String(5))
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("key", "locale", "version", name="uq_legal_text_key_locale_version"),
        CheckConstraint("locale IN ('fr','de')", name="locale_known"),
        CheckConstraint("version >= 1", name="version_positive"),
    )


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counter"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
