"""Ein- und Ausgaben der Analyse-API (docs/PLAN_AN3_ANALYSE.md 3.9).

Jede Antwort trägt `simulation: true`: Die Kennzahlen entstehen automatisch aus Baurahmen und ausgewerteten
Planunterlagen, mit offengelegten Annahmen (D11, L7). Flächen in m², Anteile 0–1, Höhen in m.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, model_validator

from app.analysis.domain.parameters import BOUNDS
from app.envelope.schemas import CitationOut, EnvelopeStatus, LimitOut, Reading


class SpanIn(BaseModel):
    low: float
    high: float


class AnalysisParametersIn(BaseModel):
    """Annahmen eines Projekts; jede als Bereich. Grenzen in `analysis.domain.parameters.BOUNDS`."""

    storey_height_m: SpanIn
    wall_share: SpanIn
    attic_share: SpanIn
    attique_share: SpanIn

    @model_validator(mode="after")
    def _within_bounds(self) -> "AnalysisParametersIn":
        for name, (lowest, highest) in BOUNDS.items():
            span: SpanIn = getattr(self, name)
            if span.low > span.high:
                raise ValueError(f"{name}: low über high")
            if span.low < lowest or span.high > highest:
                raise ValueError(f"{name}: außerhalb {lowest}–{highest}")
        return self


class SpanOut(BaseModel):
    low: float
    high: float


class AnalysisParametersOut(BaseModel):
    storey_height_m: SpanOut
    wall_share: SpanOut
    attic_share: SpanOut
    attique_share: SpanOut


class AnalysisAssumptionsOut(BaseModel):
    values: AnalysisParametersOut
    """Benutzte Annahmen."""
    defaults: AnalysisParametersOut
    custom: bool
    """Der Architekt hat die Annahmen dieses Projekts geändert."""


class FootprintCandidateOut(BaseModel):
    source: Literal["contour", "ratio", "absolute"]
    value_m2: float | None = None
    status: str
    citation: CitationOut | None = None


class AnalysisFootprintOut(BaseModel):
    value_m2: float | None = None
    binding: Literal["contour", "ratio", "absolute"] | None = None
    complete: bool
    """`false`: Der Wert ist eine Obergrenze, z. B. weil die Grundflächenzahl nicht ermittelt ist."""
    reasons: list[str]
    candidates: list[FootprintCandidateOut]


class AnalysisStoreysOut(BaseModel):
    full_min: int | None = None
    full_max: int | None = None
    top: Literal["none", "attic", "attique"]
    top_certain: bool
    source: Literal["storeys", "eave", "parapet", "ridge", "unknown"]
    status: str
    citation: CitationOut | None = None
    notes: list[str]


class AnalysisFloorAreaOut(BaseModel):
    low_m2: float | None = None
    high_m2: float | None = None
    cap_m2: float | None = None
    capped: bool
    complete: bool
    reasons: list[str]
    cap_citation: CitationOut | None = None


class AnalysisPartOut(BaseModel):
    zone_code: str
    area_m2: float
    excluded: str | None = None
    footprint: dict[Reading, AnalysisFootprintOut]
    storeys: AnalysisStoreysOut
    floor_area: AnalysisFloorAreaOut


class FootprintTotalOut(BaseModel):
    value_m2: float
    complete: bool


class FloorAreaTotalOut(BaseModel):
    low_m2: int | None = None
    high_m2: int | None = None
    complete: bool
    capped: bool
    reasons: list[str]


class RuleComparisonOut(BaseModel):
    kind: str
    building_kind: str
    verdict: Literal[
        "stricter", "looser", "equal", "mixed", "different", "only_supplement", "no_own_rule", "unknown"
    ]
    supplement: LimitOut
    plu: LimitOut | None = None
    details: dict[str, Literal["stricter", "looser", "equal", "different"]]


class SupplementAnalysisOut(BaseModel):
    document_id: uuid.UUID
    title: str
    du_type: str
    lot: str | None = None
    status: str
    reason: str | None = None
    updating: bool
    comparisons: list[RuleComparisonOut]
    hints: list[LimitOut]


class AnalysisOut(BaseModel):
    simulation: Literal[True] = True
    status: EnvelopeStatus
    reason: str | None = None
    engine_version: str
    input_hash: str
    """Prüfsumme über Baurahmen-Eingaben, Annahmen und Regelstände der Zusatzdokumente (für AN5)."""
    assumptions: AnalysisAssumptionsOut
    footprint: dict[Reading, FootprintTotalOut]
    floor_area: FloorAreaTotalOut | None = None
    parts: list[AnalysisPartOut]
    not_counted: list[str]
    """Was die Nutzfläche nicht abzieht oder begrenzt (R.111-22, Gabarit) – Anzeige als Liste."""
    supplements: list[SupplementAnalysisOut]
    supplement_stricter: list[str]
    warnings: list[str]
