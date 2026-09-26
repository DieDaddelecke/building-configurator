"""Bindende Grundfläche je Zonen-Teilfläche und Auslegung (docs/PLAN_AN3_ANALYSE.md 3.1).

Drei Kandidaten: die Kontur des Baurahmens innerhalb der Teilfläche, der Anteil aus `max_footprint_ratio`
und die feste Obergrenze aus `max_area.footprint_m2`. Bindend ist das Minimum der ermittelten. Fehlt der
Anteil, bleibt der Wert eine Obergrenze – nie geschätzt (D11).
"""

from dataclasses import dataclass, field
from typing import Literal

from app.envelope.domain.derive import Contour, PartResult
from app.envelope.domain.inputs import Citation
from app.envelope.domain.setbacks import RuleIndex, rule_for

Source = Literal["contour", "ratio", "absolute"]
SOURCE_ORDER: tuple[Source, ...] = ("ratio", "absolute", "contour")
"""Bei gleichem Wert benennt die Ausgabe zuerst die Regel: Sie ist die rechtliche Grenze."""


@dataclass(frozen=True)
class Candidate:
    source: Source
    value_m2: float | None
    status: str
    """`effective`, `unknown`, `missing` oder `not_regulated` (Regel), bei der Kontur `effective`."""
    citation: Citation | None = None


@dataclass(frozen=True)
class Footprint:
    value_m2: float | None
    binding: Source | None
    complete: bool
    reasons: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def part_footprint(part: PartResult, contour: Contour, rules: RuleIndex, reading: str) -> Footprint:
    if part.excluded is not None:
        # Ohne Regeln trägt die Teilfläche nichts bei, ist aber auch nicht geklärt; GRZ 0 ist eine Aussage
        complete = part.excluded == "footprint_zero"
        return Footprint(
            value_m2=0.0,
            binding="ratio" if complete else None,
            complete=complete,
            reasons=[] if complete else [f"zone_{part.excluded}"],
        )
    inside = contour.geometry.intersection(part.geometry).area if not contour.geometry.is_empty else 0.0
    candidates = [Candidate("contour", round(float(inside), 2), "effective")]
    reasons: list[str] = []
    if reading == "strict" and not contour.complete:
        reasons.append("contour_incomplete")

    ratio_rule = rule_for(rules, "max_footprint_ratio")
    if ratio_rule is None:
        candidates.append(Candidate("ratio", None, "missing"))
        reasons.append("footprint_ratio_unknown")
    else:
        ratio = ratio_rule.params.get("ratio")
        known = (
            ratio_rule.status == "effective"
            and isinstance(ratio, int | float)
            and not isinstance(ratio, bool)
        )
        value = round(float(ratio) * part.area_m2, 2) if known and ratio is not None else None
        candidates.append(Candidate("ratio", value, ratio_rule.status, ratio_rule.citation))
        if ratio_rule.status in ("unknown", "missing") or (
            ratio_rule.status == "effective" and value is None
        ):
            reasons.append("footprint_ratio_unknown")

    area_rule = rule_for(rules, "max_area")
    if area_rule is not None and area_rule.status == "effective":
        absolute = area_rule.params.get("footprint_m2")
        if isinstance(absolute, int | float) and not isinstance(absolute, bool):
            candidates.append(
                Candidate("absolute", round(float(absolute), 2), "effective", area_rule.citation)
            )

    known_values = [
        (c.value_m2, SOURCE_ORDER.index(c.source), c) for c in candidates if c.value_m2 is not None
    ]
    best = min(known_values, key=lambda item: (item[0], item[1]))[2]
    return Footprint(
        value_m2=best.value_m2,
        binding=best.source,
        complete=not reasons,
        reasons=reasons,
        candidates=candidates,
    )
