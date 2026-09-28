"""Abstand je Grundstückskante in beiden Auslegungen (Spez. 5.3.2, 5.3.4; Plan G3 3.1, 3.2).

`lenient` ist die günstigste, `strict` die strengste Lesart derselben Regel. Ist ein Abstand nicht
ermittelt, wird nichts abgezogen und die Kante markiert: Die Fläche kann dann zu groß sein, das steht als
Hinweis daran (Plan 3.5). Nie wird ein Wert geschätzt (D11).
"""

from dataclasses import dataclass, field
from typing import Any

from app.envelope.domain.heights import Heights
from app.envelope.domain.inputs import Citation, EdgeInput, RuleInput

KIND_BY_EDGE: dict[str, tuple[str, ...]] = {
    "street": ("setback_street",),
    "side": ("setback_side",),
    "rear": ("setback_rear",),
    "other": ("setback_side", "setback_rear"),
}
"""Kante `other` (Rand eines Lochs, Grundstück ohne Hauptstraße) ist eine *limite séparative* ohne
Einordnung: Beide Regeln kommen in Betracht, die günstigere gilt weit, die strengere eng ausgelegt."""

RuleIndex = dict[tuple[str, str], RuleInput]

HEIGHT_EPSILON_M = 1e-6
"""Vergleich einer Stufenhöhe mit `on_boundary_max_height_m`: nur Gleitkommafehler, denn schon 1 mm darüber
darf der Baukörper nicht mehr auf der Grenze stehen (die Abstandslinie im Schnitt springt dort)."""


@dataclass(frozen=True)
class Setback:
    """Abstand einer Kante nach einer Regel; `None` heißt „nicht ermittelt, kein Abzug“."""

    zone_code: str
    kind: str
    building_kind: str
    status: str
    """`effective`, `not_regulated`, `unknown` oder `missing` (keine Regel dieser Art)."""
    reason: str | None
    lenient_m: float | None
    strict_m: float | None
    params: dict[str, Any] = field(default_factory=dict)
    citation: Citation | None = None
    markers: list[str] = field(default_factory=list)


def index_rules(rules: list[RuleInput]) -> RuleIndex:
    return {(rule.kind, rule.building_kind): rule for rule in rules}


def rule_for(rules: RuleIndex, kind: str, building_kind: str = "main") -> RuleInput | None:
    """Regel für einen Baukörper; ohne eigene Regel gilt die allgemeine (`any`, Spez. 5.2.4)."""
    return rules.get((kind, building_kind)) or rules.get((kind, "any"))


def setbacks_for_edge(
    edge: EdgeInput, rules: RuleIndex, heights: Heights, zone_code: str, building_kind: str = "main"
) -> list[Setback]:
    """Alle Regeln, die für diese Kante in Betracht kommen (bei `other` zwei)."""
    return [
        _setback(rules, kind, heights, zone_code, building_kind)
        for kind in KIND_BY_EDGE.get(edge.kind, ("setback_side",))
    ]


def _setback(rules: RuleIndex, kind: str, heights: Heights, zone_code: str, building_kind: str) -> Setback:
    rule = rule_for(rules, kind, building_kind)
    if rule is None:
        return Setback(
            zone_code=zone_code,
            kind=kind,
            building_kind=building_kind,
            status="missing",
            reason="missing",
            lenient_m=None,
            strict_m=None,
            markers=["setback_unknown"],
        )
    base = Setback(
        zone_code=zone_code,
        kind=kind,
        building_kind=rule.building_kind,
        status=rule.status,
        reason=rule.reason,
        lenient_m=None,
        strict_m=None,
        params=dict(rule.params),
        citation=rule.citation,
    )
    if rule.status == "not_regulated":
        # Belegt „nicht geregelt“ (RW24): kein Abstand vorgeschrieben
        return _with(base, 0.0, 0.0, [])
    if rule.status != "effective":
        return _with(base, None, None, ["setback_unknown"])
    if kind == "setback_street":
        return _street(base, rule)
    return _boundary(base, rule, heights)


