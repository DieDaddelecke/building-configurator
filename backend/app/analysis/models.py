"""Tabellen des Moduls AN3 (docs/PLAN_AN3_ANALYSE.md 3.4).

Die Analyse selbst wird wie der Baurahmen bei jedem Abruf neu gerechnet; gespeichert sind nur die Annahmen,
die der Architekt für ein Projekt geändert hat (E-AN3-1). Ohne Zeile gelten die Vorgaben.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class AnalysisParameters(Base):
    """Annahmen je Projekt als `{name: [unten, oben]}`; wird mit dem Projekt gelöscht."""

    __tablename__ = "analysis_parameters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))
