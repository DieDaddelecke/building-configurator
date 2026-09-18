"""Tabellen des Moduls A (Plan 3.6, docs/PLAN_A_ANFRAGE.md 4.1).

`customer` entsteht schon beim Kontaktformular, bevor die E-Mail-Adresse bestätigt ist; erst die Bestätigung
legt `inquiry` und `consent` an (3.1/3.2 des Plans). `consent` ist unveränderlich wie `audit_log`/`legal_text`
(Migration); `inquiry` nicht, weil `status` sich ändert (3.7) – `number` und `snapshot` sind endgültig, weil
kein Endpunkt sie nach der Anlage schreibt.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk

LOTISSEMENT_VALUES = "('yes','no','unknown')"
INQUIRY_STATUSES = "('neu','in_bearbeitung','beantwortet','geschlossen')"
CONSENT_KINDS = "('simulation_confirmation','transmission_office')"


class Customer(UuidPk, Created, Base):
    __tablename__ = "customer"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    desired_start: Mapped[str | None] = mapped_column(String(60))
    financing_clarified: Mapped[bool | None] = mapped_column(Boolean)
    lotissement: Mapped[str] = mapped_column(String(10), server_default=text("'unknown'"))
    email_code_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    email_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_code_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(f"lotissement IN {LOTISSEMENT_VALUES}", name="lotissement_known"),)


class Inquiry(UuidPk, Created, Base):
    __tablename__ = "inquiry"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id", ondelete="CASCADE"), unique=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'neu'"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_schema_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (CheckConstraint(f"status IN {INQUIRY_STATUSES}", name="status_known"),)


class Consent(UuidPk, Created, Base):
    __tablename__ = "consent"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    legal_text_key: Mapped[str] = mapped_column(String(80))
    legal_text_version: Mapped[int] = mapped_column(Integer)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "kind", name="uq_consent_project_kind"),
        CheckConstraint(f"kind IN {CONSENT_KINDS}", name="kind_known"),
    )