def _street(base: Setback, rule: RuleInput) -> Setback:
    params = rule.params
    if params.get("mode") == "alignment":
        # Flucht der Nachbarbebauung: ohne Nachbargebäude nicht berechenbar (Plan G3 3.1)
        return _with(base, None, None, ["alignment"])
    minimum = _number(params.get("min_m")) or 0.0
    return _with(base, minimum, minimum, [])


def _boundary(base: Setback, rule: RuleInput, heights: Heights) -> Setback:
    params = rule.params
    minimum = _number(params.get("min_m")) or 0.0
    factor = _number(params.get("height_factor"))
    markers: list[str] = []
    lenient = minimum
    if params.get("allow_on_boundary"):
        lenient = 0.0
        markers.append("on_boundary_allowed")
    strict = minimum
    if factor is not None:
        height = heights.for_basis(params.get("height_basis"))
        if height is None:
            markers.append("height_unknown")
        else:
            strict = max(minimum, factor * height)
    return _with(base, lenient, strict, markers)


def at_height(setback: Setback, heights: Heights, height_m: float) -> Setback:
    """Derselbe Abstand für einen Baukörperteil, der bis `height_m` reicht (Gabarit, docs/PLAN_AN3_GABARIT.md
    3.1).

    Wie `_boundary`, aber mit der Höhe der Stufe statt der Höchsthöhe: Über der Bezugshöhe der Regel (Traufe
    bei `eave`) wächst der Abstand nicht weiter, und auf der Grenze darf weit ausgelegt nur bis
    `on_boundary_max_height_m` gebaut werden. Abstände zur Straße, nicht geregelte und nicht ermittelte
    bleiben, wie sie sind.
    """
    if setback.kind == "setback_street" or setback.status != "effective":
        return setback
    params = setback.params
    minimum = _number(params.get("min_m")) or 0.0
    factor = _number(params.get("height_factor"))
    cap = heights.for_basis(params.get("height_basis"))
    height = min(height_m, cap) if cap is not None else height_m
    strict = max(minimum, factor * height) if factor is not None else minimum
    lenient = strict
    markers = [m for m in setback.markers if m not in ("height_unknown", "on_boundary_allowed")]
    limit = _number(params.get("on_boundary_max_height_m"))
    if params.get("allow_on_boundary") and (limit is None or height_m <= limit + HEIGHT_EPSILON_M):
        lenient = 0.0
        markers.append("on_boundary_allowed")
    return _with(setback, lenient, strict, markers)


def distances(setbacks: list[Setback]) -> tuple[float | None, float | None, list[str]]:
    """Abstand der Kante aus allen in Betracht kommenden Regeln.

    Weiteste Auslegung: der kleinste Abstand; ist eine Regel nicht ermittelt, wird nichts abgezogen.
    Engste Auslegung: der größte ermittelte Abstand; fehlt einer, ist die Kontur unvollständig.
    """
    markers = sorted({m for s in setbacks for m in s.markers})
    lenient_values = [s.lenient_m for s in setbacks]
    lenient = (
        None if any(v is None for v in lenient_values) else min(v for v in lenient_values if v is not None)
    )
    strict_known = [s.strict_m for s in setbacks if s.strict_m is not None]
    strict = max(strict_known) if strict_known else None
    return lenient, strict, markers


def incomplete_reasons(edge: EdgeInput, setbacks: list[Setback]) -> list[str]:
    """Gründe, warum die engste Kontur an dieser Kante nicht belastbar ist."""
    reasons: list[str] = []
    for setback in setbacks:
        if setback.strict_m is None:
            reasons.append(f"setback_unknown:{edge.kind}:{setback.zone_code}")
        elif "height_unknown" in setback.markers:
            reasons.append(f"height_unknown:{edge.kind}:{setback.zone_code}")
    return reasons


def _with(base: Setback, lenient: float | None, strict: float | None, markers: list[str]) -> Setback:
    return Setback(
        zone_code=base.zone_code,
        kind=base.kind,
        building_kind=base.building_kind,
        status=base.status,
        reason=base.reason,
        lenient_m=lenient,
        strict_m=strict,
        params=base.params,
        citation=base.citation,
        markers=markers,
    )


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
