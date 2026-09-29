"""Tabellen der Module AN3 und AN5 (docs/PLAN_AN3_ANALYSE.md 3.4, docs/PLAN_AN5_AUSGABE.md 3.6).

Die Analyse selbst wird wie der Baurahmen bei jedem Abruf neu gerechnet; gespeichert sind nur die Annahmen,
die der Architekt für ein Projekt geändert hat (E-AN3-1), und die erzeugten Berichte. Ohne Zeile gelten die
Vorgaben.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk


class AnalysisParameters(Base):
    """Annahmen je Projekt als `{name: [unten, oben]}`; wird mit dem Projekt gelöscht."""

    __tablename__ = "analysis_parameters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))


class AnalysisReport(UuidPk, Created, Base):
    """Bericht als PDF je Projekt, Prüfsumme und Sprache (AN5 3.6). Die Zeile löscht die Datenbank mit dem
    Projekt, die Datei `platform.projects.delete_project` über `register_storage_keys`."""

    __tablename__ = "analysis_report"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(80))
    """Prüfsumme des Berichts mit Präfix (`sha256:` und 64 Zeichen), nicht die der Analyse."""
    locale: Mapped[str] = mapped_column(String(5))
    engine_version: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column()
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "input_hash", "locale", name="uq_analysis_report_project_hash_locale"),
    )
