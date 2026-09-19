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
