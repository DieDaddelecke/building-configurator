"""Auswertung eines Zonenkapitels: Aufrufe des Sprachmodells, Schranken, neue Regelwerksversionen (Plan 3.4).

Ablauf: Auswertung (Lauf 1) → Schranken → Gegenprüfung (Lauf 2, docs/ANNAHMEN.md RW19) → Regelwerk je Sektor.
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
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.openrouter import ExtractionError, ExtractionRequest, RuleExtractor
from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.rules import pdf
from app.rules.domain import ENGINE_VERSION, PROMPT_VERSION
from app.rules.domain.assess import (
    AssessedRule,
    DocumentPages,
    assess_rule,
    claim_for,
    collapse,
    complete,
    coverage,
    verify,
)
from app.rules.domain.chapters import CHAPTER_MAX_PAGES
from app.rules.domain.extraction import (
    DocumentKind,
    ExtractedRule,
    VerificationCheck,
    document_kind,
    parse_output,
    parse_verification,
    prompt_fingerprint,
)
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)

log = get_logger("rules_extract")
ACTOR = "system:rules_extract"
SessionFactory = Callable[[], AbstractContextManager[Session]]
RUNNING_STALE_AFTER = timedelta(minutes=70)
"""Länger als das Zeitlimit des Jobs (60 min) „läuft“ kein Kapitel; danach gilt der Lauf als abgebrochen."""
CLAIMS_PER_CALL = 30
"""Regeln je Aufruf der Gegenprüfung; kleinere Antworten, weniger Risiko für `max_tokens`."""
RUN_EXTRACTION, RUN_VERIFICATION = 1, 2


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


def input_hash(
    settings: Settings, source_sha256: str, chapter: RegulationChapter, kind: DocumentKind = "plu"
) -> str:
    """Eingabe der Aufrufe. Die Version der Schranken gehört nicht dazu: Sie ändert nur die Bewertung. Der
    Prompt hängt an der Dokumentart (PLU oder Zusatzdokument, AN3)."""
    payload = {
        "source": source_sha256,
        "chapter": [chapter.code, chapter.first_page, chapter.last_page],
        "general": chapter.general_pages,
        "sectors": sorted(chapter.sectors),
        "model": settings.rules_model,
        "effort": settings.rules_effort,
        "runs": settings.rules_runs,
        "prompt": [PROMPT_VERSION, prompt_fingerprint(kind)],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def month_cost(session: Session, now: datetime | None = None) -> float:
    current = now or utcnow()
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    total = session.execute(
        select(func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0)).where(
            RuleExtractionRun.created_at >= start
        )
    ).scalar_one()
    return float(total)


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


@dataclass
class _Calls:
    """Aufrufe eines Kapitels mit Wiederverwendung, Budget, Zeitbudget und Kostenerfassung."""

    sessions: SessionFactory
    settings: Settings
    chapter_id: uuid.UUID
    digest: str
    source_sha256: str
    extractor_factory: Callable[[], RuleExtractor]
    final_attempt: bool
    deadline: float | None
    storage_key: str
    chapter_code: str
    chapter_pages: list[int]
    general_pages: list[int]
    reusable: dict[tuple[int, str], tuple[uuid.UUID, dict[str, Any]]]
    split: set[tuple[int, str]]
    document_kind: DocumentKind = "plu"
    cost: float = 0.0
    model: str = ""
    run_ids: list[uuid.UUID] = field(default_factory=list)
    in_flight: tuple[int, str] | None = None
    _pdfs: tuple[bytes, bytes | None] | None = None

    def _documents(self) -> tuple[bytes, bytes | None]:
        if self._pdfs is None:
            data = storage.get_bytes(self.storage_key)
            general = pdf.extract_pages(data, self.general_pages) if self.general_pages else None
            self._pdfs = (pdf.extract_pages(data, self.chapter_pages), general)
        return self._pdfs

    def _set_chapter(self, status: str, error: str | None = None) -> None:
        with self.sessions() as session:
            current = session.get(RegulationChapter, self.chapter_id)
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

    def _record(self, run_no: int, part: str, **values: Any) -> uuid.UUID:
        with self.sessions() as session:
            run = RuleExtractionRun(
                chapter_id=self.chapter_id,
                run_no=run_no,
                part=part[:200],
                input_hash=self.digest,
                prompt_version=PROMPT_VERSION,
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
        self, run_no: int, part: str, sectors: list[str], claims: list[dict[str, Any]] | None = None
    ) -> Any:
        """Antwort eines Teils; `None`, wenn der Teil für eine Antwort zu groß ist (`max_tokens`)."""
        key = (run_no, part)
        if key in self.reusable:
            run_id, output = self.reusable[key]
            self.run_ids.append(run_id)
            return output
        if key in self.split:
            return None
        self._before_call()
        chapter_pdf, general_pdf = self._documents()
        request = ExtractionRequest(
            chapter_code=self.chapter_code,
            sectors=sectors,
            chapter_pdf=chapter_pdf,
            chapter_pages=self.chapter_pages,
            general_pdf=general_pdf,
            general_pages=self.general_pages,
            claims=claims,
            document_kind=self.document_kind,
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
        run_id = self._record(
            run_no,
            part,
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
        self.reusable[key] = (run_id, response.output)
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
) -> ChapterOutcome:
    """`deadline` (Zeitpunkt aus `time.monotonic`): kein neuer Aufruf, der danach enden könnte."""
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
        digest = input_hash(settings, source.sha256, chapter, kind)
        if (
            not force
            and chapter.status == "succeeded"
            and chapter.input_hash == digest
            and chapter.engine_version == ENGINE_VERSION
        ):
            return ChapterOutcome("skipped", "unchanged")
        if (
            skip_if_running
            and chapter.status == "extracting"
            and utcnow() - chapter.updated_at < RUNNING_STALE_AFTER
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
        reusable: dict[tuple[int, str], tuple[uuid.UUID, dict[str, Any]]] = {}
        split: set[tuple[int, str]] = set()
        if not force:
            for run in session.execute(
                select(RuleExtractionRun)
                .where(RuleExtractionRun.chapter_id == chapter.id, RuleExtractionRun.input_hash == digest)
                .order_by(RuleExtractionRun.created_at)
            ).scalars():
                if run.status == "succeeded" and run.output is not None:
                    reusable[(run.run_no, run.part)] = (run.id, run.output)
                elif run.error == "max_tokens":
                    split.add((run.run_no, run.part))
        chapter.status, chapter.error, chapter.updated_at = "extracting", None, utcnow()
        session.commit()
        sectors = sorted(chapter.sectors)
        calls = _Calls(
            sessions=sessions,
            settings=settings,
            chapter_id=chapter_id,
            digest=digest,
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
            document_kind=kind,
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
    # Zusatzdokumente haben keine Pflichtarten: Was sie nicht regeln, regelt der PLU (AN3, 3.7)
    final = (
        complete(rules, sectors)
        if calls.document_kind == "plu"
        else sorted(rules, key=lambda r: (r.sector, r.kind, r.building_kind))
    )

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
        current_digest = input_hash(calls.settings, calls.source_sha256, chapter, calls.document_kind)
        by_sector: dict[str, list[AssessedRule]] = defaultdict(list)
        for assessed_rule in final:
            by_sector[assessed_rule.sector].append(assessed_rule)
        for sector in sectors:
            sector_rules = by_sector.get(sector, [])
            counts = coverage(sector_rules)
            for key, value in counts.items():
                counts_total[key] += value
            _write_version(
                session,
                chapter,
                sector,
                sector_rules,
                counts | {"dropped": dropped},
                file_id,
                calls.run_ids,
                calls.digest,
                calls.model,
            )
        changed_meanwhile = current_digest != calls.digest
        chapter.status, chapter.input_hash, chapter.engine_version, chapter.error, chapter.updated_at = (
            "pending" if changed_meanwhile else "succeeded",
            calls.digest,
            ENGINE_VERSION,
            None,
            utcnow(),
        )
        session.flush()
        if changed_meanwhile:
            _enqueue_follow_up(session, chapter, current_digest)
        else:
            release_fallback(session, plan_id)
        session.commit()
    log.info(
        "rules_extracted",
        chapter=calls.chapter_code,
        sectors=sectors,
        cost_usd=round(calls.cost, 4),
        calls=len(calls.run_ids),
        **counts_total,
    )
    return ChapterOutcome("succeeded", None, calls.cost, dict(counts_total))


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
) -> None:
    rule_set = session.execute(
        select(RuleSet)
        .where(RuleSet.land_use_plan_id == chapter.land_use_plan_id, RuleSet.zone_code == sector)
        .with_for_update()
    ).scalar_one_or_none()
    if rule_set is None:
        rule_set = RuleSet(
            land_use_plan_id=chapter.land_use_plan_id,
            zone_code=sector,
            chapter_id=chapter.id,
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
        prompt_version=PROMPT_VERSION,
        model=model,
        input_hash=digest,
        coverage=counts,
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
