"""Tabellen des Moduls G1 (Plan 3.3, Spez. 4.2).

`ref_*`: Kataster-Massendaten des Einzugsgebiets in Lambert-93, je Gemeinde ersetzt.
`site`, `parcel`, `site_edge`, `terrain`, `site_risk`: Projektdaten; `parcel` ist eine Kopie zum
Zeitpunkt der Auswahl, damit spätere Importe bestätigte Grundstücke nicht verändern.
"""

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk

L93 = 2154


def _geom(kind: str) -> Geometry:
    # Räumliche Indizes stehen ausdrücklich in __table_args__, damit Alembic sie vergleicht
    return Geometry(kind, srid=L93, spatial_index=False)


# ---------------------------------------------------------------------------
# Referenzdaten
# ---------------------------------------------------------------------------


class RefImport(UuidPk, Created, Base):
    """Protokoll je Import: Quelle, Stand, Prüfsumme, Anzahl (Plan 3.3)."""

    __tablename__ = "ref_import"

    source: Mapped[str] = mapped_column(String(40))
    commune_insee: Mapped[str] = mapped_column(String(5))
    release: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'running'"))
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    sha256: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('running','succeeded','failed','skipped')", name="status_known"),
        Index("ix_ref_import_commune", "commune_insee", "created_at"),
    )


class RefCommune(Base):
    __tablename__ = "ref_commune"

    insee: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))
    release: Mapped[str] = mapped_column(String(20))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_ref_commune_geometry", "geometry", postgresql_using="gist"),)


class RefParcel(Base):
    __tablename__ = "ref_parcel"

    idu: Mapped[str] = mapped_column(String(14), primary_key=True)
    commune_insee: Mapped[str] = mapped_column(String(5), index=True)
    prefix: Mapped[str] = mapped_column(String(3))
    section: Mapped[str] = mapped_column(String(2))
    number: Mapped[str] = mapped_column(String(4))
    area_official_m2: Mapped[int | None] = mapped_column(Integer)
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))
    source_updated: Mapped[date | None] = mapped_column(Date)
    release: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        Index("ix_ref_parcel_geometry", "geometry", postgresql_using="gist"),
        Index("ix_ref_parcel_section_number", "commune_insee", "section", "number"),
    )


class RefBuilding(Base):
    __tablename__ = "ref_building"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    commune_insee: Mapped[str] = mapped_column(String(5), index=True)
    kind: Mapped[str | None] = mapped_column(String(2))
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))

    __table_args__ = (Index("ix_ref_building_geometry", "geometry", postgresql_using="gist"),)


class RefRoad(Base):
    """Straßenachsen der BD TOPO je Gemeinde; bestätigen Straßenkanten (Spez. 5.1.4 Schritt 2)."""

    __tablename__ = "ref_road"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    commune_insee: Mapped[str] = mapped_column(String(5), index=True)
    cleabs: Mapped[str] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column(String(200))
    nature: Mapped[str] = mapped_column(String(60))
    private: Mapped[bool] = mapped_column(Boolean)
    width_m: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[Any] = mapped_column(_geom("LINESTRING"))

    __table_args__ = (Index("ix_ref_road_geometry", "geometry", postgresql_using="gist"),)


class RefParcelStaging(Base):
    """Zwischenablage eines Imports; nach der Plausibilitätsprüfung in `ref_parcel` getauscht."""

    __tablename__ = "ref_parcel_staging"

    import_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    idu: Mapped[str] = mapped_column(String(14), primary_key=True)
    commune_insee: Mapped[str] = mapped_column(String(5))
    prefix: Mapped[str] = mapped_column(String(3))
    section: Mapped[str] = mapped_column(String(2))
    number: Mapped[str] = mapped_column(String(4))
    area_official_m2: Mapped[int | None] = mapped_column(Integer)
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))
    source_updated: Mapped[date | None] = mapped_column(Date)
    valid_source: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = ({"prefixes": ("UNLOGGED",)},)


class RefBuildingStaging(Base):
    __tablename__ = "ref_building_staging"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    import_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    commune_insee: Mapped[str] = mapped_column(String(5))
    kind: Mapped[str | None] = mapped_column(String(2))
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))

    __table_args__ = ({"prefixes": ("UNLOGGED",)},)


class GeocodeCache(Base):
    """Antworten der Adresssuche. Schlüssel ist ein HMAC der Eingabe, nicht die Eingabe selbst."""

    __tablename__ = "geocode_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Projektdaten
# ---------------------------------------------------------------------------

ENRICH_STATUS = "IN ('pending','ok','unavailable')"


