"""Tabellen des Moduls G3 (Plan G3 4.2).

Der Baurahmen selbst wird bei jedem Abruf neu gerechnet und nicht gespeichert; nur der erzeugte
Steckbrief liegt im Objektspeicher, adressiert über die Prüfsumme seiner Eingaben.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk


class EnvelopeSheet(UuidPk, Created, Base):
    """Steckbrief als PDF je Projekt und Eingabestand. Wird mit dem Projekt gelöscht."""

    __tablename__ = "envelope_sheet"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(80))
    """Prüfsumme mit Präfix (`sha256:` und 64 Zeichen)."""
    engine_version: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column()
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "input_hash", name="uq_envelope_sheet_project_hash"),)
