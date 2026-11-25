"""Auswertung eines Zonenkapitels: Aufrufe des Sprachmodells, Schranken, neue Regelwerksversionen (Plan 3.4).

Ablauf: Auswertung (Lauf 1) → Schranken → Gegenprüfung (Lauf 2, docs/ANNAHMEN.md RW19) → Nachsuche für
Lücken und offene Textstellen (Lauf 3, docs/PLAN_G2_VOLLSTAENDIGKEIT.md) → Regelwerk je Sektor.
Datenbanktransaktionen umschließen nie einen Aufruf des Sprachmodells über OpenRouter (Minuten). Jeder
Aufruf wird sofort mit Kosten gespeichert; eine Wiederholung nutzt bereits erfolgreiche Teile derselben
Eingabe. Liegen alle Teile vor (z. B. nach einer neuen Version der Schranken), wird ohne Aufruf neu bewertet.
"""

import hashlib
import json
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.rules import pdf
from app.rules.domain import ENGINE_VERSION, lexicon
from app.rules.domain.assess import (
    AssessedRule,
    DocumentPages,
    Key,
    assess_rule,
    claim_for,
    collapse,
    complete,
    coverage,
    fill_gaps,
    rule_key,
    verify,
)
from app.rules.domain.chapters import CHAPTER_MAX_PAGES
from app.rules.domain.extraction import (
    DocumentKind,
    ExtractedRule,
    ExtractionError,
    ExtractionRequest,
    GapSearchResult,
    RuleExtractor,
    VerificationCheck,
    document_kind,
    parse_gaps,
    parse_output,
    parse_verification,
    prompt_version,
)
from app.rules.domain.kinds import MANDATORY_BY_SCOPE, MANDATORY_KINDS, RuleScope
from app.rules.domain.passages import Passage, chapter_passages, for_search
from app.rules.domain.passages import coverage as passage_coverage
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    RegulationChapterScope,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)
from app.rules.runs import RUNNING_STALE_AFTER, input_hash, month_cost, ocr_stamp

log = get_logger("rules_extract")
ACTOR = "system:rules_extract"
SessionFactory = Callable[[], AbstractContextManager[Session]]
CLAIMS_PER_CALL = 30
"""Regeln je Aufruf der Gegenprüfung; kleinere Antworten, weniger Risiko für `max_tokens`."""
RUN_EXTRACTION, RUN_VERIFICATION, RUN_GAP_SEARCH = 1, 2, 3
PASSAGES_FOR_SEARCH = 120
"""Höchstens so viele offene Textstellen gehen an die Nachsuche (mit Zahl zuerst)."""
SKIP_GAP = ("graphic_reference",)
"""Offene Regeln, die die Nachsuche nicht klären kann: Der Wert steht im Plan, nicht im Text."""
PDF_REQUEST_MAX_BYTES = 20 * 1024 * 1024
"""Größere Seitenauszüge (Scans mit 0,3–1 MB je Seite) gehen als erkannter Text statt als PDF; die Anbieter
nehmen etwa 32 MB je Anfrage, Base64 macht ein Drittel mehr (AN7, PLAN_AN7_SCAN 3.4)."""


class RetryableExtractionError(Exception):
    """Der Job soll es erneut versuchen (Überlastung, Netz, Zeitbudget des Jobs)."""


@dataclass(frozen=True)
class ChapterOutcome:
    status: str
    """`succeeded`, `skipped`, `failed`, `budget_exceeded`, `not_configured`."""
    detail: str | None = None
    cost_usd: float = 0.0
    counts: dict[str, int] | None = None


class _Stop(Exception):
    """Auswertung endet ohne Wiederholung; das Kapitel steht danach auf `failed` mit `error`."""

    def __init__(self, outcome: ChapterOutcome, error: str) -> None:
        super().__init__(error)
        self.outcome = outcome
        self.error = error


def plan_complete(session: Session, plan_id: uuid.UUID) -> bool:
    """Alle Kapitel mit Sektoren sind ausgewertet (Grundlage für den Rückfall auf den vorigen Planstand)."""
    chapters = session.execute(
        select(RegulationChapter.status).where(
            RegulationChapter.land_use_plan_id == plan_id, func.cardinality(RegulationChapter.sectors) > 0
        )
    ).scalars()
    statuses = list(chapters)
    return bool(statuses) and all(status == "succeeded" for status in statuses)


def release_fallback(session: Session, plan_id: uuid.UUID) -> None:
    """Ist der Planstand vollständig ausgewertet, sehen Kunden ihn statt des vorigen."""
    if plan_complete(session, plan_id):
        session.execute(
            update(RulesCommune)
            .where(RulesCommune.land_use_plan_id == plan_id)
            .values(fallback_land_use_plan_id=None)
        )


