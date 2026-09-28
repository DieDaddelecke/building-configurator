"""Eingaben des Baurahmens: was G1 und G2 liefern, als unveränderliche Datenklassen ohne Bezug zu
Datenbank oder API (Plan 3.2). Der Dienst bildet die Antworten der Module hierauf ab.
"""

from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class Citation:
    """Herkunft eines Werts (L3): Seite, Zitat, Prüfstatus, Verweis auf die Planunterlage."""

    page: int | None = None
    quote: str | None = None
    quote_verified: bool = False
    source_url: str | None = None
    origin: str = "extraction"
    confidence: float = 0.0
    notes: str | None = None
    document_id: str | None = None
    """Dokument der Fundstelle; die Analyse erkennt daran Übernahmen aus Zusatzdokumenten (AN4)."""


@dataclass(frozen=True)
class RuleInput:
    kind: str
    building_kind: str
    status: str
    """`effective`, `unknown`, `not_regulated` oder `text_only` (G2)."""
    reason: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    citation: Citation = field(default_factory=Citation)


@dataclass(frozen=True)
class ZoneInput:
    code: str
    label: str | None
    status: str
    """`simulated`, `office_reviewed`, `outdated`, `in_progress` oder `unavailable` (G2)."""
    reason: str | None
    area_m2: float
    share: float
    polygon: BaseGeometry
    """Teilfläche Grundstück × Zone in Lambert-93."""
    rules: list[RuleInput] = field(default_factory=list)
    hints: list[RuleInput] = field(default_factory=list)
    version_id: str | None = None


@dataclass(frozen=True)
class ConstraintInput:
    category: str
    """`prescription`, `information` oder `servitude` (GPU)."""
    type_code: str | None
    label: str
    endpoint: str
    geometry: BaseGeometry


@dataclass(frozen=True)
class EdgeInput:
    seq: int
    ring: int
    kind: str
    """`street`, `side`, `rear` oder `other` (G1)."""
    classification_source: str
    confidence: float
    length_m: float
    normal_azimuth_deg: float
    street_name: str | None
    geometry: BaseGeometry


@dataclass(frozen=True)
class TerrainInput:
    status: str
    slope_percent: float | None = None
    reference_altitude_ngf: float | None = None
    method: str | None = None


@dataclass(frozen=True)
class SiteInput:
    polygon: Polygon
    area_m2: float
    local_origin: tuple[float, float]
    edges: list[EdgeInput]
    main_street_seq: int | None = None
    warnings: list[str] = field(default_factory=list)
    customer_edges_unconfirmed: bool = False
    terrain: TerrainInput = field(default_factory=lambda: TerrainInput(status="pending"))
    parcels: list[str] = field(default_factory=list)
    revision: int = 1
    engine_version: str = ""


@dataclass(frozen=True)
class EnvelopeInput:
    site: SiteInput
    zones: list[ZoneInput] = field(default_factory=list)
    constraints: list[ConstraintInput] = field(default_factory=list)
    rules_status: str = "unavailable"
    """Gesamtstatus der Regeln (G2): `ok`, `partial`, `in_progress` oder `unavailable`."""
    rules_reason: str | None = None
    uncovered_share: float = 0.0
    warnings: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    rules_engine_version: str = ""
