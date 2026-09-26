"""Nutzfläche (surface de plancher, SDP) als Spanne (docs/PLAN_AN3_ANALYSE.md 3.3).

SDP = F × (n + s) × (1 − w): F bindende Grundfläche, n Vollgeschosse, s anrechenbarer Anteil des obersten
Geschosses, w Außenwandabzug. Unten die engste Auslegung und die ungünstigen Annahmen, oben die weiteste
und die günstigen. Eine Obergrenze `max_area.sdp_m2` begrenzt beide Enden. Kein Aufmaß: Was R.111-22
darüber hinaus abzieht, benennt `NOT_COUNTED`.
"""

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
    "boundary_height",
    "upper_setbacks",
)
"""Abzüge und Grenzen, die die Spanne nicht rechnet (Anzeige mit Erklärung): Treppen- und Aufzugsöffnungen,
Flächen unter 1,80 m (nur über den Anteil des Dachgeschosses angenähert), Stellplätze und Rampen, nicht
ausbaufähige Dachräume, Technik- und Kellerräume, 10 % bei Sammelerschließung, Laibungen; Höhenbegrenzung
beim Bauen auf der Grenze und höhenabhängige Abstände oberer Geschosse (Gabarit, RA2)."""


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


def _top_share(storeys: Storeys, params: Parameters) -> tuple[float, float]:
    span = params.attique_share if storeys.top == "attique" else params.attic_share
    if storeys.top == "none":
        return 0.0, 0.0
    return (span.low if storeys.top_certain else 0.0), span.high


def part_floor_area(
    strict: Footprint, lenient: Footprint, storeys: Storeys, area_rule: RuleInput | None, params: Parameters
) -> FloorArea:
    reasons = sorted({*strict.reasons, *lenient.reasons})
    if storeys.full_min is None or storeys.full_max is None:
        return FloorArea(None, None, reasons=sorted({*reasons, "height_unknown"}))
    if strict.value_m2 is None or lenient.value_m2 is None:
        return FloorArea(None, None, reasons=sorted({*reasons, "footprint_unknown"}))
    s_low, s_high = _top_share(storeys, params)
    wall = params.wall_share
    low = strict.value_m2 * (storeys.full_min + s_low) * (1 - wall.high)
    high = lenient.value_m2 * (storeys.full_max + s_high) * (1 - wall.low)
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
    )