def scope_state(
    session: Session, chapter: RegulationChapter, scope: RuleScope, *, create: bool = False
) -> RegulationChapter | RegulationChapterScope | None:
    """Stand der Auswertung im Umfang: `house` am Kapitel selbst, sonst in `regulation_chapter_scope`
    (PLAN_REGELDIENST 3.2). Beide tragen `status`, `input_hash`, `engine_version`, `error`, `updated_at`."""
    if scope == "house":
        return chapter
    state = session.get(RegulationChapterScope, (chapter.id, scope))
    if state is None and create:
        state = RegulationChapterScope(chapter_id=chapter.id, scope=scope, status="pending")
        session.add(state)
        session.flush()
    return state


@dataclass
class _Calls:
    """Aufrufe eines Kapitels mit Wiederverwendung, Budget, Zeitbudget und Kostenerfassung."""

    sessions: SessionFactory
    settings: Settings
    chapter_id: uuid.UUID
    digest: str
    text_digest: str
    """Kennung der Aufrufe, die im PDF-Modus als Text gingen (`input_hash(as_text=True)`); im Textmodus
    gleich `digest`."""
    source_sha256: str
    extractor_factory: Callable[[], RuleExtractor]
    final_attempt: bool
    deadline: float | None
    storage_key: str
    chapter_code: str
    chapter_pages: list[int]
    general_pages: list[int]
    reusable: dict[tuple[int, str], tuple[uuid.UUID, dict[str, Any], bool]]
    """Gespeicherte Antworten je Aufruf: Lauf, Antwort und ob die Eingabe als Text ging."""
    split: set[tuple[int, str]]
    page_texts: dict[int, str] = field(default_factory=dict)
    """Textschicht je Seite (`source_page`); dieselbe, gegen die die Zitate geprüft werden."""
    document_texts: dict[int, str] = field(default_factory=dict)
    """Textschicht aller Seiten des Dokuments (Nachsuche: Zusatzseiten suchen und Zitate darauf prüfen)."""
    extra_candidates: list[int] = field(default_factory=list)
    """Seiten außerhalb des Kapitels, der gesendeten allgemeinen Seiten und der Kapitel anderer Zonen."""
    document_kind: DocumentKind = "plu"
    scan_pages: frozenset[int] = frozenset()
    """Seiten, deren Text per Texterkennung gelesen wurde (AN7)."""
    ocr: str | None = None
    scope: RuleScope = "house"
    """Umfang der Auswertung (PLAN_REGELDIENST 3.1): Prompt, Pflichtarten und Ablage des Ergebnisses."""
    cost: float = 0.0
    model: str = ""
    run_ids: list[uuid.UUID] = field(default_factory=list)
    text_used: bool = False
    """Mindestens ein Aufruf ging als Text: Das Kapitel trägt dann `text_digest`."""
    in_flight: tuple[int, str] | None = None
    _data: bytes | None = None
    _pdfs: tuple[bytes, bytes | None] | None = None

    def _source(self) -> bytes:
        if self._data is None:
            self._data = storage.get_bytes(self.storage_key)
        return self._data

    def _documents(self) -> tuple[bytes, bytes | None]:
        if self._pdfs is None:
            data = self._source()
            general = pdf.extract_pages(data, self.general_pages) if self.general_pages else None
            self._pdfs = (pdf.extract_pages(data, self.chapter_pages), general)
        return self._pdfs

    def _pages_text(self, numbers: list[int]) -> str:
        """Textschicht statt PDF (PU12). Die Marken zählen wie im PDF-Auszug ab 1, damit die Rückrechnung
        der Seiten (Spez. 5.2.3) gleich bleibt."""
        texts = self.document_texts or self.page_texts
        return "\n\n".join(
            f"=== page {position} ===\n{texts.get(page, '').strip()}"
            for position, page in enumerate(numbers, start=1)
        )

    def _texts(self) -> tuple[str, str | None]:
        general = self._pages_text(self.general_pages) if self.general_pages else None
        return self._pages_text(self.chapter_pages), general

    @property
    def mandatory(self) -> tuple[str, ...]:
        return MANDATORY_BY_SCOPE[self.scope]

    def _set_chapter(self, status: str, error: str | None = None) -> None:
        with self.sessions() as session:
            chapter = session.get(RegulationChapter, self.chapter_id)
            current = scope_state(session, chapter, self.scope, create=True) if chapter is not None else None
            if current is not None:
                current.status, current.error, current.updated_at = status, error, utcnow()
                session.commit()

    def _before_call(self) -> None:
        if self.settings.openrouter_api_key is None:
            raise _Stop(ChapterOutcome("not_configured", None, self.cost), "not_configured")
        with self.sessions() as session:
            spent = month_cost(session)
        if spent >= self.settings.rules_budget_month_usd:
            log.error(
                "rules_budget_exceeded",
                spent_usd=round(spent, 2),
                budget_usd=self.settings.rules_budget_month_usd,
            )
            raise _Stop(ChapterOutcome("budget_exceeded", f"{spent:.2f}", self.cost), "budget_exceeded")
        if (
            self.deadline is not None
            and time.monotonic() + self.settings.rules_request_timeout_seconds > self.deadline
        ):
            # Lieber neu einplanen als mitten im Aufruf vom Zeitlimit des Jobs abgebrochen werden
            self._set_chapter("pending")
            raise RetryableExtractionError("time_budget")

    def _record(self, run_no: int, part: str, *, as_text: bool = False, **values: Any) -> uuid.UUID:
        with self.sessions() as session:
            run = RuleExtractionRun(
                chapter_id=self.chapter_id,
                run_no=run_no,
                part=part[:200],
                input_hash=self.text_digest if as_text else self.digest,
                prompt_version=prompt_version(self.scope),
                scope=self.scope,
                created_by=ACTOR,
                **values,
            )
            session.add(run)
            session.commit()
            return run.id

    def record_interrupted(self, error: str) -> None:
        """Aufruf durch Zeitlimit oder Absturz abgebrochen: sichtbar machen (Kosten unbekannt)."""
        if self.in_flight is not None:
            run_no, part = self.in_flight
            self._record(run_no, part, model=self.settings.rules_model, status="failed", error=error[:300])
            self.in_flight = None

    def run(
        self,
        run_no: int,
        part: str,
        sectors: list[str],
        claims: list[dict[str, Any]] | None = None,
        gaps: dict[str, Any] | None = None,
        extra_pages: list[int] | None = None,
    ) -> Any:
        """Antwort eines Teils; `None`, wenn der Teil für eine Antwort zu groß ist (`max_tokens`)."""
        key = (run_no, part)
        if key in self.reusable:
            run_id, output, as_text = self.reusable[key]
            self.text_used |= as_text
            self.run_ids.append(run_id)
            return output
        if key in self.split:
            return None
        self._before_call()
        chapter_text: str | None = None
        general_text: str | None = None
        extra_text: str | None = None
        extra_pdf: bytes | None = None
        extra = extra_pages or []
        as_text = self.settings.rules_input == "text"
        if as_text:
            chapter_text, general_text = self._texts()
            chapter_pdf, general_pdf = b"", None
            extra_text = self._pages_text(extra) if extra else None
        else:
            chapter_pdf, general_pdf = self._documents()
            extra_pdf = pdf.extract_pages(self._source(), extra) if extra else None
            size = len(chapter_pdf) + len(general_pdf or b"") + len(extra_pdf or b"")
            if size > PDF_REQUEST_MAX_BYTES:
                log.info("rules_input_as_text", chapter=str(self.chapter_id), part=part, pdf_bytes=size)
                chapter_text, general_text = self._texts()
                chapter_pdf, general_pdf, extra_pdf = b"", None, None
                extra_text = self._pages_text(extra) if extra else None
                as_text = True
        request = ExtractionRequest(
            chapter_code=self.chapter_code,
            sectors=sectors,
            chapter_pdf=chapter_pdf,
            chapter_pages=self.chapter_pages,
            general_pdf=general_pdf,
            general_pages=self.general_pages,
            claims=claims,
            document_kind=self.document_kind,
            chapter_text=chapter_text,
            general_text=general_text,
            gaps=gaps,
            extra_pdf=extra_pdf,
            extra_pages=extra,
            extra_text=extra_text,
            scope=self.scope,
        )
        self.in_flight = key
        try:
            response = self.extractor_factory().extract(request)
        except ExtractionError as exc:
            self.in_flight = None
            self.cost += _cost(self.settings, exc.usage)
            self._record(
                run_no,
                part,
                as_text=as_text,
                model=self.settings.rules_model,
                status="failed",
                error=exc.reason[:300],
                usage=exc.usage,
                cost_usd=_cost(self.settings, exc.usage),
            )
            if exc.reason == "max_tokens":
                self.split.add(key)
                return None
            if exc.retryable and not self.final_attempt:
                self._set_chapter("pending")
                raise RetryableExtractionError(exc.reason) from exc
            raise _Stop(ChapterOutcome("failed", exc.reason, self.cost), exc.reason) from exc
        self.in_flight = None
        self.cost += response.cost_usd
        self.model = response.model
        self.text_used |= as_text
        run_id = self._record(
            run_no,
            part,
            as_text=as_text,
            model=response.model,
            status="succeeded",
            stop_reason=response.stop_reason,
            served_by_fallback=response.served_by_fallback,
            usage=response.usage,
            cost_usd=response.cost_usd,
            duration_ms=response.duration_ms,
            request_id=response.request_id,
            output=response.output,
        )
        self.reusable[key] = (run_id, response.output, as_text)
        self.run_ids.append(run_id)
        return response.output


