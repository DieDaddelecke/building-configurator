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


class ServiceToken(UuidPk, Created, Base):
    """Zugang eines anderen Dienstes ohne Person (ADR-12, docs/PLAN_REGELDIENST.md 4.1): nur Leserouten mit
    passendem Recht, keine Projekte. Gespeichert wird nur der SHA-256 des Tokens; angelegt per CLI."""

    __tablename__ = "service_token"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("scopes <@ ARRAY['rules:read']::varchar[]", name="scopes_known"),)


class Project(UuidPk, Created, Base):
    """Anonymes Kundenprojekt. Modul A ergänzt Kontakt und Anfrage, G1 das Grundstück."""

    __tablename__ = "project"

    access_token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    status: Mapped[str] = mapped_column(String(30), server_default=text("'draft'"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    owner_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_user.id", ondelete="SET NULL")
    )
    """Gesetzt für Projekte, die ein Architekt in „Emprise Analyse“ anlegt (AN1). Sie gehören keinem
    Kunden, haben kein Zugangscookie und werden nicht nach 90 Tagen gelöscht (UP06)."""
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisation.id", ondelete="RESTRICT")
    )
    """Organisation, der das Projekt gehört (AN6, docs/PLAN_AN6_MANDANTEN.md 3.2): gesetzt für Projekte aus
    „Emprise Analyse“, ob per Konto oder API-Schlüssel angelegt; NULL für Kundenprojekte des Konfigurators.
    Nur Mitglieder und Schlüssel dieser Organisation sehen das Projekt."""
    name: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(2000))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Name, Notiz und Archiv am Architektenkonto (AN5, docs/PLAN_AN5_AUSGABE.md 3.1). Name und Notiz können
    einen Bauherrn nennen; sie verlassen das System nicht, außer im Bericht der Analyse. Archivieren blendet
    nur aus (E-AN5-7)."""

    __table_args__ = (
        Index(
            "ix_project_owner_staff_user_id",
            "owner_staff_user_id",
            postgresql_where=text("owner_staff_user_id IS NOT NULL"),
        ),
        Index(
            "ix_project_organisation_id",
            "organisation_id",
            "last_activity_at",
            postgresql_where=text("organisation_id IS NOT NULL"),
        ),
    )


class Organisation(UuidPk, Created, Base):
    """Büro mit eigenen Projekten und Mitgliedern (AN6, docs/PLAN_AN6_MANDANTEN.md 3.1). Genau eine
    Organisation der Art `operator`: das Büro, das Emprise betreibt; nur ihre Mitglieder haben die Rollen des
    Betriebs. Weitere (`customer`) erst nach juristischer Prüfung (E-A5). API-Schlüssel, Budget und
    Scan-Kontingent je Organisation und das Erscheinungsbild sind seit dem 29.09.2026 zurückgebaut
    (REFACTORING_PLAN S8, Migration 0023)."""

    __tablename__ = "organisation"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("kind IN ('operator','customer')", name="kind_known"),
        Index("uq_organisation_operator", "kind", unique=True, postgresql_where=text("kind = 'operator'")),
    )


class OrganisationMember(Created, Base):
    """Ein Konto gehört zu höchstens einer Organisation (E-AN6-1)."""

    __tablename__ = "organisation_member"

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_user.id", ondelete="CASCADE"), primary_key=True
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisation.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))

    __table_args__ = (CheckConstraint("role IN ('admin','member')", name="role_known"),)


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
        CheckConstraint("actor_type IN ('staff','customer','system','api_key')", name="actor_type_known"),
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


class AppSetting(Base):
    """Einstellung, die der Betrieb in der Verwaltung ändert – zuerst das KI-Modell der Auswertung (PU11,
    VA09); sie gilt für Konfigurator und Analyse. Ohne Zeile gilt die Umgebung."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))
    """Kennung des Kontos (`StaffUser.id`) oder `system:<Befehl>`."""
    updated_by_name: Mapped[str | None] = mapped_column(String(200))
    """Anzeigename zum Zeitpunkt der Änderung; die Verwaltung zeigt ihn ohne weitere Abfrage."""


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
