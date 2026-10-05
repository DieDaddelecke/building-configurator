"""Ergebnisarten und Status des Hausmodells (docs/PLAN_HAUSMODELL.md 3.7, E-HM-6).

Katalogregeln rechnet der Kern (`info`, `warning`, `block`); die PLU-Prüfung hier ergibt `deviation` (wirksame
Regel verletzt), `warning` (Regel unbekannt oder nicht prüfbar) oder `info` (Hinweis). Der Status ist
abgeleitet und wird nie gespeichert: `blocked` vor `with_deviations` vor `valid_with_warnings` vor `valid`.
"""

import math
from collections.abc import Iterable
from typing import Literal

from app.configuration.domain.checks import FAIL, HINT, UNKNOWN, Check

SiteOutcome = Literal["deviation", "warning", "info"]
HouseStatus = Literal["valid", "valid_with_warnings", "with_deviations", "blocked"]


def site_outcome(check: Check) -> SiteOutcome | None:
    """Ergebnisart einer Prüfung auf dem Grundstück; `None` für bestanden oder nicht anwendbar."""
    if check.status == FAIL:
        return "deviation" if check.binding else "warning"
    if check.status == UNKNOWN:
        return "warning"
    if check.status == HINT:
        return "info"
    return None


def combined_status(catalog_status: str, outcomes: Iterable[str]) -> HouseStatus:
    """Status aus dem Ergebnis des Kerns (Katalogregeln) und den Ergebnisarten der PLU-Prüfung."""
    found = set(outcomes)
    if catalog_status == "blocked" or "block" in found:
        return "blocked"
    if "deviation" in found:
        return "with_deviations"
    if catalog_status != "valid" or "warning" in found:
        return "valid_with_warnings"
    return "valid"


def round_amount(value: float, step: float) -> float:
    """Kaufmännisch auf `step` Euro, symmetrisch zur Null: `sign(x)·⌊|x|/step + 0,5⌋·step`. Der Browser
    rechnet genauso (`frontend/src/haus/preis.ts`), damit beide dieselbe Zahl zeigen (E-HM-2)."""
    rounded = math.floor(abs(value) / step + 0.5) * step
    return math.copysign(rounded, value) if rounded else 0.0
