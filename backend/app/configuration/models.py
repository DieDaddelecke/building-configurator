"""Tabellen des Moduls H2 (docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md 4.2, Spez. 4.4) und des Hausmodells.

Eine Konfiguration je Projekt. Sie hält den gewählten Typ als **Typversion** (L4) und die Lage; Prüfung
und Zulässigkeit entstehen bei jedem Abruf neu, weil Regeln, Grundstück und Katalog sich ändern. H3 ergänzt
Linie und Optionen, V friert den Stand in der Anfrage ein. `house_configuration` ist die Konfiguration des
Hausmodells (HM4), bis zur Ablösung daneben.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func, text
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
    package_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("package_version.id"))
    """Gewählte Ausstattungslinie als Version (L4, Plan H3 3.1)."""
    modules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    """Ausdrücklich gewählte Optionen `{module_version_id}` (Spez. 4.4); die der Linie kommen dazu."""
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))


class HouseConfigurationRecord(UuidPk, Created, Base):
    """Konfiguration des Hausmodells (docs/PLAN_HAUSMODELL.md 3.5, HM4), eine je Projekt, neben
    `configuration` bis zur Ablösung (3.12).

    Template- und Katalogversion sind festgehalten (E-HM-7, L4); Grundstück und Regeln gelten im aktuellen
    Stand. Der Snapshot hält das maßgebliche Ergebnis von `engine` beim Speichern (exakte Beträge, Mengen,
    Regelergebnisse, Hausbeschreibung) und die PLU-Prüfung mit ihrem Prüfstempel; der Kunde sieht daraus nur
    gerundete Beträge (L1). Der Status wird nie gespeichert (3.7).
    """

    __tablename__ = "house_configuration"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), unique=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    template_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("house_template_version.id"))
    catalog_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("house_catalog_version.id"))
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("""'{"selections": {}}'::jsonb""")
    )
    """Auswahl (`HouseConfiguration`); leer heißt: die Standards des Templates."""
    placement: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    """`{origin_e, origin_n, rotation_deg}` in Lambert-93 wie `configuration.placement`."""
    boundary_options: Mapped[dict[str, bool]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    """`{computed_at, domain_version, evaluation, site, price_check}`; leer ohne Template."""
    engine_version: Mapped[str | None] = mapped_column(String(40))
    """Stand des Rechenkerns beim Speichern (`HouseEvaluation.domain_version`, P 16)."""
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(
            "(template_version_id IS NULL) = (catalog_version_id IS NULL)", name="versions_together"
        ),
    )
