"""Vollgeschosse aus der Höhenregel (docs/PLAN_AN3_ANALYSE.md 3.2).

Aus den Parametern der Regel `max_height`, nicht aus `envelope.heights.Heights`: Dort ist `R+1+C` schon mit
3,00 m in Traufe und First umgerechnet, und die Quelle wäre falsch benannt (7.1 Nr. 2).
"""

import math
import re
from dataclasses import dataclass, field
from typing import Literal

from app.analysis.domain.parameters import ATTIC_MIN_RISE_M, ROOF_RISE_M, Parameters
from app.envelope.domain.inputs import Citation, RuleInput

_STOREYS = re.compile(r"^R(?:\+(\d))?(?:\+(C|A|CA|COMBLES))?$", re.IGNORECASE)
_EPSILON = 1e-6
"""Rechentoleranz: 6,00 m / 3,00 m sind zwei Geschosse, auch wenn die Division 1,9999999 ergibt."""

Top = Literal["none", "attic", "attique"]
StoreySource = Literal["storeys", "eave", "parapet", "ridge", "unknown"]


@dataclass(frozen=True)
class Storeys:
    full_min: int | None
    full_max: int | None
    top: Top
    top_certain: bool
    """`True`: der Plan nennt das Geschoss (`+C`, `+A`). `False`: aus den Höhen nur möglich – das untere
    Ende der Nutzfläche zählt es nicht (E-AN3-5)."""
    source: StoreySource
    status: str
    """Status der Höhenregel: `effective`, `unknown`, `not_regulated`, `missing`."""
    citation: Citation | None = None
    notes: list[str] = field(default_factory=list)


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _count(height: float, storey: float) -> int:
    return max(0, math.floor(height / storey + _EPSILON))


def _attic_possible(ridge: float | None, full_max: int, params: Parameters) -> bool:
    """Passt über `full_max` Geschossen (mit der kleinsten Geschosshöhe) ein Dachgeschoss unter den First?
    Ohne Firsthöhe begrenzt der Plan das Dach nicht."""
    return ridge is None or ridge - full_max * params.storey_height_m.low >= ATTIC_MIN_RISE_M - _EPSILON


def storeys_for(rule: RuleInput | None, params: Parameters) -> Storeys:
    if rule is None:
        return Storeys(None, None, "none", False, "unknown", "missing")
    if rule.status != "effective":
        return Storeys(None, None, "none", False, "unknown", rule.status, rule.citation)
    p = rule.params
    eave, ridge, parapet = _number(p.get("eave_m")), _number(p.get("ridge_m")), _number(p.get("parapet_m"))
    h = params.storey_height_m
    text = str(p.get("storeys") or "").replace(" ", "")
    match = _STOREYS.match(text) if text else None
    if match is not None:
        full = 1 + int(match.group(1) or 0)
        suffix = (match.group(2) or "").upper()
        top: Top = "attique" if suffix == "A" else "attic" if suffix else "none"
        notes = ["storeys_exceed_eave"] if eave is not None and full * h.low > eave + 0.01 else []
        return Storeys(full, full, top, bool(suffix), "storeys", "effective", rule.citation, notes)
    if eave is not None:
        low, high = _count(eave, h.high), _count(eave, h.low)
        attic = _attic_possible(ridge, high, params)
        return Storeys(
            low,
            high,
            "attic" if attic else "none",
            False,
            "eave",
            "effective",
            rule.citation,
            ["attic_possible"] if attic else [],
        )
    if parapet is not None:
        return Storeys(
            _count(parapet, h.high),
            _count(parapet, h.low),
            "none",
            False,
            "parapet",
            "effective",
            rule.citation,
        )
    if ridge is not None:
        # Dachform offen: unten ein geneigtes Dach über den Geschossen, oben ein Flachdach bis zum First
        low, high = _count(max(0.0, ridge - ROOF_RISE_M), h.high), _count(ridge, h.low)
        attic = _attic_possible(ridge, high, params)
        notes = ["roof_form_open", *(["attic_possible"] if attic else [])]
        return Storeys(
            low, high, "attic" if attic else "none", False, "ridge", "effective", rule.citation, notes
        )
    return Storeys(None, None, "none", False, "unknown", "effective", rule.citation, ["height_without_value"])