def _halves(items: list[Any]) -> list[list[Any]]:
    middle = (len(items) + 1) // 2
    return [items[:middle], items[middle:]]


def _extract(calls: _Calls, sectors: list[str]) -> list[ExtractedRule]:
    """Lauf 1. Ist die Antwort für alle Sektoren zu lang, werden die Sektoren auf mehrere Aufrufe verteilt."""
    rules: list[ExtractedRule] = []
    queue = [sectors]
    while queue:
        group = queue.pop(0)
        output = calls.run(RUN_EXTRACTION, "sectors:" + ",".join(group), group)
        if output is None:
            if len(group) == 1:
                raise _Stop(ChapterOutcome("failed", "max_tokens", calls.cost), "max_tokens")
            queue[0:0] = _halves(group)
            continue
        try:
            rules.extend(parse_output(output))
        except ValueError:
            continue
    return rules


def _verify(calls: _Calls, claims: dict[int, dict[str, Any]]) -> dict[int, list[VerificationCheck]]:
    """Lauf 2: Gegenprüfung in Teilen. Ein einzelner Eintrag ohne Antwort bleibt ungeprüft (`unknown`)."""
    checks: dict[int, list[VerificationCheck]] = {}
    numbers = sorted(claims)
    queue = [numbers[i : i + CLAIMS_PER_CALL] for i in range(0, len(numbers), CLAIMS_PER_CALL)]
    while queue:
        group = queue.pop(0)
        items = [claims[n] for n in group]
        digest = hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        sectors = sorted({str(item["sector"]) for item in items})
        output = calls.run(RUN_VERIFICATION, f"verify:{digest[:16]}", sectors, items)
        if output is None:
            if len(group) > 1:
                queue[0:0] = _halves(group)
            continue
        try:
            parsed = parse_verification(output)
        except ValueError:
            parsed = {}
        for number in group:
            checks[number] = parsed.get(number, [])
    return checks


