"""Automatische Schranken statt Freigabe (Plan 3.4, Entscheidung D11).

1. Jede Regel der Auswertung: Sektor bekannt, Parameter gültig und plausibel, Zitat auf der Seite gefunden,
   jeder Zahlenwert im Zitat und dort nicht einem anderen Sektor zugeordnet.
2. Gegenprüfung: Ein zweiter Aufruf liest jede belegte Regel ohne ihre Werte erneut aus dem Zitat. Nur
   übereinstimmende Werte wirken; Abweichungen werden `unknown` (docs/ANNAHMEN.md RW19).
3. Fehlende Pflichtarten werden `unknown` („missing“), nie mit einem Standardwert gefüllt.

Ergebnis je Regel: `effective` (wirkt in der Simulation), `unknown` (mit Grund), `not_regulated` (belegt
nicht geregelt) oder `text_only` (Hinweis).
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from app.rules.domain.extraction import ExtractedRule, VerificationCheck
from app.rules.domain.kinds import MANDATORY_KINDS, ParamProblem, params_equal, validate_params
from app.rules.domain.text import (
    QuoteCheck,
    normalize,
    quotes_overlap,
    states_not_regulated,
    value_positions,
    values_in_quote,
    verify_quote,
)

RuleStatus = Literal["effective", "unknown", "not_regulated", "text_only"]
UnknownReason = Literal[
    "quote_unverified",
    "value_not_in_quote",
    "sector_mismatch",
    "invalid_params",
    "implausible",
    "not_regulated_unproven",
    "graphic_reference",
    "runs_disagree",
    "ambiguous",
    "missing",
    "not_found_after_search",
    "not_expressible",
    "scan_unconfirmed",
]
_SECTOR_PREFIX = re.compile(r"^(?:sous-secteur|secteur|zone)s?\s+", re.IGNORECASE)
_SHORT_CODE_CONTEXT = re.compile(r"(?:zones?|secteurs?)\s*$", re.IGNORECASE)
_CLAUSE_SEPARATOR = re.compile(r"[;:]|[.,](?=\s|$)|\s(?:et|sauf|ou|mais)\s", re.IGNORECASE)
"""Satzteile; Dezimalzahlen („3,50“) haben kein Leerzeichen nach dem Komma und bleiben ganz."""
_FILLER = re.compile(r"\b(?:dans|en|les?|la|du|des|de|d'|sous-secteurs?|secteurs?|zones?)\b", re.IGNORECASE)


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
    sources: tuple[int, ...] = ()
    """Nummern der Regeln in der Antwort des Modells, aus denen diese Regel entstand (Gegenprüfung)."""


@dataclass(frozen=True)
class DocumentPages:
    """Welche Originalseiten in welchem PDF an das Modell gingen, in Reihenfolge."""

    general: list[int]
    chapter: list[int]
    extra: list[int] = field(default_factory=list)
    """Zusatzseiten der Nachsuche (drittes PDF, PLAN_G2_VOLLSTAENDIGKEIT 3.6)."""

    def original_page(self, document: str, position: int) -> int | None:
        pages = {"general": self.general, "extra": self.extra}.get(document, self.chapter)
        return pages[position - 1] if 1 <= position <= len(pages) else None


def match_sector(value: str, sectors: Iterable[str]) -> str | None:
    """Sektor der Antwort einem angefragten Sektor zuordnen: „secteur UBa“ → „Uba“, wenn eindeutig. Zuletzt
    ohne Leer- und Satzzeichen, damit „Lot 12“ das angefragte Lot `Lot-12` eines Zusatzdokuments trifft
    (AN3)."""
    candidate = _SECTOR_PREFIX.sub("", value.strip())
    requested = list(sectors)
    if candidate in requested:
        return candidate
    folded = [s for s in requested if s.lower() == candidate.lower()]
    if folded:
        return folded[0] if len(folded) == 1 else None
    compact = [s for s in requested if _compact(s) == _compact(candidate)]
    return compact[0] if len(compact) == 1 else None


def _compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", value).lower()


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


def _sector_mentions(quote: str, sectors: Iterable[str]) -> list[tuple[int, int, str]]:
    """Nennungen angefragter Sektoren im Zitat (Groß- und Kleinschreibung zählt: „Ub“ ist nicht „UB“).
    Einbuchstabige Codes („A“, „N“) nur nach „zone“ oder „secteur“, sonst wäre jedes „A“ ein Sektor."""
    ordered = sorted(set(sectors), key=len, reverse=True)
    if not ordered:
        return []
    pattern = re.compile(
        r"(?<![0-9A-Za-zÀ-ÿ])(" + "|".join(re.escape(s) for s in ordered) + r")(?![0-9A-Za-zÀ-ÿ])"
    )
    mentions: list[tuple[int, int, str]] = []
    for match in pattern.finditer(quote):
        code = match.group(1)
        if len(code) == 1 and not _SHORT_CODE_CONTEXT.search(
            quote[max(0, match.start() - 20) : match.start()]
        ):
            continue
        mentions.append((match.start(), match.end(), code))
    return mentions


def _clauses(quote: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for separator in _CLAUSE_SEPARATOR.finditer(quote):
        spans.append((start, separator.start()))
        start = separator.end()
    spans.append((start, len(quote)))
    return spans


def foreign_sector(sector: str, sectors: Iterable[str], quote: str, params: Mapping[str, Any]) -> str | None:
    """Anderer Sektor, für den ein Zahlenwert im Zitat gilt, wenn er nicht (auch) für den Sektor der Regel
    gilt.

    Zugeordnet wird über Satzteile: Ein Wert gilt für die Sektoren seines Satzteils, sonst des nächsten
    vorangehenden Satzteils mit Sektor; angrenzende reine Aufzählungen („zones Ub et Uba“) zählen mit.
    „5 mètres en zone Ub et de 3 mètres dans le secteur Uba“ belegt für Ub nur 5 m, „En zone Ub, le recul est
    de 5 m, sauf dans le secteur Uba où il est de 3 m“ ebenso. Nennt das Zitat keinen anderen angefragten
    Sektor, gibt es nichts zu prüfen."""
    mentions = _sector_mentions(quote, sectors)
    if not any(code != sector for _, _, code in mentions):
        return None
    spans = _clauses(quote)
    codes: list[set[str]] = [{c for s, _, c in mentions if start <= s < end} for start, end in spans]

    def only_codes(index: int) -> bool:
        start, end = spans[index]
        rest = quote[start:end]
        for code in codes[index]:
            rest = re.sub(rf"(?<![0-9A-Za-zÀ-ÿ]){re.escape(code)}(?![0-9A-Za-zÀ-ÿ])", " ", rest)
        return bool(codes[index]) and not _FILLER.sub(" ", rest).strip(" ,.;:()-–")

    def governing(index: int) -> set[str]:
        anchor: int | None = index if codes[index] else None
        if anchor is None:
            anchor = next((i for i in range(index - 1, -1, -1) if codes[i]), None)
        if anchor is None:
            anchor = next((i for i in range(index + 1, len(spans)) if codes[i]), None)
        if anchor is None:
            return set()
        result = set(codes[anchor])
        for step in (-1, 1):
            neighbour = anchor + step
            while 0 <= neighbour < len(spans) and only_codes(neighbour):
                result |= codes[neighbour]
                neighbour += step
        return result

    for name, value in params.items():
        if not isinstance(value, int | float) or isinstance(value, bool):
            continue
        assigned = [
            governing(next(i for i, (s, e) in enumerate(spans) if s <= start <= e))
            for start, _ in value_positions(name, float(value), quote)
        ]
        if not assigned or any(not group or sector in group for group in assigned):
            continue
        return sorted(assigned[0])[0]
    return None


def assess_rule(
    rule: ExtractedRule, sectors: set[str], documents: DocumentPages, page_texts: dict[int, str]
) -> AssessedRule | None:
    """Schranken für eine Regel. None, wenn der Sektor nicht angefragt war oder ein Hinweis unbelegt ist."""
    sector = match_sector(rule.sector, sectors)
    if sector is None:
        return None
    quote = _check_quote(rule, documents, page_texts)
    base = AssessedRule(
        sector=sector,
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
        if not quote.verified:
            return replace(base, reason="not_regulated_unproven", detail=quote.reason)
        if not states_not_regulated(rule.quote):
            # Ein beliebiger echter Satz belegt nicht, dass nichts geregelt ist (Abstand 0 m in G3)
            return replace(base, reason="not_regulated_unproven", detail="no_marker")
        return replace(base, status="not_regulated")
    if rule.duplicate_params:
        return replace(base, reason="invalid_params", detail="duplicate:" + ",".join(rule.duplicate_params))
    try:
        params = validate_params(rule.kind, rule.params)
    except ParamProblem as problem:
        return replace(base, reason=problem.reason, detail=problem.detail)
    if not quote.verified:
        return replace(base, params=params, reason="quote_unverified", detail=quote.reason)
    numeric = {
        name: float(value)
        for name, value in params.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    missing = values_in_quote(numeric, rule.quote)
    if missing:
        # Belegtes Zitat, aber der Wert steht nicht darin: der Wert könnte erfunden oder verwechselt sein
        return replace(base, params=params, reason="value_not_in_quote", detail=",".join(missing))
    other = foreign_sector(sector, sectors, rule.quote, numeric)
    if other is not None:
        return replace(base, params=params, reason="sector_mismatch", detail=other)
    return replace(base, status="effective", params=params)


Key = tuple[str, str, str]


def rule_key(sector: str, kind: str, building_kind: str) -> Key:
    # „any“ gilt auch für das Hauptgebäude; so gilt dieselbe Regel als eine, auch wenn einmal „main“ und
    # einmal „any“ geschrieben wird
    return (sector, kind, "main" if building_kind == "any" else building_kind)


def _key(rule: AssessedRule) -> Key:
    return rule_key(rule.sector, rule.kind, rule.building_kind)


def _alternative(rule: AssessedRule) -> dict[str, Any]:
    return {"status": rule.status, "reason": rule.reason, "params": rule.params, "page": rule.page}


def collapse(rules: Iterable[AssessedRule]) -> list[AssessedRule]:
    """Eine Regel je Schlüssel. Mehrere gleichwertige Nennungen: die am besten belegte; widersprüchliche:
    `unknown` („ambiguous“). Hinweise bleiben einzeln, gleiche Fundstellen nur einmal."""
    grouped: dict[Key, list[AssessedRule]] = defaultdict(list)
    hints: dict[tuple[str, str, str], AssessedRule] = {}
    for rule in rules:
        if rule.status == "text_only":
            hints.setdefault((rule.sector, str(rule.page), normalize(rule.quote or "")[:80]), rule)
            continue
        grouped[_key(rule)].append(rule)
    result: list[AssessedRule] = []
    for key in sorted(grouped):
        group = grouped[key]
        first = group[0]
        building_kind = "any" if all(r.building_kind == "any" for r in group) else key[2]
        if all(r.status == first.status and params_equal(r.params, first.params) for r in group[1:]):
            best = max(group, key=lambda r: (r.quote_verified, r.similarity))
            result.append(
                replace(
                    best,
                    building_kind=building_kind,
                    confidence=min(r.confidence for r in group),
                    sources=tuple(sorted(s for r in group for s in r.sources)),
                )
            )
        else:
            result.append(
                replace(
                    first,
                    building_kind=building_kind,
                    status="unknown",
                    reason="ambiguous",
                    params={},
                    alternatives=[_alternative(r) for r in group],
                )
            )
    return result + list(hints.values())


def claim_for(number: int, rule: ExtractedRule, sectors: Iterable[str]) -> dict[str, Any] | None:
    """Regel der Auswertung als Frage an die Gegenprüfung: ohne Werte. Die Fragen hängen nur von der Antwort
    des Modells ab, nicht von den Schranken; eine Neubewertung kann die gespeicherte Gegenprüfung nutzen."""
    sector = match_sector(rule.sector, sectors)
    if sector is None or rule.kind == "text_only" or rule.status not in ("regulated", "not_regulated"):
        return None
    return {
        "claim": number,
        "sector": sector,
        "kind": rule.kind,
        "building_kind": rule.building_kind,
        "document": rule.document,
        "page": rule.page,
        "quote": rule.quote,
    }


def verify(rules: list[AssessedRule], checks: Mapping[int, list[VerificationCheck]]) -> list[AssessedRule]:
    """Ergebnis der Gegenprüfung anwenden: Eine wirksame oder belegt nicht geregelte Regel bleibt nur, wenn
    jede ihrer Quellen in der Gegenprüfung denselben Status und dieselben Werte ergibt."""
    result: list[AssessedRule] = []
    for rule in rules:
        if rule.status not in ("effective", "not_regulated"):
            result.append(rule)
            continue
        answers = [answer for source in rule.sources for answer in checks.get(source, [])]
        answered = bool(rule.sources) and all(checks.get(source) for source in rule.sources)
        if answered and all(_confirms(rule, answer) for answer in answers):
            result.append(rule)
            continue
        result.append(
            replace(
                rule,
                status="unknown",
                reason="runs_disagree",
                params={},
                alternatives=[_alternative(rule)]
                + ([{"status": a.status, "params": a.params} for a in answers] or [{"status": "absent"}]),
            )
        )
    return result


def _confirms(claim: AssessedRule, answer: VerificationCheck) -> bool:
    if claim.status == "not_regulated":
        return answer.status == "not_regulated"
    if answer.status != "regulated" or answer.duplicate_params:
        return False
    try:
        params = validate_params(claim.kind, answer.params)
    except ParamProblem:
        return False
    return params_equal(claim.params, params)


def _open_rule(key: Key, reason: str, detail: str | None) -> AssessedRule:
    return AssessedRule(
        sector=key[0],
        kind=key[1],
        building_kind=key[2],
        status="unknown",
        reason=reason,
        params={},
        page=None,
        quote=None,
        quote_verified=False,
        similarity=0.0,
        confidence=0.0,
        notes="",
        detail=detail,
    )


def _gap_result(
    key: Key,
    existing: AssessedRule | None,
    found: list[AssessedRule],
    absent: Mapping[Key, str],
    not_expressible: Mapping[Key, str | None],
) -> AssessedRule | None:
    candidate = collapse(found)[0] if found else None
    if candidate is not None and (
        candidate.status in ("effective", "not_regulated") or candidate.reason == "ambiguous"
    ):
        return candidate
    if key in not_expressible:
        return _open_rule(key, "not_expressible", not_expressible[key])
    if existing is not None and existing.quote:
        # Der Befund aus Auswertung und Gegenprüfung bleibt sichtbar, wenn die Nachsuche ihn nicht klärt
        return existing
    if candidate is not None:
        return candidate
    if key in absent and key[1] in MANDATORY_KINDS and key[2] == "main":
        return _open_rule(key, "not_found_after_search", absent[key])
    return existing


def fill_gaps(
    rules: list[AssessedRule],
    found: list[AssessedRule],
    gap_keys: set[Key],
    absent: Mapping[Key, str],
    not_expressible: Mapping[Key, str | None],
) -> list[AssessedRule]:
    """Ergebnis der Nachsuche einarbeiten (PLAN_G2_VOLLSTAENDIGKEIT 3.6).

    Ein bestätigter Fund für eine Lücke ersetzt die offene Regel – `collapse` hielte beide für einen
    Widerspruch. Funde für Schlüssel, die keine Lücke waren (aus offenen Textstellen), gehen mit den
    vorhandenen Regeln durch `collapse`: gleiche Werte bleiben eine Regel, andere werden `ambiguous`.
    Nicht gefundene Pflichtarten werden `not_found_after_search`, nicht abbildbare `not_expressible`."""
    by_key: dict[Key, list[AssessedRule]] = defaultdict(list)
    for rule in found:
        if rule.status != "text_only":
            by_key[_key(rule)].append(rule)
    kept: list[AssessedRule] = []
    seen: set[Key] = set()
    for rule in rules:
        if rule.status == "text_only":
            kept.append(rule)
            continue
        key = _key(rule)
        seen.add(key)
        result = (
            _gap_result(key, rule, by_key.get(key, []), absent, not_expressible) if key in gap_keys else rule
        )
        kept.append(result or rule)
    for key in sorted(gap_keys - seen):
        result = _gap_result(key, None, by_key.get(key, []), absent, not_expressible)
        if result is not None:
            kept.append(result)
    # Nur bestätigte Funde: Ein Fund, der Schranken oder Gegenprüfung nicht besteht, stellt keine geprüfte
    # Regel in Frage
    others = [
        rule
        for key, group in by_key.items()
        if key not in gap_keys
        for rule in group
        if rule.status in ("effective", "not_regulated")
    ]
    # Ein Hinweis zu einer Stelle, die schon ein Hinweis belegt, käme doppelt (Staffel aus Auswertung und
    # Nachsuche mit anderem Zitatbeginn); `collapse` vergleicht nur den Anfang des Zitats
    hints: list[AssessedRule] = []
    for hint in (rule for rule in found if rule.status == "text_only"):
        known = [
            r
            for r in kept + hints
            if r.status == "text_only" and r.sector == hint.sector and r.page == hint.page
        ]
        if not any(quotes_overlap(r.quote, hint.quote) for r in known):
            hints.append(hint)
    return collapse(kept + others + hints)


def complete(rules: list[AssessedRule], sectors: list[str]) -> list[AssessedRule]:
    """Fehlende Pflichtarten als `unknown` („missing“) ergänzen und fachlich sortieren."""
    result = list(rules)
    covered = {(r.sector, r.kind) for r in rules if r.building_kind in ("main", "any")}
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
