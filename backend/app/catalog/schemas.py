"""Ein- und Ausgaben der Katalogpflege (Modul H1, Plan H1 4.3). Nur für das Büro, kein Kundenschritt."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

VersionStatus = Literal["draft", "review", "published", "retired"]
RoofForm = Literal["gable", "hip", "flat", "complex"]


class ConsistencyFindingOut(BaseModel):
    code: str
    level: Literal["error", "warning"]
    detail: str


class RoomOut(BaseModel):
    name: str
    category: str
    storey: str
    area_m2: float


class TypeVersionOut(BaseModel):
    id: uuid.UUID
    building_type_id: uuid.UUID
    slug: str
    version: int
    status: VersionStatus
    name: str
    family: str | None
    storeys: str
    roof_form: RoofForm
    pitch_deg: float | None
    ridge_direction: str | None
    ridge_height_m: float
    eave_height_m: float
    footprint_facade: list[list[float]]
    footprint_facade_area_m2: float
    footprint_projection: list[list[float]]
    footprint_projection_area_m2: float
    living_area_m2: float
    rooms_text: str
    rooms: list[RoomOut]
    facade_roles: dict[str, str]
    entrance: dict[str, Any] | None
    garage_door: dict[str, Any] | None
    base_price_min_cents: int
    base_price_max_cents: int
    consistency_warnings: list[ConsistencyFindingOut]
    published_at: datetime | None
    created_at: datetime


class TypeVersionRefOut(BaseModel):
    """Kurzangabe je Version, damit die Katalogpflege auch Entwürfe und zurückgezogene Stände erreicht."""

    version: int
    status: VersionStatus
    name: str
    created_at: datetime
    published_at: datetime | None


class TypeSummaryOut(BaseModel):
    id: uuid.UUID
    slug: str
    family: str | None
    alternatives: list[str]
    current_version: TypeVersionOut | None
    versions: list[TypeVersionRefOut]
    """Alle Versionen, neueste zuerst."""


class FacadeRolesIn(BaseModel):
    roles: dict[str, Literal["street", "garden", "side_left", "side_right"]]
    """Kantenindex (als Text, `0`-basiert auf `footprint_facade`) → Rolle."""


class PlacementIn(BaseModel):
    entrance: dict[str, Any] | None = None
    garage_door: dict[str, Any] | None = None


class PlanDocumentOut(BaseModel):
    id: uuid.UUID
    building_type_id: uuid.UUID
    filename: str
    size_bytes: int
    created_at: datetime


class PackageVersionOut(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    slug: str
    version: int
    status: VersionStatus
    label_de: str
    label_fr: str
    scope: list[str]
    included_option_slugs: list[str]
    """Optionen, die diese Linie ohne Aufpreis enthält (Mockup `enthalten_in`, Plan H1 5 Schritt 4)."""
    published_at: datetime | None


class PackageIn(BaseModel):
    label_de: str
    label_fr: str
    scope: list[str] = []
    included_option_slugs: list[str] = []


class ModuleVersionOut(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    slug: str
    version: int
    status: VersionStatus
    label_de: str
    label_fr: str
    excludes_slugs: list[str]
    published_at: datetime | None


class ModuleIn(BaseModel):
    label_de: str
    label_fr: str
    excludes_slugs: list[str] = []


class TypeBasePriceOut(BaseModel):
    building_type_slug: str
    min_cents: int
    max_cents: int


class PackageTypePriceOut(BaseModel):
    package_slug: str
    building_type_slug: str
    surcharge_cents: int


class ModuleTypePriceOut(BaseModel):
    module_slug: str
    building_type_slug: str
    surcharge_cents: int


class EnergyAssessmentOut(BaseModel):
    building_type_slug: str
    package_slug: str
    climate_zone: str
    verdict: str
    compliant: bool
    compliance_surcharge_cents: int | None
    measures: str | None


class EnergyAssessmentIn(BaseModel):
    """Freitext-Befund je Typ und Linie (Plan H1 3.8): kein Gutachten, eine Simulation wie G2/G3."""

    climate_zone: str
    verdict: str
    compliant: bool
    compliance_surcharge_cents: int | None = None
    measures: str | None = None


class PriceCatalogVersionOut(BaseModel):
    id: uuid.UUID
    price_catalog_id: uuid.UUID
    region: str
    version: int
    status: VersionStatus
    valid_from: date
    vat_rate_default: float
    published_at: datetime | None
    base_prices: list[TypeBasePriceOut]
    package_prices: list[PackageTypePriceOut]
    module_prices: list[ModuleTypePriceOut]
    energy_assessments: list[EnergyAssessmentOut]
