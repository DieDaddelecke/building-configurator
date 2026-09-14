"""Automatische Schranken statt Freigabe (Plan 3.4, Entscheidung D11).

1. Jede Regel eines Laufs: Sektor bekannt, Parameter gültig und plausibel, Zitat auf der Seite gefunden.
2. Zwei Läufe je Kapitel: Nur übereinstimmende Werte wirken; Abweichungen werden `unknown`.
3. Fehlende Pflichtarten werden `unknown` („missing“), nie mit einem Standardwert gefüllt.

Ergebnis je Regel: `effective` (wirkt in der Simulation), `unknown` (mit Grund), `not_regulated` (belegt
nicht geregelt) oder `text_only` (Hinweis).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from app.rules.domain.extraction import ExtractedRule
from app.rules.domain.kinds import MANDATORY_KINDS, ParamProblem, params_equal, validate_params
from app.rules.domain.text import QuoteCheck, normalize, values_in_quote, verify_quote

RuleStatus = Literal["effective", "unknown", "not_regulated", "text_only"]
UnknownReason = Literal[
    "quote_unverified",
    "value_not_in_quote",
    "invalid_params",
    "implausible",
    "not_regulated_unproven",
    "graphic_reference",
    "runs_disagree",
    "ambiguous",
    "missing",
]


@dataclass(frozen=True)
class AssessedRule:
    sector: str
    kind: str
    building_kind: str
    status: RuleStatus
    reason: str | None
    params: dict[str, Any]
    page: int | None
    """Seite im Originaldokument (1-basiert)."""
    quote: str | None
    quote_verified: bool
    similarity: float
    confidence: float
    notes: str
    detail: str | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentPages:
    """Welche Originalseiten in welchem PDF an das Modell gingen, in Reihenfolge."""

    general: list[int]
    chapter: list[int]

    def original_page(self, document: str, position: int) -> int | None:
        pages = self.general if document == "general" else self.chapter
        return pages[position - 1] if 1 <= position <= len(pages) else None


def _check_quote(rule: ExtractedRule, documents: DocumentPages, page_texts: dict[int, str]) -> QuoteCheck:
    """Erst die Position im gesendeten PDF, dann die Zahl als gedruckte bzw. Originalseite: Modelle nennen
    manchmal die aufgedruckte Seitenzahl statt der Position."""
    candidates: list[int] = []
    mapped = documents.original_page(rule.document, rule.page)
    if mapped is not None:
        candidates.append(mapped)
    if rule.page in page_texts and rule.page not in candidates:
        candidates.append(rule.page)
    best = QuoteCheck(False, None, 0.0, "page_unknown")
    for page in candidates:
        check = verify_quote(rule.quote, page_texts, page)
        if check.verified:
            return check
        if check.similarity > best.similarity or best.reason == "page_unknown":
            best = check
    return best


def assess_rule(
    rule: ExtractedRule, sectors: set[str], documents: DocumentPages, page_texts: dict[int, str]
) -> AssessedRule | None:
    """Schranken für eine Regel. None, wenn der Sektor nicht angefragt war oder ein Hinweis unbelegt ist."""
    if rule.sector not in sectors:
        return None
    quote = _check_quote(rule, documents, page_texts)
    base = AssessedRule(
        sector=rule.sector,
        kind=rule.kind,
        building_kind=rule.building_kind,
        status="unknown",
        reason=None,
        params={},
        page=quote.page,
        quote=rule.quote.strip() or None,
        quote_verified=quote.verified,
        similarity=quote.similarity,
        confidence=rule.confidence,
        notes=rule.notes,
    )
    if rule.status == "text_only" or rule.kind == "text_only":
        summary = rule.params.get("summary") or rule.notes
        if not quote.verified or not summary:
            return None
        return replace(base, kind="text_only", status="text_only", params={"summary": str(summary)[:500]})
    if rule.status == "graphic_reference":
        return replace(base, reason="graphic_reference")
    if rule.status == "not_regulated":
        if quote.verified:
            return replace(base, status="not_regulated")
        return replace(base, reason="not_regulated_unproven", detail=quote.reason)
    if rule.duplicate_params:
        return replace(base, reason="invalid_params", detail="duplicate:" + ",".join(rule.duplicate_params))
    try:
        params = validate_params(rule.kind, rule.params)
    except ParamProblem as problem:
        return replace(base, reason=problem.reason, detail=problem.detail)
    if not quote.verified:
        return replace(base, params=params, reason="quote_unverified", detail=quote.reason)
    numeric = [float(v) for v in params.values() if isinstance(v, int | float) and not isinstance(v, bool)]
    missing = values_in_quote(numeric, rule.quote)
    if missing:
        # Belegtes Zitat, aber der Wert steht nicht darin: der Wert könnte erfunden oder verwechselt sein
        return replace(
            base, params=params, reason="value_not_in_quote", detail=",".join(f"{v:g}" for v in missing)
        )
    return replace(base, status="effective", params=params)


Key = tuple[str, str, str]


def _key(rule: AssessedRule) -> Key:
    # „any“ gilt auch für das Hauptgebäude; so vergleichen zwei Läufe dieselbe Regel, auch wenn einer
    # „main“ und der andere „any“ schreibt
    building_kind = "main" if rule.building_kind == "any" else rule.building_kind
    return (rule.sector, rule.kind, building_kind)


def _collapse(rules: list[AssessedRule]) -> AssessedRule:
    """Mehrere Regeln desselben Schlüssels in einem Lauf: nur gleichwertig eindeutig."""
    first = rules[0]
    if len(rules) == 1:
        return first
    if all(r.status == first.status and params_equal(r.params, first.params) for r in rules[1:]):
        return max(rules, key=lambda r: r.similarity)
    return replace(
        first,
        status="unknown",
        reason="ambiguous",
        alternatives=[_alternative(r) for r in rules],
    )


def _alternative(rule: AssessedRule) -> dict[str, Any]:
    return {"status": rule.status, "reason": rule.reason, "params": rule.params, "page": rule.page}


def _agree(a: AssessedRule, b: AssessedRule) -> bool:
    if a.status != b.status:
        return False
    if a.status == "effective":
        return params_equal(a.params, b.params)
    return True


def consensus(runs: list[list[AssessedRule]], sectors: list[str]) -> list[AssessedRule]:
    """Ergebnis aus einem oder mehreren Läufen je Kapitel, ergänzt um fehlende Pflichtarten."""
    by_run: list[dict[Key, list[AssessedRule]]] = []
    hints: dict[tuple[str, str, str], AssessedRule] = {}
    for run in runs:
        grouped: dict[Key, list[AssessedRule]] = defaultdict(list)
        for rule in run:
            if rule.status == "text_only":
                # Hinweise sind frei formuliert; gleich sind sie, wenn sie dieselbe Stelle zitieren
                hint_key = (rule.sector, str(rule.page), normalize(rule.quote or "")[:80])
                hints.setdefault(hint_key, rule)
                continue
            grouped[_key(rule)].append(rule)
        by_run.append(grouped)
    keys = sorted({key for grouped in by_run for key in grouped})
    result: list[AssessedRule] = []
    for key in keys:
        candidates = [_collapse(grouped[key]) if key in grouped else None for grouped in by_run]
        present = [c for c in candidates if c is not None]
        building_kind = "any" if all(c.building_kind == "any" for c in present) else key[2]
        if len(runs) == 1 or (all(c is not None for c in candidates) and len(present) == len(runs)):
            first = present[0]
            if all(_agree(first, other) for other in present[1:]):
                best = max(present, key=lambda r: (r.quote_verified, r.similarity))
                result.append(
                    replace(best, building_kind=building_kind, confidence=min(c.confidence for c in present))
                )
                continue
        reference = present[0]
        result.append(
            replace(
                reference,
                building_kind=building_kind,
                status="unknown",
                reason="ambiguous" if any(c.reason == "ambiguous" for c in present) else "runs_disagree",
                params={},
                alternatives=[_alternative(c) if c else {"status": "absent"} for c in candidates],
                confidence=min(c.confidence for c in present),
            )
        )
    covered = {(r.sector, r.kind) for r in result if r.building_kind in ("main", "any")}
    for sector in sectors:
        for kind in MANDATORY_KINDS:
            if (sector, kind) not in covered:
                result.append(
                    AssessedRule(
                        sector=sector,
                        kind=kind,
                        building_kind="main",
                        status="unknown",
                        reason="missing",
                        params={},
                        page=None,
                        quote=None,
                        quote_verified=False,
                        similarity=0.0,
                        confidence=0.0,
                        notes="",
                    )
                )
    result.extend(hints.values())
    order = {kind: i for i, kind in enumerate(MANDATORY_KINDS)}
    return sorted(result, key=lambda r: (r.sector, order.get(r.kind, 99), r.kind, r.building_kind))


class _Countable(Protocol):
    @property
    def kind(self) -> str: ...
    @property
    def building_kind(self) -> str: ...
    @property
    def status(self) -> str: ...


def coverage(rules: Iterable[_Countable]) -> dict[str, int]:
    """Zählung je Status und Anteil unbekannter Pflichtarten für Abdeckung und Kennzahlen (Plan 6.8)."""
    counts: dict[str, int] = defaultdict(int)
    for rule in rules:
        counts[rule.status] += 1
        if (
            rule.kind in MANDATORY_KINDS
            and rule.building_kind in ("main", "any")
            and rule.status == "unknown"
        ):
            counts["mandatory_unknown"] += 1
    return dict(counts)
