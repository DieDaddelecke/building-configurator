"""Ausgaben der Baurahmen-API (Modul G3, Plan G3 4.3).

Jede Antwort trägt `simulation: true`: Der Baurahmen entsteht automatisch aus Kataster und ausgewerteten
Planunterlagen, ist unverbindlich und vom Büro nicht geprüft (D11, L7).

Koordinaten: `*_local` in Metern (Ost, Nord) relativ zu `local_origin`; `geojson` in WGS84.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.site.schemas import LocalOrigin, LocalRing

EnvelopeStatus = Literal["ok", "partial", "in_progress", "unavailable"]
Reading = Literal["lenient", "strict"]
LimitStatus = Literal["effective", "unknown", "not_regulated", "text_only", "missing"]


class CitationOut(BaseModel):
    """Herkunft eines Werts (L3): Seite und Zitat der Planunterlage, Prüfstatus, Link mit Seitensprung."""

    page: int | None = None
    quote: str | None = None
    quote_verified: bool
    source_url: str | None = None
    origin: Literal["extraction", "office", "project"]
    confidence: float
    notes: str | None = None
    from_scan: bool = False
    """Zitat von einer per Texterkennung gelesenen Seite (AN7, docs/PLAN_AN7_SCAN.md 3.3)."""


class LimitOut(BaseModel):
    key: str
    """Regelart (`max_height`) oder abgeleiteter Wert (`footprint_max_m2`, `unsealed_min_m2`)."""
    kind: str
    building_kind: str
    status: LimitStatus
    reason: str | None = None
    value: float | None = None
    params: dict[str, Any]
    citation: CitationOut | None = None
    derived_from: str | None = None


class HeightsOut(BaseModel):
    eave_m: float | None = None
    ridge_m: float | None = None
    parapet_m: float | None = None
    storeys: str | None = None
    reference: str
    measured_at: str
    assumptions: list[str]
    """Z. B. Standard-Geschosshöhe, wenn der Plan nur Geschosse nennt; wirkt nur auf die engste Kontur."""


class SetbackOut(BaseModel):
    zone_code: str
    kind: str
    building_kind: str
    status: LimitStatus
    reason: str | None = None
    lenient_m: float | None = None
    strict_m: float | None = None
    """`null` heißt: nicht ermittelt, es wird nichts abgezogen (die Fläche kann zu groß sein)."""
    params: dict[str, Any]
    citation: CitationOut | None = None
    markers: list[str]


class EnvelopeEdgeOut(BaseModel):
    seq: int
    ring: int
    kind: Literal["street", "side", "rear", "other"]
    classification_source: Literal["auto", "customer", "architect"]
    confidence: float
    length_m: float
    normal_azimuth_deg: float
    street_name: str | None = None
    coords_local: LocalRing
    lenient_m: float | None = None
    strict_m: float | None = None
    setbacks: list[SetbackOut]
    markers: list[str]
    """`setback_unknown`, `height_unknown`, `alignment`, `on_boundary_allowed`, `kind_unclear`,
    `classification_uncertain`, `customer_correction`."""


class ContourOut(BaseModel):
    rings_local: list[LocalRing]
    geojson: dict[str, Any] | None = None
    area_m2: float
    complete: bool
    incomplete_reasons: list[str]


class BandOut(BaseModel):
    """Bauband an einer Straßenkante (`setback_street` mit Band, Plan G3 3.3)."""

    edge_seq: int
    zone_code: str
    min_m: float
    max_m: float
    band: Literal["building", "facade"] | None = None
    limits_area: dict[str, bool]
    """Je Auslegung, ob das Band die Fläche begrenzt oder nur die Lage der Straßenfassade."""
    rings_local: list[LocalRing]


class PartOut(BaseModel):
    zone_code: str
    zone_status: str
    reason: str | None = None
    area_m2: float
    share: float
    rings_local: list[LocalRing]
    excluded: str | None = None
    """Gesetzt, wenn die Teilfläche nicht in den Konturen steckt (keine Regeln, Grundflächenzahl 0)."""
    limits: list[LimitOut]
    hints: list[LimitOut]
    heights: HeightsOut


class ConstraintOut(BaseModel):
    effect: Literal["no_build", "restricts", "info"]
    category: Literal["prescription", "information", "servitude"]
    type_code: str | None = None
    label: str
    endpoint: str
    area_m2: float
    rings_local: list[LocalRing]
    lines_local: list[LocalRing]


class ProvenanceOut(BaseModel):
    site_revision: int
    site_engine_version: str
    rules_engine_version: str
    plan_id: uuid.UUID | None = None
    plan_title: str | None = None
    rule_set_version_ids: list[uuid.UUID]
    project_overrides: int
    terrain_status: str
    terrain_slope_percent: float | None = None
    terrain_reference_altitude_ngf: float | None = None
    assumptions: list[str]


class EnvelopeOut(BaseModel):
    simulation: Literal[True] = True
    status: EnvelopeStatus
    reason: str | None = None
    engine_version: str
    input_hash: str
    """Prüfsumme über den **Inhalt** der Eingaben: Grundstück, Gelände, Regeln, Korrekturen, Vorgaben.
    Ändert sich etwas davon, ändert sich der Baurahmen und mit ihm der Steckbrief."""
    updated_at: datetime
    local_origin: LocalOrigin
    area_m2: float
    parcels: list[str]
    outline_local: list[LocalRing]
    contours: dict[Reading, ContourOut]
    parts: list[PartOut]
    edges: list[EnvelopeEdgeOut]
    bands: list[BandOut]
    constraints: list[ConstraintOut]
    warnings: list[str]
    notices: list[str]
    """Schlüssel der Hinweise nach L7 (`GET /legal/notices?key=`)."""
    provenance: ProvenanceOut


class SheetOut(BaseModel):
    """Steckbrief als PDF: fertig (`ready`) oder in Arbeit (`job_id`)."""

    status: Literal["ready", "pending"]
    input_hash: str
    job_id: uuid.UUID | None = None
    created_at: datetime | None = None
