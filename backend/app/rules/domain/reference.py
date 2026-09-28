"""Referenzlisten: Soll-Regeln eines Zonenkapitels und die Messung einer Auswertung daran
(docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10).

Eine Referenzliste nennt je Vorschrift den erwarteten Status, die maßgeblichen Parameter, Seite und Zitat.
Verglichen werden nur die Parameter, die der Eintrag nennt: Wo die Zuordnung zum Vokabular strittig ist
(„cuivre“: `metal` oder `other`), lässt die Liste den Parameter weg und erklärt ihn in der Notiz.

Ergebnis je Eintrag: `hit` (richtig), `wrong_value` (wirksam, aber falsch – das Schlimmste), `named_gap`
(„nicht ermittelt“ oder offene Stelle – sichtbar), `dismissed` (Stelle als „betrifft kein Einfamilienhaus“
eingestuft), `silent_gap` (nichts davon – die Vorschrift fehlt still). Ziel: kein `wrong_value`, kein
`silent_gap`.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from app.rules.domain.assess import rule_key
from app.rules.domain.kinds import BUILDING_KINDS, PARAM_MODELS, RULE_KINDS
from app.rules.domain.passages import Passage
from app.rules.domain.text import quotes_overlap

ExpectedStatus = Literal["effective", "not_regulated", "text_only", "graphic_reference", "not_expressible"]
EXPECTED_STATUSES: tuple[str, ...] = get_args(ExpectedStatus)
Outcome = Literal["hit", "wrong_value", "named_gap", "dismissed", "silent_gap"]
OUTCOMES: tuple[str, ...] = get_args(Outcome)
NUMBER_TOLERANCE = 0.01


@dataclass(frozen=True)
class ReferenceEntry:
    kind: str
    building_kind: str
    expected: str
    params: dict[str, Any]
    page: int | None
    quote: str
    note: str = ""


@dataclass(frozen=True)
class FoundRule:
    """Regel einer Regelwerksversion, wie sie die Messung braucht."""

    kind: str
    building_kind: str
    status: str
    reason: str | None
    params: dict[str, Any]
    page: int | None
    quote: str | None


@dataclass(frozen=True)
class EntryResult:
    entry: ReferenceEntry
    outcome: str
    found: FoundRule | None = None
    detail: str = ""


@dataclass(frozen=True)
class Measurement:
    results: list[EntryResult]
    extra: list[FoundRule] = field(default_factory=list)
    """Wirksame oder belegt nicht geregelte Regeln ohne Eintrag: Liste unvollständig oder Fehlfund."""
    extra_hints: list[FoundRule] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counted = Counter(r.outcome for r in self.results)
        return {outcome: counted.get(outcome, 0) for outcome in OUTCOMES} | {
            "entries": len(self.results),
            "extra": len(self.extra),
            "extra_hints": len(self.extra_hints),
        }

    @property
    def recall(self) -> float:
        return self.counts["hit"] / len(self.results) if self.results else 0.0


class ReferenceProblem(ValueError):
    pass


def parse_entries(items: Iterable[Mapping[str, Any]]) -> list[ReferenceEntry]:
    """Einträge prüfen: bekannte Art, Baukörper und Status; Parameter nur mit Namen der Regelart."""
    entries: list[ReferenceEntry] = []
    for number, item in enumerate(items, start=1):
        kind, building_kind, expected = item.get("kind"), item.get("building_kind"), item.get("expected")
        if kind not in RULE_KINDS or building_kind not in BUILDING_KINDS or expected not in EXPECTED_STATUSES:
            raise ReferenceProblem(f"entry {number}: kind, building_kind or expected unknown")
        if (kind == "text_only") != (expected == "text_only"):
            raise ReferenceProblem(f"entry {number}: text_only needs kind and expected text_only")
        params = dict(item.get("params") or {})
        unknown = sorted(set(params) - set(PARAM_MODELS[kind].model_fields))
        if unknown:
            raise ReferenceProblem(f"entry {number}: params {', '.join(unknown)} not in {kind}")
        quote = str(item.get("quote") or "").strip()
        if not quote:
            raise ReferenceProblem(f"entry {number}: quote required")
        page = item.get("page")
        entries.append(
            ReferenceEntry(
                kind=kind,
                building_kind=building_kind,
                expected=expected,
                params=params,
                page=int(page) if page is not None else None,
                quote=quote,
                note=str(item.get("note") or ""),
            )
        )
    return entries


def _value_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return abs(float(expected) - float(actual)) <= NUMBER_TOLERANCE
    if isinstance(expected, list | tuple) and isinstance(actual, list | tuple):
        return sorted(map(str, expected)) == sorted(map(str, actual))
    return bool(expected == actual)


def differing_params(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> list[str]:
    """Namen der Parameter des Eintrags, die in der Regel fehlen oder anders sind."""
    return [
        name
        for name, value in expected.items()
        if name not in actual or not _value_equal(value, actual[name])
    ]


def _near(entry: ReferenceEntry, page: int | None) -> bool:
    return entry.page is None or page is None or abs(entry.page - page) <= 1


def _measure_kind(
    entry: ReferenceEntry,
    rule: FoundRule | None,
    hints: Sequence[FoundRule],
    open_passages: Sequence[Passage],
    dismissed: Sequence[Passage],
) -> EntryResult:
    if rule is None:
        # Ohne Regel zählt, ob die Vorschrift sichtbar ist: als Hinweis, offene oder verworfene Stelle
        seen = _measure_hint(entry, hints, open_passages, dismissed)
        outcome = "named_gap" if seen.outcome == "hit" else seen.outcome
        return EntryResult(entry, outcome, seen.found, "hint" if seen.outcome == "hit" else seen.detail)
    if rule.status == "unknown":
        wanted = {"not_expressible": "not_expressible", "graphic_reference": "graphic_reference"}
        if wanted.get(entry.expected) == rule.reason:
            return EntryResult(entry, "hit", rule)
        return EntryResult(entry, "named_gap", rule, rule.reason or "")
    if entry.expected == "effective":
        if rule.status != "effective":
            return EntryResult(entry, "wrong_value", rule, rule.status)
        differing = differing_params(entry.params, rule.params)
        return EntryResult(entry, "wrong_value" if differing else "hit", rule, ",".join(differing))
    if entry.expected == "not_regulated" and rule.status == "not_regulated":
        return EntryResult(entry, "hit", rule)
    # Erwartet war „nicht geregelt“, „Wert im Plan“ oder „nicht abbildbar“: ein Wert ist hier falsch
    return EntryResult(entry, "wrong_value", rule, rule.status)


def _measure_hint(
    entry: ReferenceEntry,
    hints: Sequence[FoundRule],
    open_passages: Sequence[Passage],
    dismissed: Sequence[Passage],
) -> EntryResult:
    for hint in hints:
        if _near(entry, hint.page) and quotes_overlap(entry.quote, hint.quote):
            return EntryResult(entry, "hit", hint)
    if any(_near(entry, p.page) and quotes_overlap(entry.quote, p.text) for p in open_passages):
        return EntryResult(entry, "named_gap", None, "open_passage")
    if any(_near(entry, p.page) and quotes_overlap(entry.quote, p.text) for p in dismissed):
        return EntryResult(entry, "dismissed", None, "out_of_scope")
    return EntryResult(entry, "silent_gap")


def measure(
    entries: Sequence[ReferenceEntry],
    rules: Sequence[FoundRule],
    open_passages: Sequence[Passage] = (),
    dismissed: Sequence[Passage] = (),
) -> Measurement:
    """Regeln **eines** Sektors gegen die Einträge. Schlüssel wie beim Zusammenführen (`any` gilt als
    Hauptgebäude)."""
    by_key: dict[tuple[str, str, str], FoundRule] = {}
    hints: list[FoundRule] = []
    for found in rules:
        if found.kind == "text_only" or found.status == "text_only":
            hints.append(found)
        else:
            by_key.setdefault(rule_key("", found.kind, found.building_kind), found)
    results: list[EntryResult] = []
    used_hints: set[int] = set()
    for entry in entries:
        if entry.expected == "text_only":
            result = _measure_hint(entry, hints, open_passages, dismissed)
        else:
            rule = by_key.get(rule_key("", entry.kind, entry.building_kind))
            result = _measure_kind(entry, rule, hints, open_passages, dismissed)
        if result.found is not None and result.found.status == "text_only":
            used_hints.add(id(result.found))
        results.append(result)
    keys = {rule_key("", e.kind, e.building_kind) for e in entries if e.expected != "text_only"}
    extra = [
        found
        for key, found in sorted(by_key.items())
        if key not in keys and found.status in ("effective", "not_regulated")
    ]
    return Measurement(results, extra, [h for h in hints if id(h) not in used_hints])
