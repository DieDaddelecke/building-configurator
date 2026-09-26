"""Regeln eines Zusatzdokuments mit den PLU-Regeln vergleichen (docs/PLAN_AN3_ANALYSE.md 3.8).

Beide gelten nebeneinander; das Strengere bindet – sofern das Zusatzdokument gilt, was der Architekt
beurteilt (E-AN3-2). Der Vergleich ordnet deshalb nur ein, er verrechnet nichts. Je Parameter eine Richtung:
Ein Höchstwert ist kleiner strenger, ein Mindestwert größer, eine erlaubte Menge als echte Teilmenge. Ein
Parameter nur im Zusatzdokument schränkt zusätzlich ein; einer nur im PLU gilt weiter und ist neutral.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.envelope.domain.inputs import RuleInput
from app.envelope.domain.setbacks import index_rules, rule_for

Verdict = Literal[
    "stricter", "looser", "equal", "mixed", "different", "only_supplement", "no_own_rule", "unknown"
]
ParamVerdict = Literal["stricter", "looser", "equal", "different"]
Direction = Literal["max", "min", "allowed", "forbidden", "permission", "storeys", "ordered"]

_BOUNDARY: dict[str, Direction] = {
    "min_m": "min",
    "height_factor": "min",
    "allow_on_boundary": "permission",
    "on_boundary_max_height_m": "max",
}
DIRECTIONS: dict[str, dict[str, Direction]] = {
    "setback_street": {"min_m": "min", "max_m": "max"},
    "setback_side": _BOUNDARY,
    "setback_rear": _BOUNDARY,
    "setback_between_buildings": {"min_m": "min", "height_factor": "min"},
    "max_footprint_ratio": {"ratio": "max", "terrace_counts_above_m": "max"},
    "max_height": {"ridge_m": "max", "eave_m": "max", "parapet_m": "max", "storeys": "storeys"},
    "roof": {
        "allowed_forms": "allowed",
        "pitch_min_deg": "min",
        "pitch_max_deg": "max",
        "materials_allowed": "allowed",
        "flat_roof": "ordered",
        "ridge_orientation": "ordered",
    },
    "facade": {
        "materials_allowed": "allowed",
        "materials_forbidden": "forbidden",
        "color_families_allowed": "allowed",
    },
    "unsealed_min": {"ratio": "min", "full_soil_ratio": "min"},
    "parking": {"spaces_per_dwelling": "min", "spaces_per_m2_sdp": "min"},
    "annex": {"max_footprint_m2": "max", "max_height_m": "max"},
    "planting": {"trees_per_m2": "min", "min_green_ratio": "min"},
    "fence": {"max_height_m": "max", "materials": "allowed"},
    "max_area": {"sdp_m2": "max", "footprint_m2": "max"},
}
"""Parameter ohne Eintrag (Messbezug, Modus, Band …) werden auf Gleichheit geprüft."""
ORDER: dict[str, dict[str, int]] = {
    "flat_roof": {"allowed": 0, "green_only": 1, "annex_only": 1, "forbidden": 2},
    "ridge_orientation": {"any": 0, "parallel_to_street": 1, "perpendicular_to_street": 1},
}
"""Stufen von „erlaubt“ zu „verboten“; zwei verschiedene Werte derselben Stufe sind nicht vergleichbar."""
ANALYSIS_KINDS = frozenset(
    {"max_footprint_ratio", "max_area", "max_height", "setback_street", "setback_side", "setback_rear"}
)
"""Arten, die in die Kennzahlen der Analyse eingehen: Ist das Zusatzdokument hier strenger, meldet die
Analyse `supplement_stricter`, weil ihre Werte es nicht enthalten."""
RESTRICTING: frozenset[str] = frozenset({"stricter", "only_supplement", "mixed"})
_TOLERANCE = 0.005


@dataclass(frozen=True)
class Comparison:
    kind: str
    building_kind: str
    verdict: Verdict
    supplement: RuleInput
    plu: RuleInput | None
    details: dict[str, ParamVerdict] = field(default_factory=dict)


def _levels(value: Any) -> int | None:
    """`R+1+C` → Zahl der Ebenen (Erdgeschoss, Obergeschosse, oberstes Geschoss als halbe Ebene)."""
    text = str(value).replace(" ", "").upper()
    parts = text.split("+")
    if not parts or parts[0] != "R":
        return None
    count = 2
    for part in parts[1:]:
        if part.isdigit():
            count += 2 * int(part)
        elif part:
            count += 1
    return count


def _param(name: str, direction: Direction | None, plu: Any, supplement: Any) -> ParamVerdict:
    if direction in ("max", "min") and _is_number(plu) and _is_number(supplement):
        difference = float(supplement) - float(plu)
        if abs(difference) <= _TOLERANCE:
            return "equal"
        stricter = difference < 0 if direction == "max" else difference > 0
        return "stricter" if stricter else "looser"
    if direction in ("allowed", "forbidden"):
        left, right = set(plu or ()), set(supplement or ())
        if left == right:
            return "equal"
        narrower, wider = (
            (right < left, right > left) if direction == "allowed" else (right > left, right < left)
        )
        return "stricter" if narrower else "looser" if wider else "different"
    if direction == "permission":
        if bool(plu) == bool(supplement):
            return "equal"
        return "stricter" if not supplement else "looser"
    if direction == "storeys":
        left_levels, right_levels = _levels(plu), _levels(supplement)
        if left_levels is None or right_levels is None:
            return "equal" if plu == supplement else "different"
        if left_levels == right_levels:
            return "equal"
        return "stricter" if right_levels < left_levels else "looser"
    if direction == "ordered":
        ranks = ORDER[name]
        if plu == supplement:
            return "equal"
        left_rank, right_rank = ranks.get(str(plu)), ranks.get(str(supplement))
        if left_rank is None or right_rank is None or left_rank == right_rank:
            return "different"
        return "stricter" if right_rank > left_rank else "looser"
    return "equal" if plu == supplement else "different"


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _combine(details: dict[str, ParamVerdict]) -> Verdict:
    values = set(details.values())
    if "different" in values:
        return "different"
    if {"stricter", "looser"} <= values:
        return "mixed"
    if "stricter" in values:
        return "stricter"
    if "looser" in values:
        return "looser"
    return "equal"


def compare_rule(supplement: RuleInput, plu: RuleInput | None) -> Comparison:
    base: dict[str, Any] = {
        "kind": supplement.kind,
        "building_kind": supplement.building_kind,
        "supplement": supplement,
    }
    if supplement.status == "not_regulated":
        # „Non réglementé“ im Zusatzdokument heißt: Es regelt nichts Eigenes, der PLU gilt (7.1 Nr. 5)
        return Comparison(**base, verdict="no_own_rule", plu=plu)
    if supplement.status != "effective":
        return Comparison(**base, verdict="unknown", plu=plu)
    if plu is None or plu.status not in ("effective", "not_regulated"):
        return Comparison(**base, verdict="only_supplement", plu=plu)
    if plu.status == "not_regulated":
        return Comparison(**base, verdict="stricter", plu=plu)
    directions = DIRECTIONS.get(supplement.kind, {})
    details: dict[str, ParamVerdict] = {}
    for name, value in supplement.params.items():
        direction = directions.get(name)
        if name not in plu.params:
            # Zusätzliche Festsetzung: schränkt ein, wo sie eine Richtung hat; sonst nicht vergleichbar
            details[name] = "stricter" if direction is not None else "different"
            continue
        details[name] = _param(name, direction, plu.params[name], value)
    return Comparison(**base, verdict=_combine(details), plu=plu, details=details)


def compare(supplement_rules: list[RuleInput], plu_rules: list[RuleInput]) -> list[Comparison]:
    """Je Regel des Zusatzdokuments (ohne Hinweise) die PLU-Regel derselben Art und desselben Baukörpers,
    mit Rückfall auf `any` (Spez. 5.2.4)."""
    index = index_rules(plu_rules)
    return [
        compare_rule(rule, rule_for(index, rule.kind, rule.building_kind))
        for rule in supplement_rules
        if rule.status != "text_only" and rule.kind != "text_only"
    ]


def stricter_kinds(comparisons: list[Comparison]) -> list[str]:
    """Arten der Kennzahlen, bei denen das Zusatzdokument strenger ist oder allein einschränkt."""
    return sorted({c.kind for c in comparisons if c.kind in ANALYSIS_KINDS and c.verdict in RESTRICTING})
