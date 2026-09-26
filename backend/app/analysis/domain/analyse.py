"""Analyse für den Entwurf: Kennzahlen je Zonen-Teilfläche und gesamt, Vergleich der Zusatzdokumente
(docs/PLAN_AN3_ANALYSE.md 3). Rein und deterministisch wie `derive_envelope`, auf dessen Ergebnis sie baut.
"""

import math
from dataclasses import dataclass, field

from app.analysis.domain.compare import Comparison, compare, stricter_kinds
from app.analysis.domain.floor_area import FloorArea, part_floor_area
from app.analysis.domain.footprint import Footprint, part_footprint
from app.analysis.domain.parameters import Parameters
from app.analysis.domain.storeys import Storeys, storeys_for
from app.envelope.domain.derive import READINGS, ZONE_WITHOUT_RULES, Envelope
from app.envelope.domain.inputs import EnvelopeInput, RuleInput
from app.envelope.domain.setbacks import index_rules, rule_for

RESULT_STATUSES = ("simulated", "office_reviewed", "outdated")


@dataclass(frozen=True)
class SupplementInput:
    """Regeln eines Zusatzdokuments für das gewählte Lot (aus `rules.service.supplement_rules`)."""

    document_id: str
    title: str
    du_type: str
    lot: str | None
    status: str
    reason: str | None
    rules: list[RuleInput] = field(default_factory=list)
    hints: list[RuleInput] = field(default_factory=list)
    updating: bool = False


@dataclass(frozen=True)
class SupplementResult:
    source: SupplementInput
    comparisons: list[Comparison]


@dataclass(frozen=True)
class PartAnalysis:
    zone_code: str
    area_m2: float
    excluded: str | None
    footprint: dict[str, Footprint]
    storeys: Storeys
    floor_area: FloorArea


@dataclass(frozen=True)
class FootprintTotal:
    value_m2: float
    complete: bool


@dataclass(frozen=True)
class FloorAreaTotal:
    low_m2: int | None
    high_m2: int | None
    complete: bool
    capped: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Analysis:
    status: str
    """Wie der Baurahmen: `ok`, `partial`, `in_progress`, `unavailable`; ohne Baurahmen keine Kennzahlen."""
    reason: str | None
    parts: list[PartAnalysis]
    footprint: dict[str, FootprintTotal]
    floor_area: FloorAreaTotal | None
    supplements: list[SupplementResult]
    supplement_stricter: list[str]
    """Arten der Kennzahlen, bei denen ein Zusatzdokument strenger ist – in den Werten nicht verrechnet."""
    warnings: list[str]


def round_m2(value: float) -> int:
    """Auf ganze m², halbe aufgerundet; `round` rundete 379,5 je nach Gleitkommafehler auf 379."""
    return math.floor(round(value, 6) + 0.5)


def _no_storeys() -> Storeys:
    return Storeys(None, None, "none", False, "unknown", "missing")


def _plu_rules(data: EnvelopeInput) -> list[RuleInput]:
    """Regeln der größten Zone mit Regeln; die Zonen kommen nach Fläche sortiert (G2)."""
    for zone in data.zones:
        if zone.status not in ZONE_WITHOUT_RULES:
            return [*zone.rules, *zone.hints]
    return []


def analyse(
    data: EnvelopeInput, envelope: Envelope | None, params: Parameters, supplements: list[SupplementInput]
) -> Analysis:
    plu = _plu_rules(data)
    results = [
        SupplementResult(s, compare(s.rules, plu) if s.status in RESULT_STATUSES else []) for s in supplements
    ]
    stricter = sorted({kind for result in results for kind in stricter_kinds(result.comparisons)})
    warnings = ["supplement_stricter"] if stricter else []
    if len(data.zones) > 1 and supplements:
        warnings.append("supplement_compared_with_largest_zone")
    if envelope is None or envelope.status in ZONE_WITHOUT_RULES:
        return Analysis(
            status=envelope.status if envelope is not None else "unavailable",
            reason=envelope.reason if envelope is not None else data.rules_reason,
            parts=[],
            footprint={},
            floor_area=None,
            supplements=results,
            supplement_stricter=stricter,
            warnings=warnings,
        )

    zones = {zone.code: zone for zone in data.zones}
    parts: list[PartAnalysis] = []
    for part in envelope.parts:
        rules = index_rules(zones[part.zone_code].rules) if part.zone_code in zones else {}
        footprint = {
            reading: part_footprint(part, envelope.contours[reading], rules, reading) for reading in READINGS
        }
        if part.excluded is not None:
            storeys = _no_storeys()
            lenient = footprint["lenient"]
            floor = FloorArea(0.0, 0.0, complete=lenient.complete, reasons=list(lenient.reasons))
        else:
            storeys = storeys_for(rule_for(rules, "max_height"), params)
            floor = part_floor_area(
                footprint["strict"], footprint["lenient"], storeys, rule_for(rules, "max_area"), params
            )
        parts.append(
            PartAnalysis(
                zone_code=part.zone_code,
                area_m2=part.area_m2,
                excluded=part.excluded,
                footprint=footprint,
                storeys=storeys,
                floor_area=floor,
            )
        )

    totals = {
        reading: FootprintTotal(
            value_m2=round(sum(p.footprint[reading].value_m2 or 0.0 for p in parts), 2),
            complete=all(p.footprint[reading].complete for p in parts),
        )
        for reading in READINGS
    }
    return Analysis(
        status=envelope.status,
        reason=envelope.reason,
        parts=parts,
        footprint=totals,
        floor_area=_floor_total(parts),
        supplements=results,
        supplement_stricter=stricter,
        warnings=warnings,
    )


def _floor_total(parts: list[PartAnalysis]) -> FloorAreaTotal:
    reasons = sorted({reason for p in parts for reason in p.floor_area.reasons})
    lows = [p.floor_area.low_m2 for p in parts]
    highs = [p.floor_area.high_m2 for p in parts]
    if not parts or any(v is None for v in lows) or any(v is None for v in highs):
        return FloorAreaTotal(None, None, complete=False, capped=False, reasons=reasons)
    return FloorAreaTotal(
        low_m2=round_m2(sum(v for v in lows if v is not None)),
        high_m2=round_m2(sum(v for v in highs if v is not None)),
        complete=all(p.floor_area.complete for p in parts),
        capped=any(p.floor_area.capped for p in parts),
        reasons=reasons,
    )
