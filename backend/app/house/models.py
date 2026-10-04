"""Tabellen des Hausmodells (docs/PLAN_HAUSMODELL.md 3.5): Haustyp und Katalog mit Versionen, Prüfbefund der
Kompatibilität.

- `house_template` ist der Haustyp (`slug`), `house_template_version` Entwurf und Version in einem (E-HM-9):
  gelesenes Modell (`raw`), Angaben des Büros (`decisions`), daraus Template (`document`) und Importbericht.
- `house_catalog` je Markt, `house_catalog_version` ein Dokument mit Bauteilen, Slots, Werten, Regeln und
  Preisen (E-HM-8).
- `house_catalog_compatibility`: Befund aus `engine` für ein Paar aus Template- und Katalogversion; das
  Veröffentlichen ist die Freigabe durch einen Menschen.

Veröffentlichte Versionen sind unveränderlich (L4): Der Trigger `house_version_guard` lässt danach nur
`published` → `retired` zu und kein Löschen, `house_compatibility_guard` hält einen freigegebenen Befund fest
(Migration 0024).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk

TEMPLATE_STATUSES = ("draft", "reviewed", "published", "rejected", "retired")
"""`draft`: Import und Entwurf; `reviewed`: Kompatibilität geprüft, wartet auf die Freigabe; `rejected`:
verworfen; `retired`: nicht mehr für neue Konfigurationen."""
CATALOG_STATUSES = ("draft", "published", "retired")


def _known(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class HouseTemplateRecord(UuidPk, Created, Base):
    """Haustyp über alle Versionen (`slug` = `HouseTemplate.slug`)."""

    __tablename__ = "house_template"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    """Zuletzt veröffentlichte Version; neue Konfigurationen beginnen mit ihr (HM4)."""


class HouseTemplateVersion(UuidPk, Created, Base):
    __tablename__ = "house_template_version"

    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_template.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_catalog_version.id"))
    """Katalogversion des Imports: Zuordnungstabelle der Zonen, Fenster- und Türtypen, Prüfung."""
    ifc_file_name: Mapped[str] = mapped_column(String(255))
    ifc_sha256: Mapped[str] = mapped_column(String(64))
    ifc_key: Mapped[str] = mapped_column(String(300))
    ifc_size_bytes: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    """Gelesenes Modell (`RawModel`); leer, solange der Job läuft oder wenn die Datei nicht lesbar war."""
    decisions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Angaben des Büros (`HouseDraftDecisions`); Entwurf und Bericht entstehen daraus neu."""
    document: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    """Template (`HouseTemplate`), sobald es sich bilden ließ."""
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    """Importbericht (`HouseImportReport`); leer, solange der Job läuft."""
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(200))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[str | None] = mapped_column(String(200))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_house_template_version_template_version"),
        CheckConstraint(_known("status", TEMPLATE_STATUSES), name="status_known"),
    )


class HouseCatalogRecord(UuidPk, Created, Base):
    """Katalog eines Markts (E-HM-16: nur FR)."""

    __tablename__ = "house_catalog"

    market: Mapped[str] = mapped_column(String(2), unique=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    """Zuletzt veröffentlichte Version; der Import nimmt sie (3.6 Nr. 3)."""

    __table_args__ = (CheckConstraint("market IN ('FR')", name="market_known"),)


class HouseCatalogVersion(UuidPk, Created, Base):
    __tablename__ = "house_catalog_version"

    catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_catalog.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Katalogversion (`HouseCatalog`)."""
    sha256: Mapped[str] = mapped_column(String(64))
    """Prüfsumme des Dokuments in fester Form; derselbe Katalog ergibt keine neue Version."""
    source: Mapped[str] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(200))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("catalog_id", "version", name="uq_house_catalog_version_catalog_version"),
        CheckConstraint(_known("status", CATALOG_STATUSES), name="status_known"),
    )


class HouseCatalogCompatibility(UuidPk, Created, Base):
    """Prüfbefund Template ↔ Katalog (P 2.1 Nr. 5) aus `engine`; `approved_*` setzt die Veröffentlichung."""

    __tablename__ = "house_catalog_compatibility"

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("house_template_version.id"), index=True
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_catalog_version.id"))
    domain_version: Mapped[str] = mapped_column(String(40))
    supported: Mapped[bool] = mapped_column()
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint(
            "template_version_id", "catalog_version_id", name="uq_house_catalog_compatibility_pair"
        ),
    )
