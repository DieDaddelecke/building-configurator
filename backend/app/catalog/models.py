"""Tabellen des Moduls H1 (Plan H1 4.1, Spez. 4.3 – reduziert auf den Weg ohne IFC).

Bewusst nicht angelegt (Plan H1 4.1, 8): `variant_group`/`variant`/`space_category_map` (kein heutiger
Typ braucht Variantengruppen), `ifc_package`/`type_facts` (kein Modell, kein Kombinationscache),
`price_item`/`measurement_rule` (Optionspreise sind feste Spannen, kein Mengengerüst vor X3).

Jede Katalogart ist eine Identität (`building_type`, `package`, `module`, `price_catalog`) mit
Versionen; nur die Identität hat einen stabilen Schlüssel, Preise binden an sie (Plan H1 3.7). Eine
veröffentlichte Version ist unveränderlich (L4): der Trigger `forbid_published_modification` blockt
UPDATE und DELETE, sobald `status = 'published'`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk

VERSION_STATUSES = "('draft','review','published','retired')"


class BuildingType(UuidPk, Created, Base):
    """Typ-Identität (Plan H1 3.7): Preise und RE2020-Bewertungen binden hieran, nicht an eine Version."""

    __tablename__ = "building_type"

    slug: Mapped[str] = mapped_column(String(60), unique=True)
    family: Mapped[str | None] = mapped_column(String(60))
    alternatives: Mapped[list[str]] = mapped_column(ARRAY(String(60)), server_default=text("'{}'"))
    """Slugs anderer Typen, die beim Sperren als Vorschlag erscheinen (Spez. 5.4.6)."""
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class BuildingTypeVersion(UuidPk, Created, Base):
    __tablename__ = "building_type_version"

    building_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("building_type.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    name: Mapped[str] = mapped_column(String(120))
    storeys: Mapped[str] = mapped_column(String(20))
    """PLU-Notation, z. B. `R+1`, `R+1+C` (Spez. 5.4.3)."""
    roof_form: Mapped[str] = mapped_column(String(10))
    pitch_deg: Mapped[float | None] = mapped_column()
    ridge_direction: Mapped[str | None] = mapped_column(String(10))
    ridge_height_m: Mapped[float] = mapped_column()
    eave_height_m: Mapped[float] = mapped_column()
    footprint_facade: Mapped[list[list[float]]] = mapped_column(JSONB)
    """Polygon in lokalen Metern, Y-Achse = Modellnord; kein geografischer Bezug vor der Implantation
    (Spez. 5.4.4)."""
    footprint_facade_area_m2: Mapped[float] = mapped_column()
    footprint_projection: Mapped[list[list[float]]] = mapped_column(JSONB)
    footprint_projection_area_m2: Mapped[float] = mapped_column()
    living_area_m2: Mapped[float] = mapped_column()
    rooms_text: Mapped[str] = mapped_column(String(300))
    rooms: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    """Flache Liste `{name, category, storey, area_m2}` (Plan H1 3.2), ohne Dachschrägen-Schnitt."""
    facade_roles: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    """Kantenindex (als Text) → Rolle (`street`/`garden`/`side_left`/`side_right`), in der Katalogpflege
    zugewiesen (Plan H1 3.3), leer bis dahin."""
    entrance: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    """`{edge_index, position_m}` auf `footprint_facade`."""
    garage_door: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    base_price_min_cents: Mapped[int] = mapped_column()
    base_price_max_cents: Mapped[int] = mapped_column()
    consistency_warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    """Befunde aus `domain.consistency`, die die Veröffentlichung nicht sperren (nur `error`-Befunde
    tun das, Plan H1 3.9)."""
    source_xlsx_key: Mapped[str] = mapped_column(String(300))
    source_xlsx_sha256: Mapped[str] = mapped_column(String(64))
    source_dxf_key: Mapped[str] = mapped_column(String(300))
    source_dxf_sha256: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column()
    published_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("building_type_id", "version", name="uq_building_type_version_type_version"),
        CheckConstraint(f"status IN {VERSION_STATUSES}", name="status_known"),
        CheckConstraint("roof_form IN ('gable','hip','flat','complex')", name="roof_form_known"),
    )


class Package(UuidPk, Created, Base):
    """Ausstattungslinie, Identität (Plan H1 4.1)."""

    __tablename__ = "package"

    slug: Mapped[str] = mapped_column(String(60), unique=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class PackageVersion(UuidPk, Created, Base):
    __tablename__ = "package_version"

    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("package.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    label_de: Mapped[str] = mapped_column(String(120))
    label_fr: Mapped[str] = mapped_column(String(120))
    scope: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    """Stichpunkte des Leistungsumfangs (Mockup `LINIEN[].umfang`)."""
    included_module_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=text("'{}'")
    )
    regulatory: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    """Materialklassen der Linie für die Regelprüfung (`facade_material`, `roof_material`, Plan H3 3.2)."""
    published_at: Mapped[datetime | None] = mapped_column()
    published_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("package_id", "version", name="uq_package_version_package_version"),
        CheckConstraint(f"status IN {VERSION_STATUSES}", name="status_known"),
    )


class Module(UuidPk, Created, Base):
    """Option, Identität (Plan H1 4.1). `geometry_mode` ist für alle heutigen Optionen `none` (3.1)."""

    __tablename__ = "module"

    slug: Mapped[str] = mapped_column(String(60), unique=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ModuleVersion(UuidPk, Created, Base):
    __tablename__ = "module_version"

    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    label_de: Mapped[str] = mapped_column(String(120))
    label_fr: Mapped[str] = mapped_column(String(120))
    geometry_mode: Mapped[str] = mapped_column(String(20), server_default=text("'none'"))
    excludes_slugs: Mapped[list[str]] = mapped_column(ARRAY(String(60)), server_default=text("'{}'"))
    kind: Mapped[str] = mapped_column(String(20), server_default=text("'plain'"))
    """`plain`, `terrace`, `carport` (Plan H3 3.2). Die Art legt Geometrie und Einheit des Preises fest."""
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    """Maße der Art, geprüft und mit Standardwerten gefüllt (`domain.options.normalize_params`)."""
    regulatory: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    published_at: Mapped[datetime | None] = mapped_column()
    published_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("module_id", "version", name="uq_module_version_module_version"),
        CheckConstraint(f"status IN {VERSION_STATUSES}", name="status_known"),
        CheckConstraint("geometry_mode IN ('none','parametric','ifc_variant')", name="geometry_mode_known"),
        CheckConstraint("kind IN ('plain','terrace','carport')", name="kind_known"),
    )


class PriceCatalog(UuidPk, Created, Base):
    __tablename__ = "price_catalog"

    region: Mapped[str] = mapped_column(String(60))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class PriceCatalogVersion(UuidPk, Created, Base):
    __tablename__ = "price_catalog_version"

    price_catalog_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_catalog.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    valid_from: Mapped[Any] = mapped_column(Date)
    vat_rate_default: Mapped[float] = mapped_column(server_default=text("0.20"))
    """Brutto-Anzeige (Entscheidung D10)."""
    published_at: Mapped[datetime | None] = mapped_column()
    published_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("price_catalog_id", "version", name="uq_price_catalog_version_catalog_version"),
        CheckConstraint(f"status IN {VERSION_STATUSES}", name="status_known"),
    )


class TypeBasePrice(UuidPk, Created, Base):
    """Basispreis-Spanne je Typ-Identität (nicht Version, Plan H1 3.7)."""

    __tablename__ = "type_base_price"

    price_catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_catalog_version.id", ondelete="CASCADE"), index=True
    )
    building_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("building_type.id", ondelete="CASCADE"), index=True
    )
    min_cents: Mapped[int] = mapped_column()
    max_cents: Mapped[int] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "price_catalog_version_id", "building_type_id", name="uq_type_base_price_catalog_type"
        ),
    )


class PackageTypePrice(UuidPk, Created, Base):
    """Linienaufpreis, hängt vom Typ ab (Spez. 4.3: Fassadenfläche, Fenster, Wohnfläche)."""

    __tablename__ = "package_type_price"

    price_catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_catalog_version.id", ondelete="CASCADE"), index=True
    )
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("package.id", ondelete="CASCADE"))
    building_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building_type.id", ondelete="CASCADE"))
    surcharge_cents: Mapped[int] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "price_catalog_version_id",
            "package_id",
            "building_type_id",
            name="uq_package_type_price_catalog_package_type",
        ),
    )


class ModuleTypePrice(UuidPk, Created, Base):
    """Optionsaufpreis je Typ (nur die Optionen, die für diesen Typ gelten, Plan H1 3.2)."""

    __tablename__ = "module_type_price"

    price_catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_catalog_version.id", ondelete="CASCADE"), index=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module.id", ondelete="CASCADE"))
    building_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building_type.id", ondelete="CASCADE"))
    surcharge_cents: Mapped[int] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "price_catalog_version_id",
            "module_id",
            "building_type_id",
            name="uq_module_type_price_catalog_module_type",
        ),
    )


class EnergyAssessment(UuidPk, Created, Base):
    """RE2020-Befund je Typ und Linie, zusammengefasst statt granular (Plan H1 3.8). Nicht versioniert:
    eine Korrektur ersetzt den Befund, ein echtes Gutachten (X3) ersetzt diese Tabelle."""

    __tablename__ = "energy_assessment"

    building_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("building_type.id", ondelete="CASCADE"), index=True
    )
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("package.id", ondelete="CASCADE"))
    climate_zone: Mapped[str] = mapped_column(String(10))
    verdict: Mapped[str] = mapped_column(Text)
    compliant: Mapped[bool] = mapped_column()
    compliance_surcharge_cents: Mapped[int | None] = mapped_column()
    measures: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("building_type_id", "package_id", name="uq_energy_assessment_type_package"),
    )


class PlanDocument(UuidPk, Created, Base):
    """Grundriss-PDF als reiner Upload, ohne automatische Auswertung (Plan H1 3.6)."""

    __tablename__ = "plan_document"

    building_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("building_type.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