class Site(UuidPk, Created, Base):
    __tablename__ = "site"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), unique=True)
    origin: Mapped[str] = mapped_column(String(20), server_default=text("'parcel'"))
    address_label: Mapped[str | None] = mapped_column(String(200))
    geometry: Mapped[Any] = mapped_column(_geom("POLYGON"))
    area_m2: Mapped[float] = mapped_column(Float)
    area_official_m2: Mapped[int | None] = mapped_column(Integer)
    local_origin_e: Mapped[float] = mapped_column(Float)
    local_origin_n: Mapped[float] = mapped_column(Float)
    parcel_idus: Mapped[list[str]] = mapped_column(ARRAY(String(14)))
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    outline_hash: Mapped[str] = mapped_column(String(64))
    main_street_seq: Mapped[int | None] = mapped_column(Integer)
    street_azimuth_deg: Mapped[float | None] = mapped_column(Float)
    garden_azimuth_deg: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
    neighbour_coverage: Mapped[str] = mapped_column(String(10))
    road_data: Mapped[bool] = mapped_column(Boolean)
    terrain_status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    risks_status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    engine_version: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(f"terrain_status {ENRICH_STATUS}", name="terrain_status_known"),
        CheckConstraint(f"risks_status {ENRICH_STATUS}", name="risks_status_known"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "neighbour_coverage IN ('complete','partial','none')", name="neighbour_coverage_known"
        ),
        CheckConstraint("origin IN ('parcel','manual_sketch')", name="origin_known"),
    )


class SiteParcel(UuidPk, Created, Base):
    """Kopie der Parzelle zum Zeitpunkt der Auswahl (Spez. 4.2 `parcel`)."""

    __tablename__ = "parcel"

    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), index=True)
    idu: Mapped[str] = mapped_column(String(14))
    commune_insee: Mapped[str] = mapped_column(String(5))
    prefix: Mapped[str] = mapped_column(String(3))
    section: Mapped[str] = mapped_column(String(2))
    number: Mapped[str] = mapped_column(String(4))
    geometry: Mapped[Any] = mapped_column(_geom("MULTIPOLYGON"))
    area_official_m2: Mapped[int | None] = mapped_column(Integer)
    area_geometric_m2: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    release: Mapped[str] = mapped_column(String(20))
    accuracy_class: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        UniqueConstraint("site_id", "idu", name="uq_parcel_site_idu"),
        CheckConstraint(
            "accuracy_class IN ('cadastre_vector','upload_vector','pdf_trace')", name="accuracy_class_known"
        ),
    )


EDGE_KINDS = "('street','side','rear','other')"


class SiteEdge(UuidPk, Created, Base):
    __tablename__ = "site_edge"

    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ring: Mapped[int] = mapped_column(Integer)
    geometry: Mapped[Any] = mapped_column(_geom("LINESTRING"))
    length_m: Mapped[float] = mapped_column(Float)
    normal_azimuth_deg: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(10))
    kind_auto: Mapped[str] = mapped_column(String(10))
    override_kind: Mapped[str | None] = mapped_column(String(12))
    classification_source: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    neighbour_share: Mapped[float] = mapped_column(Float)
    street_candidate: Mapped[str] = mapped_column(String(15))
    probe_in_parcel: Mapped[bool] = mapped_column(Boolean)
    road_share: Mapped[float | None] = mapped_column(Float)
    street_name: Mapped[str | None] = mapped_column(String(200))
    adjacent: Mapped[list[str]] = mapped_column(ARRAY(String(14)), server_default=text("'{}'"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("site_id", "seq", name="uq_site_edge_site_seq"),
        CheckConstraint(f"kind IN {EDGE_KINDS}", name="kind_known"),
        CheckConstraint(f"kind_auto IN {EDGE_KINDS}", name="kind_auto_known"),
        CheckConstraint(
            "override_kind IS NULL OR override_kind IN ('street','not_street','side','rear','other')",
            name="override_kind_known",
        ),
        CheckConstraint(
            "classification_source IN ('auto','customer','architect')", name="classification_source_known"
        ),
        CheckConstraint(
            "(override_kind IS NULL) = (classification_source = 'auto')", name="override_matches_source"
        ),
    )


class Terrain(UuidPk, Created, Base):
    __tablename__ = "terrain"

    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), unique=True)
    method: Mapped[str] = mapped_column(String(30))
    reference_altitude_ngf: Mapped[float] = mapped_column(Float)
    slope_percent: Mapped[float] = mapped_column(Float)
    samples: Mapped[list[list[float]]] = mapped_column(JSONB)
    outline_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("method IN ('ign_altimetry','survey_upload','flat_assumption')", name="method_known"),
    )


class SiteRisk(UuidPk, Created, Base):
    __tablename__ = "site_risk"

    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(10))
    label: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(40))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("site_id", "kind", name="uq_site_risk_site_kind"),
        CheckConstraint("level IN ('low','moderate','high','present','unknown')", name="level_known"),
        CheckConstraint("scope IN ('address','commune')", name="scope_known"),
    )
