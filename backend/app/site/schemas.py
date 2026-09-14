"""Ein- und Ausgaben der Grundstücks-API (Spez. 6.1, 6.3; Plan 3.3).

Koordinaten: `*_local` in Metern (Ost, Nord) relativ zu `local_origin` (Lambert-93); `*_geojson` in WGS84.
"""

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.site.domain.edges import EdgeKind

LocalRing = list[list[float]]
"""Ring in lokalen Metern: Liste von [Ost, Nord]."""
INSEE_PATTERN = r"^(?:\d{2}|2[AB])\d{3}$"
IDU = re.compile(r"^(?:\d{2}|2[AB])\d{3}\d{3}[0-9A-Z]{2}\d{4}$")
"""Gemeinde (5), Präfix (3), Sektion (2), Nummer (4)."""


class AddressOut(BaseModel):
    label: str
    kind: str
    lon: float
    lat: float
    citycode: str
    postcode: str | None
    city: str
    in_service_area: bool


class CommuneOut(BaseModel):
    insee: str
    name: str
    bbox: tuple[float, float, float, float]
    """WGS84: min_lon, min_lat, max_lon, max_lat."""
    release: str
    imported_at: datetime


class ParcelSummary(BaseModel):
    idu: str
    commune_insee: str
    prefix: str
    section: str
    number: str
    area_official_m2: int | None
    distance_m: float
    geometry_geojson: dict[str, Any]


class LookupIn(BaseModel):
    """Genau eine Angabe: Punkt in WGS84, Punkt in Lambert-93 (aus der Adresssuche) oder Parzellennummer."""

    lon: float | None = Field(default=None, ge=-5.5, le=10.0)
    lat: float | None = Field(default=None, ge=41.0, le=51.5)
    commune_insee: str | None = Field(default=None, pattern=INSEE_PATTERN)
    section: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,2}$")
    number: str | None = Field(default=None, pattern=r"^\d{1,4}$")

    @model_validator(mode="after")
    def _exactly_one(self) -> "LookupIn":
        point = self.lon is not None and self.lat is not None
        reference = self.commune_insee is not None and self.section is not None and self.number is not None
        partial_point = (self.lon is None) != (self.lat is None)
        if point == reference or partial_point:
            raise ValueError("lon+lat oder commune_insee+section+number angeben")
        return self


class LookupOut(BaseModel):
    in_service_area: bool
    contained_idu: str | None
    candidates: list[ParcelSummary]


class SiteIn(BaseModel):
    parcel_idus: list[str] = Field(min_length=1, max_length=10)

    @field_validator("parcel_idus")
    @classmethod
    def _valid(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip().upper() for v in value]
        if any(not IDU.match(v) for v in cleaned):
            raise ValueError("IDU mit 14 Zeichen erwartet")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Parzellen doppelt angegeben")
        return sorted(cleaned)


class CustomerEdgeIn(BaseModel):
    """Kunde: nur Straße oder Nachbar; `null` setzt auf die automatische Einordnung zurück."""

    kind: Literal["street", "neighbour"] | None


class ArchitectEdgeIn(BaseModel):
    kind: EdgeKind | None


class ParcelOut(BaseModel):
    idu: str
    commune_insee: str
    prefix: str
    section: str
    number: str
    area_official_m2: int | None
    area_geometric_m2: float
    release: str
    accuracy_class: str


class EdgeOut(BaseModel):
    seq: int
    ring: int
    kind: EdgeKind
    kind_auto: EdgeKind
    override_kind: str | None
    classification_source: Literal["auto", "customer", "architect"]
    confidence: float
    length_m: float
    normal_azimuth_deg: float
    adjacent: list[str]
    street_name: str | None
    """Name der Straße laut BD TOPO, wenn eine Achse die Straßenkante bestätigt."""
    road_share: float | None
    coords_local: LocalRing


class TerrainOut(BaseModel):
    status: Literal["pending", "ok", "unavailable"]
    method: str | None = None
    reference_altitude_ngf: float | None = None
    slope_percent: float | None = None
    flat: bool | None = None
    samples: int = 0


class RiskOut(BaseModel):
    kind: str
    level: Literal["low", "moderate", "high", "present", "unknown"]
    scope: Literal["address", "commune"]
    label: str


class RisksOut(BaseModel):
    status: Literal["pending", "ok", "unavailable"]
    items: list[RiskOut]


class ContextOut(BaseModel):
    """Umgebung für den Lageplan: Nachbarparzellen und Gebäude im Umkreis."""

    parcels: list[LocalRing]
    buildings: list[LocalRing]


class LocalOrigin(BaseModel):
    e: float
    n: float
    crs: Literal["EPSG:2154"] = "EPSG:2154"


class SiteOut(BaseModel):
    project_id: uuid.UUID
    revision: int
    engine_version: str
    updated_at: datetime
    area_m2: float
    area_official_m2: int | None
    local_origin: LocalOrigin
    outline_local: list[LocalRing]
    outline_geojson: dict[str, Any]
    parcels: list[ParcelOut]
    edges: list[EdgeOut]
    main_street_seq: int | None
    street_azimuth_deg: float | None
    garden_azimuth_deg: float | None
    binding: bool
    """False, solange Kundenkorrekturen an Kanten nicht vom Architekten bestätigt sind (Plan 3.3)."""
    warnings: list[str]
    notices: list[str]
    """Schlüssel der Hinweise nach L7 (`GET /legal/notices?key=`)."""
    terrain: TerrainOut
    risks: RisksOut
    context: ContextOut


class SiteReviewItem(BaseModel):
    project_id: uuid.UUID
    parcel_idus: list[str]
    revision: int
    warnings: list[str]
    customer_corrections: int
    updated_at: datetime


class ImportStatusOut(BaseModel):
    commune_insee: str
    status: str
    release: str | None
    counts: dict[str, int]
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ImportRequestIn(BaseModel):
    force: bool = False
