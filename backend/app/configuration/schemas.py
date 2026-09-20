"""Ein- und Ausgaben der Konfigurations-API (Modul H2, Plan H2 4.3).

Jede Antwort ist eine Simulation (D11, L7): Die Prüfung beruht auf automatisch ausgewerteten Regeln.
Koordinaten sind lokale Meter (Ost, Nord) relativ zu `local_origin` des Grundstücks (Spez. 6.1).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.envelope.schemas import CitationOut
from app.site.schemas import LocalRing

CheckStatus = Literal["pass", "fail", "hint", "unknown", "not_applicable"]
Mode = Literal["rules", "free"]
PresetName = Literal["street_near", "set_back", "garden_max"]


class LocalPointModel(BaseModel):
    e: float
    n: float


class PlacementRequest(BaseModel):
    origin: LocalPointModel
    """Modellursprung des Hauses in lokalen Metern."""
    rotation_deg: float
    """Im Uhrzeigersinn; Modellnorden zeigt danach nach diesem Azimut. Nur die erlaubten Drehungen."""


class PlacementOut(BaseModel):
    origin: LocalPointModel
    rotation_deg: float


class ConfigurationPatch(BaseModel):
    """Teil-Update (JSON Merge Patch): nur gesendete Felder ändern sich, `null` löscht."""

    type_slug: str | None = None
    placement: PlacementRequest | None = None
    boundary_options: dict[int, bool] | None = None
    package_slug: str | None = None
    """Ausstattungslinie; `null` löscht sie (H3)."""
    option_slugs: list[str] | None = None
    """Vollständige Liste der ausdrücklich gewählten Optionen (H3); die der Linie kommen von selbst dazu."""


class CheckOut(BaseModel):
    code: str
    """Stabiler Schlüssel der Meldung (`setback_street`, `roof_form` …); die Oberfläche übersetzt ihn."""
    kind: str
    status: CheckStatus
    binding: bool
    """Nur eine bindende Prüfung sperrt (D12); sonst ist sie ein Hinweis."""
    measured: float | str | None = None
    limit: float | str | None = None
    unit: str | None = None
    edge_seq: int | None = None
    zone_code: str | None = None
    reason: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    citation: CitationOut | None = None


class EdgeMeasureOut(BaseModel):
    seq: int
    kind: str
    measured_m: float
    required_m: float | None
    contour: Literal["facade", "projection"]
    status: CheckStatus
    on_boundary: bool
    on_boundary_allowed: bool
    """Ob an dieser Kante Bauen auf der Grenze erlaubt ist (Schalter in der Oberfläche)."""
    markers: list[str]


class TypeFactsOut(BaseModel):
    """Kennwerte des Typs für die Karte (Steckbrief, Spez. 5.4.6)."""

    storeys: str
    roof_form: str
    pitch_deg: float | None
    ridge_direction: str | None
    ridge_height_m: float
    eave_height_m: float
    footprint_m2: float
    width_m: float
    depth_m: float
    living_area_m2: float
    rooms_text: str
    base_price_min_cents: int
    base_price_max_cents: int
    facade_local: LocalRing
    projection_local: LocalRing
    facade_roles: dict[str, str]
    """Kantenindex → Rolle; leer, solange das Büro sie nicht zugewiesen hat."""
    entrance: dict[str, Any] | None


class TypeFitOut(BaseModel):
    slug: str
    version: int
    name: str
    family: str | None
    allowed: bool
    reasons: list[CheckOut]
    """Alle bindenden Verstöße; leer, wenn der Typ wählbar ist."""
    hints: list[CheckOut]
    rotations: list[float]
    """Drehungen, für die es eine zulässige Lage gibt."""
    suggestions: list[str]
    """Slugs zulässiger Typen als Ersatz für einen gesperrten (Spez. 5.4.6)."""
    facts: TypeFactsOut


class TypesOut(BaseModel):
    simulation: bool = True
    mode: Mode
    free_reason: str | None
    notices: list[str]
    site_revision: int
    types: list[TypeFitOut]


class TypeRefOut(BaseModel):
    slug: str
    version: int
    name: str
    retired: bool = False


class PlacementEvaluationOut(BaseModel):
    valid: bool
    checks: list[CheckOut]
    edges: list[EdgeMeasureOut]
    facade_local: LocalRing
    projection_local: LocalRing
    zone_code: str | None


# ---------------------------------------------------------------------------
# H3: Linie, Optionen, Nebenbauten, Flächen, Kosten (Plan H3 4.3)
# ---------------------------------------------------------------------------

OptionState = Literal["selected", "included", "available", "blocked"]


class SelectionReasonOut(BaseModel):
    code: str
    """`catalog_unavailable`, `unknown_package`, `unknown_option`, `not_offered`, `excluded_by`."""
    slug: str | None = None
    other: str | None = None


class SelectionOut(BaseModel):
    package_slug: str | None
    package_version: int | None
    option_slugs: list[str]
    """Ausdrücklich gewählte Optionen."""
    included_slugs: list[str]
    """Optionen, die die gewählte Linie ohne Aufpreis enthält."""
    invalid: list[SelectionReasonOut]
    dropped: list[str]
    """Nur in der Antwort auf `PATCH`: Linie und Optionen, die für den neuen Typ nicht gelten."""


class PriceOut(BaseModel):
    """Preis einer Linie oder Option in Cent, brutto (Anzeigebasis, D10). Kein Gesamtpreis (L1)."""

    basis: Literal["fixed", "per_m2"]
    min_cents: int
    max_cents: int
    unit_price_cents: int | None = None
    quantity: float | None = None


class EnergyStatusOut(BaseModel):
    status: Literal["compliant", "action", "not_assessed"]
    climate_zone: str | None
    verdict: str | None
    measures: str | None
    surcharge_cents: int | None


class PackageChoiceOut(BaseModel):
    slug: str
    version: int
    label_de: str
    label_fr: str
    scope: list[str]
    included_option_slugs: list[str]
    price: PriceOut
    selected: bool
    retired: bool
    energy: EnergyStatusOut


class OptionChoiceOut(BaseModel):
    slug: str
    version: int
    kind: Literal["plain", "terrace", "carport"]
    label_de: str
    label_fr: str
    excludes: list[str]
    state: OptionState
    price: PriceOut | None
    """`None` bei einer in der Linie enthaltenen Option ohne Preiszeile."""
    reasons: list[SelectionReasonOut]
    checks: list[CheckOut]
    """Bindende Verstöße, die diese Option zur Auswahl hinzufügen würde (Zustand `blocked`)."""
    area_m2: float | None = None
    """Fläche einer Terrasse oder eines Carports; hängt nur vom Typ ab."""


class OptionsOut(BaseModel):
    simulation: bool = True
    type_slug: str | None
    catalog_available: bool
    vat_rate: float
    display_basis: Literal["gross"] = "gross"
    packages: list[PackageChoiceOut]
    options: list[OptionChoiceOut]


class OutbuildingOut(BaseModel):
    slug: str
    kind: Literal["terrace", "carport"]
    placed: bool
    polygon_local: LocalRing | None
    area_m2: float
    width_m: float | None
    depth_m: float
    spaces: int | None = None
    setback: Literal["known", "assumed", "relaxed"] | None = None
    """Nur Carport: woher die Abstände kommen (Plan H3 3.4)."""


class DrivewayOut(BaseModel):
    source: Literal["carport", "garage"]
    polygon_local: LocalRing | None
    length_m: float
    area_m2: float


class OutbuildingsOut(BaseModel):
    terrace: OutbuildingOut | None
    carport: OutbuildingOut | None
    driveways: list[DrivewayOut]


class PartAreasOut(BaseModel):
    zone_code: str
    area_m2: float
    emprise_m2: float
    sealed_m2: float
    unsealed_m2: float


class AreasOut(BaseModel):
    site_m2: float
    house_m2: float
    carport_m2: float
    terrace_m2: float
    driveway_m2: float
    paths_m2: float
    emprise_m2: float
    sealed_m2: float
    unsealed_m2: float
    parts: list[PartAreasOut]


class ComplianceOut(BaseModel):
    checks: list[CheckOut]
    fail: int
    hint: int
    unknown: int
    passed: int


class RangeOut(BaseModel):
    min_cents: int
    max_cents: int


class CostItemOut(BaseModel):
    code: str
    kind: Literal["base", "package", "option", "energy"]
    slug: str | None
    label_de: str | None
    label_fr: str | None
    min_cents: int
    max_cents: int
    included: bool
    quantity: float | None
    unit: str | None
    unit_price_cents: int | None
    source: str | None


class CostsOut(BaseModel):
    """Kostenkorridor (Spez. 5.6.5): nur Spannen, kein Feld, das als Gesamtpreis lesbar ist (L1)."""

    available: bool
    reason: str | None
    net: RangeOut | None
    gross: RangeOut | None
    vat_rate: float
    display_basis: Literal["gross"] = "gross"
    display: RangeOut | None
    """Brutto auf 1.000 € gerundet; nur damit zeigt die Oberfläche („ca. X – Y €“)."""
    catalog_version: int | None
    items: list[CostItemOut]


class OrientationOut(BaseModel):
    convergence_deg: float
    """Meridiankonvergenz von Lambert-93 am Grundstück; wahr = Gitter + Konvergenz."""
    facades: dict[str, float]
    """Rolle → wahrer Azimut der Außennormalen in Grad (0° = Norden, im Uhrzeigersinn)."""


class ConfigurationOut(BaseModel):
    simulation: bool = True
    project_id: uuid.UUID
    revision: int
    """0, solange noch nichts gespeichert ist."""
    engine_version: str
    mode: Mode
    free_reason: str | None
    type: TypeRefOut | None
    placement: PlacementOut | None
    boundary_options: dict[str, bool]
    rotations: list[float]
    """Erlaubte Drehungen für den gewählten Typ."""
    fit: TypeFitOut | None
    evaluation: PlacementEvaluationOut | None
    notices: list[str]
    updated_at: datetime | None
    selection: SelectionOut | None
    """Linie und Optionen (H3)."""
    outbuildings: OutbuildingsOut | None
    areas: AreasOut | None
    compliance: ComplianceOut | None
    energy: EnergyStatusOut | None
    costs: CostsOut | None
    orientation: OrientationOut | None
    review_stamp: str | None
    """Prüfstempel der angezeigten Auswertung (V 3.3); die Übergabe schickt ihn zurück. `null` ohne Typ."""


class RotationAreaOut(BaseModel):
    rotation_deg: float
    rings_local: list[LocalRing]
    """Fläche zulässiger Ursprünge; leer, wenn es für diese Drehung keine Lage gibt."""
    area_m2: float


class PlacementAreaOut(BaseModel):
    type_slug: str
    rotations: list[RotationAreaOut]


class PresetsOut(BaseModel):
    type_slug: str
    presets: dict[PresetName, PlacementOut | None]
    """`None`, wenn es keine zulässige Lage gibt."""