@dataclass(frozen=True)
class _Gap:
    number: int
    key: Key
    sector: str
    kind: str
    building_kind: str
    previous: AssessedRule | None

    def request(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "gap": self.number,
            "sector": self.sector,
            "kind": self.kind,
            "building_kind": self.building_kind,
            "terms": list(lexicon.terms_for(self.kind, self.building_kind)),
            "article": lexicon.ARTICLES.get(self.kind),
        }
        if self.previous is not None and self.previous.quote:
            # Offene Regeln tragen ihre Werte nur noch unter den Alternativen (Gegenprüfung, `ambiguous`)
            values: dict[str, Any] = dict(self.previous.params)
            for alternative in self.previous.alternatives:
                if not values and alternative.get("params"):
                    values = dict(alternative["params"])
            item["previous"] = {
                "reason": self.previous.reason,
                "quote": self.previous.quote,
                "params": values,
            }
        return item


@dataclass(frozen=True)
class SearchOutcome:
    """Abdeckung der Textstellen und Stand der Nachsuche (PLAN_G2_VOLLSTAENDIGKEIT 3.3, 3.7)."""

    total: int = 0
    assigned: int = 0
    open: list[Passage] = field(default_factory=list)
    dismissed: list[tuple[Passage, str]] = field(default_factory=list)
    searched: bool = False

    def counts(self) -> dict[str, int]:
        return {
            "passages_total": self.total,
            "passages_assigned": self.assigned,
            "passages_out_of_scope": len(self.dismissed),
            "passages_open": len(self.open),
            "gap_search": int(self.searched),
        }


def find_gaps(
    rules: list[AssessedRule], sectors: list[str], text: str, mandatory: tuple[str, ...] = MANDATORY_KINDS
) -> list[_Gap]:
    """Lücken nach der Gegenprüfung (PLAN_G2_VOLLSTAENDIGKEIT 3.5): Pflichtarten ohne Wert; im Text genannte
    weitere Arten und Baukörper ohne Regel; offene Regeln mit Zitat (ihr Befund geht mit)."""
    by_key = {rule_key(r.sector, r.kind, r.building_kind): r for r in rules if r.status != "text_only"}
    kinds = sorted(lexicon.kinds_mentioned(text) - set(mandatory))
    building_kinds = sorted(lexicon.building_kinds_mentioned(text))
    gaps: list[_Gap] = []
    for sector in sectors:
        wanted = [(kind, "main") for kind in mandatory] + [(kind, "any") for kind in kinds]
        wanted += [(kind, bk) for bk in building_kinds for kind in ("setback_side", "setback_rear")]
        wanted += [(r.kind, r.building_kind) for r in rules if r.sector == sector and r.status == "unknown"]
        seen: set[Key] = set()
        for kind, building_kind in wanted:
            key = rule_key(sector, kind, building_kind)
            if key in seen:
                continue
            seen.add(key)
            rule = by_key.get(key)
            if rule is not None and (
                rule.status in ("effective", "not_regulated") or rule.reason in SKIP_GAP
            ):
                continue
            general = by_key.get(rule_key(sector, kind, "main"))
            if building_kind in ("annex", "pool") and general is not None and general.building_kind == "any":
                continue  # Eine Regel für alle Baukörper gilt auch hier
            gaps.append(_Gap(len(gaps) + 1, key, sector, kind, building_kind, rule))
    return gaps


def _search_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    gaps, passages = payload["gaps"], payload["passages"]
    if len(gaps) + len(passages) <= 1:
        return []
    middle_gaps, middle_passages = (len(gaps) + 1) // 2, (len(passages) + 1) // 2
    return [
        {"gaps": gaps[:middle_gaps], "passages": passages[:middle_passages]},
        {"gaps": gaps[middle_gaps:], "passages": passages[middle_passages:]},
    ]


