"""Ein- und Ausgaben der Analyse-API (docs/PLAN_AN3_ANALYSE.md 3.9).

Jede Antwort trägt `simulation: true`: Die Kennzahlen entstehen automatisch aus Baurahmen und ausgewerteten
Planunterlagen, mit offengelegten Annahmen (D11, L7). Flächen in m², Anteile 0–1, Höhen in m.
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from app.analysis.domain.parameters import BOUNDS
from app.envelope.schemas import CitationOut, EnvelopeStatus, LimitOut, Reading
from app.rules.schemas import VersionOut
from app.site.schemas import LocalRing


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


class StoreyAreaOut(BaseModel):
    level_m: float
    """Oberkante des Geschosses; mit der Gabarit-Kontur dieser Höhe gerechnet."""
    area_m2: float
    """`min(Grundfläche, Kontur)`, ohne Anteil und Wandabzug."""
    share: float
    """1 für ein Vollgeschoss, sonst der Anteil des obersten Geschosses."""


class AnalysisFloorAreaOut(BaseModel):
    low_m2: float | None = None
    high_m2: float | None = None
    cap_m2: float | None = None
    capped: bool
    complete: bool
    reasons: list[str]
    cap_citation: CitationOut | None = None
    storeys_low: list[StoreyAreaOut]
    storeys_high: list[StoreyAreaOut]
    notes: list[str]
    """`gabarit_limits_storeys`: Der Gabarit macht das obere Ende kleiner."""


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
        "stricter",
        "looser",
        "equal",
        "mixed",
        "different",
        "only_supplement",
        "no_own_rule",
        "unknown",
        "adopted",
    ]
    """`adopted`: Die wirksame Regel ist eine Projektkorrektur mit Fundstelle in diesem Dokument (AN4 3.4)."""
    supplement: LimitOut
    plu: LimitOut | None = None
    """Wirksame Regel der verglichenen PLU-Zone – mit Projektkorrekturen."""
    details: dict[str, Literal["stricter", "looser", "equal", "different"]]
    proposal: dict[str, Any] | None = None
    """Parameter für die Übernahme als Projektkorrektur: das Strengere je Parameter (AN4 3.4)."""


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


class GabaritContourOut(BaseModel):
    rings_local: list[LocalRing]
    area_m2: float
    complete: bool
    reasons: list[str]


class GabaritLevelOut(BaseModel):
    """Stufe `(from_m, to_m]`: Baukörperteile, die bis `to_m` reichen, liegen in ihrer Kontur."""

    from_m: float
    to_m: float
    roof: bool
    """Über der Traufe: Dachzone, senkrecht bis zum First (E-AN3G-7)."""
    contours: dict[Reading, GabaritContourOut]


class GabaritHeightsOut(BaseModel):
    zone_code: str
    eave_m: float | None = None
    ridge_m: float | None = None
    parapet_m: float | None = None
    derived: bool
    """Aus einer Geschossangabe mit der Geschosshöhe der Annahmen umgerechnet."""


class GabaritOut(BaseModel):
    """Hüllkörper in Stufen (docs/PLAN_AN3_GABARIT.md 3.2); Höhen über der Bezugshöhe der Regeln."""

    status: Literal["ok", "partial", "unavailable"]
    reason: str | None = None
    top_m: float | None = None
    storey_height_m: float | None = None
    """Geschosshöhe, mit der eine reine Geschossangabe umgerechnet ist."""
    reasons: list[str]
    heights: list[GabaritHeightsOut]
    levels: list[GabaritLevelOut]
    terrain_status: str
    terrain_slope_percent: float | None = None


class SectionCrossingOut(BaseModel):
    s: float
    edge_seq: int | None = None
    kind: Literal["street", "side", "rear", "other"] | None = None
    inward: int
    """+1: Das Grundstück liegt bei größerem `s`, −1: bei kleinerem."""


class SectionLevelOut(BaseModel):
    from_m: float
    to_m: float
    roof: bool
    intervals: dict[Reading, list[list[float]]]
    """Abschnitte `[s0, s1]` der Kontur der Stufe auf der Schnittlinie."""


class SectionHeightLineOut(BaseModel):
    zone_code: str
    kind: Literal["eave", "ridge", "parapet"]
    height_m: float
    start: float
    end: float
    derived: bool


class SectionProspectOut(BaseModel):
    edge_seq: int
    reading: Reading
    points: list[list[float]]
    """`[s, Höhe]`: Grenze der zulässigen Bebauung an dieser Kante."""


class SectionOut(BaseModel):
    """Schnitt A–A (von der Hauptstraße nach hinten) oder B–B (rechtwinklig dazu), docs/PLAN_AN3_GABARIT.md
    3.3. `s` in Metern ab der ersten Grenze; Gelände eben auf ±0."""

    key: Literal["A", "B"]
    start_local: list[float]
    end_local: list[float]
    length_m: float
    parcel: list[list[float]]
    crossings: list[SectionCrossingOut]
    levels: list[SectionLevelOut]
    height_lines: list[SectionHeightLineOut]
    prospects: list[SectionProspectOut]


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
    gabarit: GabaritOut | None = None
    """Ohne Baurahmen `None`."""
    sections: list[SectionOut]


# ---------------------------------------------------------------------------
# Zwei Stände vergleichen (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5)
# ---------------------------------------------------------------------------

ComparisonKind = Literal["corrections", "versions"]
"""`corrections`: ohne ↔ mit den Korrekturen des Projekts. `versions`: frühere ↔ aktuelle Auswertung, beide
ohne Korrekturen, damit diese die Änderungen der Auswertung nicht überdecken (7.1 Nr. 5)."""


class ComparisonBaseOut(BaseModel):
    """Angebotener Vergleich; `base` ist der Wert für `?base=`."""

    base: str
    kind: ComparisonKind
    zone_code: str | None = None
    version: VersionOut | None = None


class ComparisonStateOut(BaseModel):
    corrections: bool
    """Mit den Korrekturen des Projekts gerechnet?"""
    version: VersionOut | None = None
    """Beim Versionsvergleich die Version der verglichenen Zone."""
    status: EnvelopeStatus
    reason: str | None = None


class ComparisonFigureOut(BaseModel):
    key: Literal[
        "footprint_lenient",
        "footprint_strict",
        "contour_lenient",
        "contour_strict",
        "storeys_min",
        "storeys_max",
        "floor_area_low",
        "floor_area_high",
        "height_top",
    ]
    unit: Literal["m2", "m", "count"]
    left: float | None = None
    right: float | None = None
    changed: bool


class ComparisonRuleOut(BaseModel):
    zone_code: str
    kind: str
    building_kind: str
    left: LimitOut | None = None
    right: LimitOut | None = None
    changed: bool
    """Status, Grund oder Parameter verschieden (Zahlen auf 1 cm genau)."""


class AnalysisComparisonOut(BaseModel):
    simulation: Literal[True] = True
    kind: ComparisonKind
    base: str
    left: ComparisonStateOut
    right: ComparisonStateOut
    bases: list[ComparisonBaseOut]
    """Alle Vergleiche, die das Projekt gerade anbietet (für die Auswahl)."""
    figures: list[ComparisonFigureOut]
    rules: list[ComparisonRuleOut]
