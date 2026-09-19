"""Tabelle des Moduls H2 (docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md 4.2, Spez. 4.4).

Eine Konfiguration je Projekt. Sie hält den gewählten Typ als **Typversion** (L4) und die Lage; Prüfung
und Zulässigkeit entstehen bei jedem Abruf neu, weil Regeln, Grundstück und Katalog sich ändern. H3 ergänzt
Linie und Optionen, V friert den Stand in der Anfrage ein.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk


class Configuration(UuidPk, Created, Base):
    __tablename__ = "configuration"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), unique=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    """Erhöht sich mit jeder Änderung; `If-Match` der API bezieht sich darauf."""
    building_type_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("building_type_version.id"))
    placement: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    """`{origin_e, origin_n, rotation_deg}`; Lambert-93 wie Spez. 4.4, die API rechnet in lokale Meter um."""
    boundary_options: Mapped[dict[str, bool]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    """Kantennummer (als Text) → Bauen auf der Grenze (Plan H2 3.4)."""
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))
