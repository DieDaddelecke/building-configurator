"""Regeln für ein Grundstück auflösen (Plan 3.4, RW21, BR15): welche Teilflächen zählen, welchen Stand eine
Zone und das ganze Grundstück haben, wann der vorige Planstand gilt und wie eine Projektkorrektur wirkt.

Ohne Datenbank; Laden und Anzeige bleiben in `app.rules.service` (REFACTORING_PLAN S12, B-60).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.rules.domain.kinds import BUILDING_SPECIFIC_KINDS

SLIVER_MIN_M2 = 1.0
SLIVER_MIN_SHARE = 0.01
"""Teilflächen unter 1 m² oder 1 % der Grundstücksfläche werden ignoriert (Spez. 5.2.2)."""
UNCOVERED_WARNING_SHARE = 0.01
"""Liegt mehr als dieser Anteil des Grundstücks in keiner Zone des Planwerks, erscheint eine Warnung."""
RESULT_STATUSES = frozenset({"simulated", "office_reviewed"})
"""Stände einer Zone mit Regeln."""
SPECIFIC_BUILDING_KINDS = ("main", "annex", "pool")
EXTRACTING = ("pending", "extracting")
"""Stände eines Kapitels, solange seine Auswertung läuft."""


class _Part(Protocol):
    @property
    def area(self) -> float: ...


@dataclass(frozen=True)
class ZoneSplit[P: _Part]:
    relevant: list[P]
    ignored: list[P]
    uncovered_share: float
    """Anteil des Grundstücks in keiner Zone, auf vier Stellen; ohne Teilflächen 0."""
    warnings: list[str]


def split_slivers[P: _Part](parts: Sequence[P], site_area: float) -> ZoneSplit[P]:
    """Teilflächen Grundstück × Zone trennen: Splitter werden ignoriert (Spez. 5.2.2), mehrere Zonen und eine
    unvollständige Abdeckung ergeben Warnungen. `site_area` ist größer als null; die Reihenfolge bleibt."""
    relevant: list[P] = []
    ignored: list[P] = []
    for part in parts:
        keep = part.area >= SLIVER_MIN_M2 and part.area >= SLIVER_MIN_SHARE * site_area
        (relevant if keep else ignored).append(part)
    warnings = ["multiple_zones"] if len(relevant) > 1 else []
    uncovered = max(0.0, 1.0 - sum(part.area for part in parts) / site_area)
    if parts and uncovered >= UNCOVERED_WARNING_SHARE:
        warnings.append("zone_coverage_incomplete")
    return ZoneSplit(relevant, ignored, round(uncovered, 4) if parts else 0.0, warnings)


@dataclass(frozen=True)
class ZoneState:
    """Stand einer Zone: `simulated` oder `office_reviewed` mit Regeln, sonst `in_progress` oder
    `unavailable` mit Grund. `updating`: Es gibt Regeln, ihr Kapitel wird aber gerade neu ausgewertet."""

    status: str
    reason: str | None = None
    updating: bool = False


def zone_state(
    version_status: str | None,
    chapter_status: str | None,
    *,
    version_origin: str | None = None,
    pinned: bool = False,
    chapter_error: str | None = None,
) -> ZoneState:
    """Stand einer Zone aus ihrer Regelwerksversion und ihrem Kapitel; `None` heißt, es gibt sie nicht.

    Eine angeheftete frühere Version (Vergleich, AN4 3.5) zählt nach ihrer Herkunft, nicht als `retired`
    (PLAN_AN4 7.1 Nr. 4). Ohne Version entscheidet das Kapitel."""
    if version_status is not None and pinned:
        return ZoneState("office_reviewed" if version_origin == "office" else "simulated")
    if version_status is not None:
        return ZoneState(version_status, updating=chapter_status in EXTRACTING)
    if chapter_status is None:
        return ZoneState("unavailable", "chapter_not_found")
    if chapter_status in EXTRACTING:
        return ZoneState("in_progress")
    return ZoneState("unavailable", chapter_error or chapter_status)


def overall_status(zones: Sequence[ZoneState]) -> tuple[str, str | None]:
    """Stand und Grund für das ganze Grundstück; `zones` in der Reihenfolge der Anzeige (größte zuerst)."""
    statuses = {zone.status for zone in zones}
    if not zones:
        return "unavailable", "no_zone"
    if statuses <= RESULT_STATUSES:
        return "ok", None
    if "in_progress" in statuses and not statuses & RESULT_STATUSES:
        return "in_progress", None
    if statuses & RESULT_STATUSES:
        return "partial", None
    return "unavailable", zones[0].reason


def use_older(current: str | None, older: str) -> bool:
    """Gilt der vorige Planstand (RW21)? Gefragt wird nur, wenn der aktuelle nicht `ok` ist; `current` ist
    `None`, wenn er sich nicht auswerten lässt. Der vorige gilt vollständig immer, teilweise nur, solange der
    aktuelle gar keine Regeln hat."""
    return older == "ok" or (older == "partial" and current != "partial")


class _Keyed(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def building_kind(self) -> str: ...


def apply_override[R: _Keyed](
    rules: Sequence[R], correction: R, for_building: Callable[[R, str], R]
) -> list[R]:
    """Korrektur für ein Projekt einsetzen; `correction` trägt Art und Baukörper. Die spezifischere Regel
    geht vor:

    - `any` ersetzt alle Regeln dieser Art.
    - `main`, `annex` oder `pool` ersetzt die Regel dieses Baukörpers. Eine automatische Regel für `any`
      gilt dann nur noch für die übrigen Baukörper und erscheint für diese einzeln (`for_building`); bei
      Regelarten, die das Grundstück als Ganzes betreffen (Grundfläche, Stellplätze …), ersetzt die Korrektur
      sie ganz.
    """
    specific = correction.building_kind
    present = {(r.kind, r.building_kind) for r in rules}
    result: list[R] = []
    for rule in rules:
        if rule.kind != correction.kind:
            result.append(rule)
        elif specific == "any" or rule.building_kind == specific:
            continue
        elif rule.building_kind == "any":
            if correction.kind in BUILDING_SPECIFIC_KINDS:
                result.extend(
                    for_building(rule, other)
                    for other in SPECIFIC_BUILDING_KINDS
                    if other != specific and (rule.kind, other) not in present
                )
        else:
            result.append(rule)
    return [*result, correction]


def feed_state(
    version_status: str | None,
    state_status: str | None,
    *,
    chapter_known: bool,
    state_error: str | None = None,
) -> ZoneState:
    """Stand einer Zone für den Regeldienst in einem Umfang (PLAN_REGELDIENST 4.2): Mit Version zählt sie;
    sonst der Stand der Auswertung. Ein Umfang ohne Auftrag ist `not_extracted` und kommt nicht von selbst."""
    if version_status is not None:
        return ZoneState(version_status, updating=state_status in EXTRACTING)
    if not chapter_known:
        return ZoneState("unavailable", "chapter_not_found")
    if state_status is None or state_status == "pending":
        return ZoneState("not_extracted", state_status)
    if state_status == "extracting":
        return ZoneState("in_progress")
    return ZoneState("unavailable", state_error or state_status)