def _gap_search(
    calls: _Calls,
    sectors: list[str],
    first_number: int,
    rules: list[AssessedRule],
    page_texts: dict[int, str],
) -> tuple[list[AssessedRule], SearchOutcome]:
    """Nachsuche (Lauf 3) nach Auswertung und Gegenprüfung: Lücken und offene Textstellen gezielt fragen,
    Funde durch Schranken und Gegenprüfung, dann einarbeiten (PLAN_G2_VOLLSTAENDIGKEIT 3.5–3.7)."""
    passages = chapter_passages(page_texts, calls.chapter_pages)
    first = passage_coverage(passages, [(r.page, r.quote) for r in rules if r.quote], page_texts)
    if not calls.settings.rules_gap_search:
        return rules, SearchOutcome(first.total, first.assigned, first.open)
    text = "\n".join(page_texts.get(p, "") for p in calls.chapter_pages + calls.general_pages)
    gaps = find_gaps(rules, sectors, text, calls.mandatory)
    asked = for_search(first.open, PASSAGES_FOR_SEARCH)
    if not gaps and not asked:
        return rules, SearchOutcome(first.total, first.assigned, first.open)
    terms = sorted({term for gap in gaps for term in lexicon.terms_for(gap.kind, gap.building_kind)})
    extra = lexicon.extra_pages(
        calls.document_texts,
        calls.extra_candidates,
        terms,
        "\n".join(page_texts.get(p, "") for p in calls.chapter_pages),
        calls.settings.rules_gap_extra_pages_max,
    )
    position = {page: i for i, page in enumerate(calls.chapter_pages, start=1)}
    payload = {
        "gaps": [gap.request() for gap in gaps],
        "passages": [
            {"passage": i, "page": position.get(p.page, p.page), "text": p.short}
            for i, p in enumerate(asked, 1)
        ],
    }
    answers = GapSearchResult({}, {})
    queue = [payload]
    while queue:
        part = queue.pop(0)
        digest = hashlib.sha256(
            json.dumps([part, extra], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        output = calls.run(RUN_GAP_SEARCH, f"gaps:{digest[:16]}", sectors, gaps=part, extra_pages=extra)
        if output is None:
            queue[0:0] = _search_parts(part)
            continue
        try:
            parsed = parse_gaps(output, calls.scope)
        except ValueError:
            continue
        answers.gaps.update(parsed.gaps)
        answers.passages.update(parsed.passages)

    # Funde durch dieselben Schranken und die Gegenprüfung; Nummern hinter denen der Auswertung
    documents = DocumentPages(general=calls.general_pages, chapter=calls.chapter_pages, extra=extra)
    texts = page_texts | {p: calls.document_texts.get(p, "") for p in extra}
    extracted = [r for a in answers.gaps.values() for r in a.rules]
    extracted += [r for a in answers.passages.values() if a.verdict != "out_of_scope" for r in a.rules]
    assessed: list[AssessedRule] = []
    for number, extracted_rule in enumerate(extracted, start=first_number):
        result = assess_rule(extracted_rule, set(sectors), documents, texts)
        if result is not None:
            assessed.append(replace(result, sources=(number,)))
    found = collapse(assessed)
    if calls.settings.rules_runs >= 2:
        claims = {
            number: claim
            for number, extracted_rule in enumerate(extracted, start=first_number)
            if (claim := claim_for(number, extracted_rule, sectors)) is not None
        }
        found = verify(found, _verify(calls, claims) if claims else {})

    by_gap = {gap.number: gap for gap in gaps}
    absent: dict[Key, str] = {}
    not_expressible: dict[Key, str | None] = {}
    for answer in answers.gaps.values():
        gap = by_gap.get(answer.gap)
        if gap is None:
            continue
        if answer.verdict == "absent":
            absent[gap.key] = (answer.searched or ", ".join(lexicon.terms_for(gap.kind, gap.building_kind)))[
                :500
            ]
        elif answer.verdict == "not_expressible":
            page = next((r.page for r in answer.rules), None)
            original = (
                documents.original_page(answer.rules[0].document, page) if page and answer.rules else None
            )
            not_expressible[gap.key] = str(original) if original else None
    merged = fill_gaps(rules, found, {gap.key for gap in gaps}, absent, not_expressible, calls.mandatory)

    dismissed = [
        (passage, verdict.reason)
        for i, passage in enumerate(asked, 1)
        if (verdict := answers.passages.get(i)) is not None and verdict.verdict == "out_of_scope"
    ]
    final = passage_coverage(passages, [(r.page, r.quote) for r in merged if r.quote], texts)
    dismissed_ids = {id(passage) for passage, _ in dismissed}
    still_open = [p for p in final.open if id(p) not in dismissed_ids]
    return merged, SearchOutcome(final.total, final.assigned, still_open, dismissed, searched=True)


def extract_chapter(
    sessions: SessionFactory,
    settings: Settings,
    chapter_id: uuid.UUID,
    extractor_factory: Callable[[], RuleExtractor],
    *,
    force: bool = False,
    final_attempt: bool = True,
    skip_if_running: bool = True,
    deadline: float | None = None,
    scope: RuleScope = "house",
) -> ChapterOutcome:
    """`deadline` (Zeitpunkt aus `time.monotonic`): kein neuer Aufruf, der danach enden könnte. `scope`:
    Umfang `collectif` nur über die Kommandozeile, Stand in `regulation_chapter_scope` (PLAN_REGELDIENST)."""
    # 1. Lesen
    with sessions() as session:
        chapter = session.get(RegulationChapter, chapter_id)
        if chapter is None:
            return ChapterOutcome("skipped", "chapter_missing")
        plan = session.get(LandUsePlan, chapter.land_use_plan_id)
        if plan is None or plan.status != "active":
            return ChapterOutcome("skipped", "plan_not_active")
        if not chapter.sectors:
            return ChapterOutcome("skipped", "no_sectors")
        source = session.get(SourceFile, chapter.source_file_id)
        assert source is not None
        chapter_pages = list(range(chapter.first_page, chapter.last_page + 1))
        general_pages = [p for p in chapter.general_pages if p not in set(chapter_pages)]
        if len(chapter_pages) + len(general_pages) > CHAPTER_MAX_PAGES:
            # Meist falsch erkannte Kapitelgrenzen; ein Aufruf wäre teuer und kaum auswertbar
            chapter.status, chapter.error, chapter.updated_at = "failed", "chapter_too_long", utcnow()
            session.commit()
            return ChapterOutcome("failed", "chapter_too_long")
        kind = document_kind(plan.du_type)
        if kind == "supplement" and scope != "house":
            return ChapterOutcome("skipped", "scope_not_supported")
        stamp = ocr_stamp(source)
        digest = input_hash(settings, source.sha256, chapter, kind, stamp, scope=scope)
        # Ging ein Auszug als Text, trägt das Kapitel diese Kennung; sie folgt der Texterkennung (SC06)
        text_digest = input_hash(settings, source.sha256, chapter, kind, stamp, as_text=True, scope=scope)
        state = scope_state(session, chapter, scope, create=True)
        assert state is not None
        if (
            not force
            and state.status == "succeeded"
            and state.input_hash in (digest, text_digest)
            and state.engine_version == ENGINE_VERSION
        ):
            return ChapterOutcome("skipped", "unchanged")
        if (
            skip_if_running
            and state.status == "extracting"
            and utcnow() - state.updated_at < RUNNING_STALE_AFTER
        ):
            # Ein anderer Job wertet gerade aus; ein zweiter Lauf kostete doppelt, auch mit `force`. Eine
            # Wiederholung desselben Jobs (nach Absturz oder Zeitüberschreitung) setzt skip_if_running=False
            return ChapterOutcome("skipped", "already_running")
        page_texts = {
            p.page: p.text
            for p in session.execute(
                select(SourcePage).where(
                    SourcePage.source_file_id == source.id, SourcePage.page.in_(chapter_pages + general_pages)
                )
            ).scalars()
        }
        scan_pages = frozenset(
            session.execute(
                select(SourcePage.page).where(
                    SourcePage.source_file_id == source.id, SourcePage.ocr_confidence.is_not(None)
                )
            ).scalars()
        )
        document_texts: dict[int, str] = {}
        extra_candidates: list[int] = []
        if settings.rules_gap_search and kind == "plu":
            # Nachsuche: Zusatzseiten nur außerhalb der Kapitel anderer Zonen (deren Werte gelten hier nicht)
            document_texts = {
                p.page: p.text
                for p in session.execute(
                    select(SourcePage).where(SourcePage.source_file_id == source.id)
                ).scalars()
            }
            zones = session.execute(
                select(RegulationChapter.first_page, RegulationChapter.last_page).where(
                    RegulationChapter.source_file_id == source.id, RegulationChapter.id != chapter.id
                )
            ).all()
            excluded = set(chapter_pages) | set(general_pages)
            excluded |= {page for first, last in zones for page in range(first, last + 1)}
            extra_candidates = sorted(set(document_texts) - excluded)
        reusable: dict[tuple[int, str], tuple[uuid.UUID, dict[str, Any], bool]] = {}
        split: set[tuple[int, str]] = set()
        if not force:
            for run in session.execute(
                select(RuleExtractionRun)
                .where(
                    RuleExtractionRun.chapter_id == chapter.id,
                    RuleExtractionRun.input_hash.in_((digest, text_digest)),
                )
                .order_by(RuleExtractionRun.created_at)
            ).scalars():
                if run.status == "succeeded" and run.output is not None:
                    reusable[(run.run_no, run.part)] = (run.id, run.output, run.input_hash == text_digest)
                elif run.error == "max_tokens":
                    split.add((run.run_no, run.part))
        state.status, state.error, state.updated_at = "extracting", None, utcnow()
        session.commit()
        sectors = sorted(chapter.sectors)
        calls = _Calls(
            sessions=sessions,
            settings=settings,
            chapter_id=chapter_id,
            digest=digest,
            text_digest=text_digest,
            source_sha256=source.sha256,
            extractor_factory=extractor_factory,
            final_attempt=final_attempt,
            deadline=deadline,
            storage_key=source.storage_key,
            chapter_code=chapter.code,
            chapter_pages=chapter_pages,
            general_pages=general_pages,
            reusable=reusable,
            split=split,
            page_texts=page_texts,
            document_texts=document_texts,
            extra_candidates=extra_candidates,
            document_kind=kind,
            scan_pages=scan_pages,
            ocr=stamp,
            scope=scope,
            model=settings.rules_model,
        )
        file_id, plan_id = source.id, plan.id

    try:
        return _evaluate(calls, sectors, page_texts, file_id, plan_id)
    except RetryableExtractionError:
        raise
    except _Stop as stop:
        calls._set_chapter("failed", stop.error)
        return stop.outcome
    except Exception as exc:
        # Zeitlimit des Jobs, Speicher, PDF, Datenbank: das Kapitel darf nicht auf `extracting` stehen bleiben
        error = f"interrupted:{type(exc).__name__}"
        calls.record_interrupted(error)
        calls._set_chapter("failed" if final_attempt else "pending", error if final_attempt else None)
        raise


def _evaluate(
    calls: _Calls, sectors: list[str], page_texts: dict[int, str], file_id: uuid.UUID, plan_id: uuid.UUID
) -> ChapterOutcome:
    # 2. Auswertung und Schranken
    extracted = _extract(calls, sectors)
    documents = DocumentPages(general=calls.general_pages, chapter=calls.chapter_pages)
    assessed: list[AssessedRule] = []
    dropped = 0
    for number, rule in enumerate(extracted, start=1):
        result = assess_rule(rule, set(sectors), documents, page_texts)
        if result is None:
            dropped += 1
            continue
        assessed.append(replace(result, sources=(number,)))
    rules = collapse(assessed)

    # 3. Gegenprüfung
    if calls.settings.rules_runs >= 2:
        claims = {
            number: claim
            for number, rule in enumerate(extracted, start=1)
            if (claim := claim_for(number, rule, sectors)) is not None
        }
        rules = verify(rules, _verify(calls, claims) if claims else {})
    # Nachsuche und Abdeckung nur für PLU; Zusatzdokumente haben keine Pflichtarten: Was sie nicht regeln,
    # regelt der PLU (AN3, 3.7; PLAN_G2_VOLLSTAENDIGKEIT E-VA-1)
    outcome = SearchOutcome()
    if calls.document_kind == "plu":
        rules, outcome = _gap_search(calls, sectors, len(extracted) + 1, rules, page_texts)
    final = (
        complete(rules, sectors, calls.mandatory)
        if calls.document_kind == "plu"
        else sorted(rules, key=lambda r: (r.sector, r.kind, r.building_kind))
    )
    final = scan_reasons(final, calls.scan_pages, calls.chapter_pages)

    # 4. Schreiben
    counts_total: dict[str, int] = defaultdict(int)
    with calls.sessions() as session:
        chapter = session.execute(
            select(RegulationChapter).where(RegulationChapter.id == calls.chapter_id).with_for_update()
        ).scalar_one_or_none()
        if chapter is None:
            return ChapterOutcome("skipped", "chapter_missing")
        # Während der Aufrufe kann ein Sektor dazugekommen sein (zweites Projekt, neue Gemeinde). Der Job
        # dafür endete mit `already_running`; ohne Folgeauftrag bliebe er ohne Regeln (AN2, 7.1 Nr. 11)
        current_digest = input_hash(
            calls.settings, calls.source_sha256, chapter, calls.document_kind, calls.ocr, scope=calls.scope
        )
        stored_digest = calls.text_digest if calls.text_used else calls.digest
        by_sector: dict[str, list[AssessedRule]] = defaultdict(list)
        for assessed_rule in final:
            by_sector[assessed_rule.sector].append(assessed_rule)
        for sector in sectors:
            sector_rules = by_sector.get(sector, [])
            counts = coverage(sector_rules, calls.mandatory)
            for key, value in counts.items():
                counts_total[key] += value
            _write_version(
                session,
                chapter,
                sector,
                sector_rules,
                counts | {"dropped": dropped} | outcome.counts(),
                file_id,
                calls.run_ids,
                stored_digest,
                calls.model,
                outcome,
                calls.scope,
            )
        changed_meanwhile = current_digest != calls.digest
        state = scope_state(session, chapter, calls.scope, create=True)
        assert state is not None
        state.status, state.input_hash, state.engine_version, state.error, state.updated_at = (
            "pending" if changed_meanwhile else "succeeded",
            stored_digest,
            ENGINE_VERSION,
            None,
            utcnow(),
        )
        session.flush()
        # Andere Umfänge nur von Hand: Ein geänderter Sektor wartet auf den nächsten Auftrag, und der
        # Rückfall der Kunden auf den vorigen Planstand hängt nur an `house` (PLAN_REGELDIENST 3.3)
        if calls.scope == "house" and changed_meanwhile:
            _enqueue_follow_up(session, chapter, current_digest)
        elif calls.scope == "house":
            release_fallback(session, plan_id)
        session.commit()
    log.info(
        "rules_extracted",
        chapter=calls.chapter_code,
        scope=calls.scope,
        sectors=sectors,
        cost_usd=round(calls.cost, 4),
        calls=len(calls.run_ids),
        **counts_total,
    )
    return ChapterOutcome("succeeded", None, calls.cost, dict(counts_total))


def scan_reasons(
    rules: list[AssessedRule], scan_pages: frozenset[int], chapter_pages: list[int]
) -> list[AssessedRule]:
    """Auf einer Scan-Seite heißt ein nicht bestätigtes Zitat meist: Tesseract hat anders gelesen als das
    Modell, oft eine Zahl (`_numbers_match`). Eigener Grund, damit der Architekt im Dokument nachsieht statt
    einen erfundenen Wert zu vermuten (AN7, PLAN_AN7_SCAN 3.3). Ohne Fundstelle (keine Seite erreichte eine
    Ähnlichkeit, etwa weil eine Zahl fehlt) entscheidet das Kapitel: Liegt es ganz im Scan, gilt der Grund
    auch dann (7.5)."""
    if not scan_pages:
        return rules
    whole_chapter = bool(chapter_pages) and scan_pages.issuperset(chapter_pages)
    return [
        replace(rule, reason="scan_unconfirmed")
        if rule.reason == "quote_unverified"
        and (rule.page in scan_pages or (rule.page is None and whole_chapter))
        else rule
        for rule in rules
    ]


def _enqueue_follow_up(session: Session, chapter: RegulationChapter, digest: str) -> None:
    """Folgeauftrag für die geänderte Eingabe. Eigener Schlüssel: Der Job mit dem Schlüssel der neuen
    Eingabe ist schon beendet (`already_running`), Idempotenzschlüssel gelten dauerhaft."""
    import app.rules.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    enqueue(
        session,
        "rules_extract",
        {"chapter_id": str(chapter.id)},
        idempotency_key=f"rules_extract:{chapter.id}:{digest}:follow_up",
        created_by=f"{ACTOR}:input_changed",
    )
    log.info("rules_extract_follow_up", chapter=chapter.code, sectors=list(chapter.sectors))


def _cost(settings: Settings, usage: dict[str, int]) -> float:
    from app.integrations.openrouter import prices

    return prices(settings).cost(usage) if usage else 0.0


def _write_version(
    session: Session,
    chapter: RegulationChapter,
    sector: str,
    rules: list[AssessedRule],
    counts: dict[str, int],
    source_file_id: uuid.UUID,
    run_ids: list[uuid.UUID],
    digest: str,
    model: str,
    outcome: "SearchOutcome | None" = None,
    scope: RuleScope = "house",
) -> None:
    rule_set = session.execute(
        select(RuleSet)
        .where(
            RuleSet.land_use_plan_id == chapter.land_use_plan_id,
            RuleSet.zone_code == sector,
            RuleSet.scope == scope,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if rule_set is None:
        rule_set = RuleSet(
            land_use_plan_id=chapter.land_use_plan_id,
            zone_code=sector,
            chapter_id=chapter.id,
            scope=scope,
            created_by=ACTOR,
        )
        session.add(rule_set)
        session.flush()
    current = (
        session.get(RuleSetVersion, rule_set.current_version_id) if rule_set.current_version_id else None
    )
    number = (
        session.execute(
            select(func.coalesce(func.max(RuleSetVersion.version), 0)).where(
                RuleSetVersion.rule_set_id == rule_set.id
            )
        ).scalar_one()
        + 1
    )
    version = RuleSetVersion(
        rule_set_id=rule_set.id,
        version=number,
        status="simulated",
        origin="extraction",
        based_on_id=current.id if current else None,
        extraction_run_ids=list(dict.fromkeys(run_ids)),
        engine_version=ENGINE_VERSION,
        prompt_version=prompt_version(scope),
        model=model,
        input_hash=digest,
        coverage=counts,
        open_passages=[{"page": p.page, "text": p.short} for p in outcome.open] if outcome else [],
        out_of_scope_passages=(
            [{"page": p.page, "text": p.short, "reason": reason} for p, reason in outcome.dismissed]
            if outcome
            else []
        ),
        created_by=ACTOR,
    )
    session.add(version)
    session.flush()
    for rule in rules:
        session.add(
            Rule(
                rule_set_version_id=version.id,
                kind=rule.kind,
                building_kind=rule.building_kind,
                status=rule.status,
                reason=rule.reason,
                detail=rule.detail,
                params=rule.params,
                source_file_id=source_file_id if rule.page is not None else None,
                page=rule.page,
                quote=rule.quote,
                quote_verified=rule.quote_verified,
                similarity=rule.similarity,
                confidence=rule.confidence,
                notes=rule.notes or None,
                alternatives=[asdict_safe(a) for a in rule.alternatives],
                origin="extraction",
                created_by=ACTOR,
            )
        )
    if current is not None and current.status == "office_reviewed":
        # Vom Büro geprüft hat Vorrang vor einer neuen automatischen Auswertung desselben Planstands
        version.note = f"not_current:office_reviewed_v{current.version}"
    else:
        if current is not None:
            current.status = "retired"
        rule_set.current_version_id = version.id
    rule_set.chapter_id = chapter.id
    rule_set.updated_at = utcnow()


def asdict_safe(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
