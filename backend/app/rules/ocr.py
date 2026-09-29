"""Texterkennung gescannter Reglements und Zusatzdokumente (AN7, docs/PLAN_AN7_SCAN.md 3.1–3.2).

Ablauf: `rules_document_read` erkennt einen Scan (Status `scan`, `ocr_state = offered`) → der Architekt
bestätigt den Hinweis (`request`) → Job `rules_document_ocr` erkennt je Lauf höchstens `BATCH_PAGES` Seiten,
speichert jede sofort und plant den nächsten Teil, damit andere Jobs dazwischen laufen → `finish` sucht die
Kapitel und setzt das Dokument auf `active`. Erkannt werden nur Seiten ohne Textschicht; der Zustand hängt an
der Datei, dieselbe Datei wird also nur einmal erkannt, auch wenn mehrere Projekte sie nutzen.
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import audit, organisations, scan, storage
from app.platform.auth.context import project_organisation
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.platform.problems import Problem
from app.rules import documents, pdf
from app.rules.models import LandUsePlan, SourceFile, SourcePage
from app.rules.schemas import ProjectRegulationOut

log = get_logger("rules_ocr")
ACTOR = "system:rules_document_ocr"
BATCH_PAGES = 20
"""Seiten je Lauf: etwa eine Minute bei 3 s je Seite; so wartet ein anderer Job höchstens einen Teil ab."""


def request(db: Session, project_id: uuid.UUID, document_id: uuid.UUID, actor: str) -> ProjectRegulationOut:
    """Texterkennung nach dem Hinweis bestätigen. Läuft sie schon oder ist alles erkannt, ändert sich
    nichts. Die offenen Seiten zählen beim Scan-Kontingent der Organisation des Projekts (AN6,
    docs/PLAN_AN6_MANDANTEN.md 3.4); reicht es nicht, `409 ocr_quota_exceeded`."""
    link = documents.project_link(db, project_id, document_id)
    plan = db.execute(select(LandUsePlan).where(LandUsePlan.id == document_id).with_for_update()).scalar_one()
    if plan.status not in ("scan", "active"):
        raise Problem(409, "document_not_ready")
    source = documents.latest_source(db, plan.id)
    if source is None or not source.empty_pages:
        raise Problem(409, "ocr_not_needed")
    source = db.execute(select(SourceFile).where(SourceFile.id == source.id).with_for_update()).scalar_one()
    open_pages = _open_pages(db, source)
    if source.ocr_state != "running" and open_pages:
        organisation_id = project_organisation(db, project_id)
        if organisation_id is not None:
            organisations.reserve_ocr_pages(
                db, get_settings(), organisation_id, len(open_pages), f"source_file:{source.id}", actor
            )
        before = source.ocr_state
        source.ocr_state, source.ocr_error = "running", None
        source.ocr_started_at, source.ocr_finished_at = utcnow(), None
        _enqueue(db, source, open_pages[0], actor, suffix=f":{utcnow():%Y%m%d%H%M%S%f}")
        audit.record(
            db,
            actor_type="staff",
            actor_id=actor,
            action="regulation_document.ocr",
            entity_type="land_use_plan",
            entity_id=str(plan.id),
            before={"ocr_state": before},
            after={"ocr_state": "running", "pages": len(open_pages)},
        )
        log.info("rules_document_ocr_requested", document=str(plan.id), pages=len(open_pages))
    db.commit()
    return documents.link_out(db, link)


def _open_pages(db: Session, source: SourceFile) -> list[int]:
    done = set(
        db.execute(
            select(SourcePage.page).where(
                SourcePage.source_file_id == source.id, SourcePage.ocr_confidence.is_not(None)
            )
        ).scalars()
    )
    return [page for page in sorted(source.empty_pages) if page not in done]


def _enqueue(db: Session, source: SourceFile, first_page: int, actor: str, *, suffix: str = "") -> None:
    import app.rules.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    enqueue(
        db,
        "rules_document_ocr",
        {"source_id": str(source.id)},
        idempotency_key=f"rules_document_ocr:{source.id}:{first_page}{suffix}",
        created_by=actor,
    )


def run_batch(db: Session, source_id: uuid.UUID) -> dict[str, Any]:
    """Job `rules_document_ocr`: die nächsten offenen Seiten erkennen. Eine Seite, die sich nicht lesen lässt,
    bleibt leer (Sicherheit 0) und zählt als erledigt; fehlt Tesseract selbst, scheitert der Job."""
    source = db.get(SourceFile, source_id)
    if source is None or source.ocr_state != "running":
        return {"status": "skipped", "reason": source.ocr_state if source else "missing"}
    todo = _open_pages(db, source)
    data = storage.get_bytes(source.storage_key) if todo else b""
    batch, rest = todo[:BATCH_PAGES], todo[BATCH_PAGES:]
    unreadable = 0
    for page in batch:
        try:
            recognized = scan.recognize(scan.render(data, page))
            text, confidence = recognized.text.replace("\x00", ""), recognized.confidence
        except scan.ScanProblem as problem:
            if str(problem) == "ocr_unavailable":
                raise
            log.warning(
                "rules_document_ocr_page_failed", source=str(source.id), page=page, error=str(problem)
            )
            text, confidence, unreadable = "", 0.0, unreadable + 1
        db.execute(
            update(SourcePage)
            .where(SourcePage.source_file_id == source.id, SourcePage.page == page)
            .values(text=text, ocr_confidence=confidence)
        )
        # Jede Seite sofort: Ein Abbruch durch das Zeitlimit verliert höchstens eine Seite
        db.commit()
    if rest:
        _enqueue(db, source, rest[0], ACTOR)
        db.commit()
        return {"status": "running", "pages": len(batch), "open": len(rest), "unreadable": unreadable}
    return finish(db, source.id) | {"pages": len(batch), "unreadable": unreadable}


def finish(db: Session, source_id: uuid.UUID) -> dict[str, Any]:
    """Alle Seiten erkannt: Kapitel suchen bzw. ergänzen und das Dokument freigeben. Bleibt auch nach der
    Erkennung mehr als die Hälfte leer, ist das Dokument nicht lesbar (`ocr_no_text`)."""
    source = db.execute(select(SourceFile).where(SourceFile.id == source_id).with_for_update()).scalar_one()
    plan = db.execute(
        select(LandUsePlan).where(LandUsePlan.id == source.land_use_plan_id).with_for_update()
    ).scalar_one()
    # .all(): Ein Result hat keys() und wäre für dict() eine Zuordnung, keine Folge von Paaren (README)
    pages = dict(
        db.execute(select(SourcePage.page, SourcePage.text).where(SourcePage.source_file_id == source.id))
        .tuples()
        .all()
    )
    empty = sum(1 for text in pages.values() if len(text.strip()) < pdf.EMPTY_PAGE_CHARS)
    source.ocr_finished_at = utcnow()
    result: dict[str, Any]
    if plan.status == "scan" and documents.is_scan(len(pages), empty):
        source.ocr_state, source.ocr_error = "failed", "ocr_no_text"
        plan.status, plan.error = "failed", "ocr_no_text"
        result = {"status": "failed", "error": "ocr_no_text"}
    else:
        chapters = documents.index_document(db, plan, source, pages)
        source.ocr_state = "done"
        if plan.status == "scan":
            plan.status, plan.error, plan.activated_at = "active", None, utcnow()
        result = {"status": "done", "chapters": chapters}
    db.commit()
    log.info("rules_document_ocr_finished", document=str(plan.id), still_empty=empty, **result)
    return result


def mark_failed(db: Session, source_id: uuid.UUID, error: str) -> None:
    """Letzter Versuch des Jobs gescheitert: erneut anstoßbar, bereits erkannte Seiten bleiben."""
    source = db.get(SourceFile, source_id)
    if source is not None and source.ocr_state == "running":
        source.ocr_state, source.ocr_error, source.ocr_finished_at = "failed", error[:300], utcnow()
        db.commit()
