"""Nutzfläche (surface de plancher, SDP) als Spanne (docs/PLAN_AN3_ANALYSE.md 3.3, PLAN_AN3_GABARIT.md 3.4).

Je Geschoss die bindende Grundfläche F, höchstens die Fläche der Gabarit-Kontur auf der Höhe seiner Oberkante;
das oberste Geschoss mit seinem anrechenbaren Anteil s; alles mal (1 − w) für den Außenwandabzug. Unten die
engste Auslegung und die ungünstigen Annahmen, oben die weiteste und die günstigen. Eine Obergrenze
`max_area.sdp_m2` begrenzt beide Enden. Kein Aufmaß: Was R.111-22 darüber hinaus abzieht, benennt
`NOT_COUNTED`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.analysis.domain.footprint import Footprint
from app.analysis.domain.parameters import Parameters
from app.analysis.domain.storeys import Storeys
from app.envelope.domain.inputs import Citation, RuleInput

NOT_COUNTED: tuple[str, ...] = (
    "stairs_lifts",
    "low_height",
    "parking",
    "attic_unusable",
    "technical_cellars",
    "collective_ten_percent",
    "embrasures",
)
"""Abzüge, die die Spanne nicht rechnet (Anzeige mit Erklärung): Treppen- und Aufzugsöffnungen, Flächen unter
1,80 m (nur über den Anteil des Dachgeschosses angenähert), Stellplätze und Rampen, nicht ausbaufähige
Dachräume, Technik- und Kellerräume, 10 % bei Sammelerschließung, Laibungen. Höhengrenze der Grenzbebauung und
höhenabhängige Abstände oberer Geschosse rechnet seit dem Gabarit jedes Geschoss selbst."""

AreaAt = Callable[[float, str], float]
"""Fläche der Gabarit-Kontur innerhalb der Teilfläche für eine Höhe und eine Auslegung."""


@dataclass(frozen=True)
class StoreyArea:
    level_m: float
    """Oberkante des Geschosses: Mit der Gabarit-Kontur dieser Höhe ist es gerechnet."""
    area_m2: float
    """`min(F, Fläche der Kontur)`, ohne Anteil und Wandabzug."""
    share: float
    """1 für ein Vollgeschoss, sonst der Anteil des obersten Geschosses."""


@dataclass(frozen=True)
class FloorArea:
    low_m2: float | None
    high_m2: float | None
    cap_m2: float | None = None
    capped: bool = False
    """Die Obergrenze `max_area.sdp_m2` ist kleiner als das obere Ende ohne sie."""
    complete: bool = False
    reasons: list[str] = field(default_factory=list)
    cap_citation: Citation | None = None
    storeys_low: list[StoreyArea] = field(default_factory=list)
    storeys_high: list[StoreyArea] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    """`gabarit_limits_storeys`: Der Gabarit macht das obere Ende kleiner als F × (n + s) × (1 − w)."""


def _top_share(storeys: Storeys, params: Parameters) -> tuple[float, float]:
    span = params.attique_share if storeys.top == "attique" else params.attic_share
    if storeys.top == "none":
        return 0.0, 0.0
    return (span.low if storeys.top_certain else 0.0), span.high


def _storeys(
    footprint: float,
    full: int,
    top_share: float,
    storey_height: float,
    storeys: Storeys,
    reading: str,
    area_at: AreaAt | None,
) -> list[tuple[float, float, float]]:
    """(Oberkante, Fläche, Anteil) je Geschoss: Vollgeschosse bei k · h, das Dachgeschoss auf der Höhe des
    Geschosses darunter, ein Attikageschoss eine Geschosshöhe höher (3.4)."""
    levels = [(k * storey_height, 1.0) for k in range(1, full + 1)]
    if top_share > 0:
        levels.append(((full if storeys.top == "attic" else full + 1) * storey_height, top_share))
    return [
        (level, min(footprint, area_at(level, reading)) if area_at is not None else footprint, share)
        for level, share in levels
    ]


def _sum(storeys: list[tuple[float, float, float]]) -> float:
    return sum(area * share for _level, area, share in storeys)


def _out(storeys: list[tuple[float, float, float]]) -> list[StoreyArea]:
    return [StoreyArea(round(level, 2), round(area, 2), share) for level, area, share in storeys]


def part_floor_area(
    strict: Footprint,
    lenient: Footprint,
    storeys: Storeys,
    area_rule: RuleInput | None,
    params: Parameters,
    area_at: AreaAt | None = None,
) -> FloorArea:
    """Spanne einer Teilfläche. Ohne `area_at` (kein Gabarit) wirkt je Geschoss nur die Grundfläche."""
    reasons = sorted({*strict.reasons, *lenient.reasons})
    if storeys.full_min is None or storeys.full_max is None:
        return FloorArea(None, None, reasons=sorted({*reasons, "height_unknown"}))
    if strict.value_m2 is None or lenient.value_m2 is None:
        return FloorArea(None, None, reasons=sorted({*reasons, "footprint_unknown"}))
    s_low, s_high = _top_share(storeys, params)
    wall, h = params.wall_share, params.storey_height_m
    below = _storeys(strict.value_m2, storeys.full_min, s_low, h.high, storeys, "strict", area_at)
    above = _storeys(lenient.value_m2, storeys.full_max, s_high, h.low, storeys, "lenient", area_at)
    low = _sum(below) * (1 - wall.high)
    high = _sum(above) * (1 - wall.low)
    unlimited = lenient.value_m2 * (storeys.full_max + s_high) * (1 - wall.low)
    notes = ["gabarit_limits_storeys"] if high < unlimited - 0.5 else []
    cap: float | None = None
    citation: Citation | None = None
    if area_rule is not None and area_rule.status == "effective":
        value = area_rule.params.get("sdp_m2")
        if isinstance(value, int | float) and not isinstance(value, bool):
            cap, citation = float(value), area_rule.citation
    capped = cap is not None and cap < high
    if cap is not None:
        low, high = min(low, cap), min(high, cap)
    return FloorArea(
        low_m2=round(low, 2),
        high_m2=round(high, 2),
        cap_m2=cap,
        capped=capped,
        complete=not reasons,
        reasons=reasons,
        cap_citation=citation,
        storeys_low=_out(below),
        storeys_high=_out(above),
        notes=notes,
    )
