"""Hochgeladenes règlement écrit (AN2, docs/PLAN_AN2_PLU.md).

Ablauf: PDF hochladen (schnelle Prüfung, Objektspeicher) → Job `rules_document_read` liest Text und Kapitel
→ der Architekt wählt Kapitel und Zonencode → das Kapitel wird wie beim GPU-Import eingeplant und vom
Job `rules_extract` ausgewertet. Kosten entstehen erst mit der Zonenwahl, einmal je Kapitel und
Sektorenmenge. Dasselbe PDF ist dasselbe Dokument (E-AN2-1); es bleibt, wenn ein Projekt gelöscht wird
(E-AN2-4).

Zusatzdokumente (AN3, docs/PLAN_AN3_ANALYSE.md 3.7): règlement de lotissement und cahier des charges, bis
zu drei je Projekt. Statt Zonenkapiteln ein Kapitel `DOC` über das ganze Dokument; der Architekt wählt das
Lot (Sektor `Lot-12`, ohne Lot `Ensemble`), die Auswertung läuft mit eigenem Prompt.
"""

import hashlib
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.platform import audit, storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.platform.models import Project
from app.platform.problems import Problem
from app.rules import pdf
from app.rules.domain.chapters import CHAPTER_MAX_PAGES, detect_structure, sector_candidates
from app.rules.domain.extraction import document_kind
from app.rules.models import (
    LandUsePlan,
    ProjectRegulation,
    RegulationChapter,
    RuleExtractionRun,
    SourceFile,
    SourcePage,
)
from app.rules.schemas import (
    DocumentChapterOut,
    LotChoiceIn,
    OcrOut,
    ProjectRegulationOut,
    RegulationDocumentOut,
    UploadDuType,
    ZoneChoiceIn,
)
from app.rules.sources import ChapterValues, ensure_chapter, store_source

log = get_logger("rules_documents")
READ_ACTOR = "system:rules_document_read"
UPLOAD_PREFIX = "rules/uploads"
NO_TEXT_SHARE = 0.5
"""Mehr als die Hälfte der Seiten ohne Text: gescanntes Reglement, erst nach der Texterkennung nutzbar (RW03,
seit AN7 kein Fehler mehr)."""
FILE_URL = "/api/v1/regulation-files/{id}"
SUPPLEMENT_CHAPTER = "DOC"
"""Einziges Kapitel eines Zusatzdokuments: das ganze Dokument oder ein Seitenbereich (AN3, 3.7)."""
SUPPLEMENT_WHOLE = "Ensemble"
"""Sektor eines Zusatzdokuments ohne Lot: das Dokument als Ganzes."""
MAX_SUPPLEMENTS = 3
"""Zusatzdokumente je Projekt (E-AN3-6): lotissement, cahier des charges, ein Änderungsstand."""
OCR_UNCERTAIN_BELOW = 70.0
"""Erkannte Seite mit mittlerer Wortsicherheit darunter gilt als unsicher (AN7, E-AN7-5)."""


def supplement_sector(lot: str | None) -> str:
    """Sektor eines Lots. Mit Vorsilbe, weil eine blanke Nummer („12“) in jedem Zitat als Zahl vorkäme und
    die Zuordnung der Werte zu Sektoren (`assess.foreign_sector`) in die Irre führte (7.1 Nr. 3)."""
    return f"Lot-{lot}" if lot else SUPPLEMENT_WHOLE


def storage_key(sha256: str) -> str:
    return f"{UPLOAD_PREFIX}/{sha256}.pdf"


def file_url(source_id: uuid.UUID) -> str:
    """Feste Adresse der Datei für Zitate (`#page=` hängt `rules.service` an), 3.6."""
    return FILE_URL.format(id=source_id)


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def project_plu(db: Session, project_id: uuid.UUID) -> ProjectRegulation | None:
    return db.execute(
        select(ProjectRegulation).where(
            ProjectRegulation.project_id == project_id, ProjectRegulation.role == "plu"
        )
    ).scalar_one_or_none()


def latest_source(db: Session, plan_id: uuid.UUID) -> SourceFile | None:
    return (
        db.execute(
            select(SourceFile)
            .where(SourceFile.land_use_plan_id == plan_id)
            .order_by(SourceFile.created_at.desc())
        )
        .scalars()
        .first()
    )


def _document_out(db: Session, plan: LandUsePlan) -> RegulationDocumentOut:
    source = latest_source(db, plan.id)
    chapters = list(
        db.execute(
            select(RegulationChapter)
            .where(RegulationChapter.land_use_plan_id == plan.id)
            .order_by(RegulationChapter.first_page, RegulationChapter.code)
        ).scalars()
    )
    stats: dict[uuid.UUID, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
    for row in db.execute(
        select(
            RuleExtractionRun.chapter_id,
            func.count().label("runs"),
            func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0).label("cost"),
        )
        .where(RuleExtractionRun.chapter_id.in_([c.id for c in chapters]))
        .group_by(RuleExtractionRun.chapter_id)
    ).all():
        stats[row.chapter_id] = (int(row.runs), float(row.cost))
    status: Any = plan.status if plan.status in ("importing", "active", "failed", "scan") else "failed"
    return RegulationDocumentOut(
        id=plan.id,
        title=plan.title,
        du_type=plan.du_type,
        status=status,
        error=plan.error,
        file_name=source.filename if source else None,
        file_url=source.url if source else None,
        sha256=source.sha256 if source else None,
        page_count=source.page_count if source else None,
        empty_pages=list(source.empty_pages) if source else [],
        ocr=ocr_out(db, source) if source else None,
        created_at=plan.created_at,
        chapters=[
            DocumentChapterOut(
                code=c.code,
                title=c.title,
                first_page=c.first_page,
                last_page=c.last_page,
                general_pages=list(c.general_pages),
                detection=c.detection,
                sectors=list(c.sectors),
                suggested_sectors=list(c.suggested_sectors),
                status=c.status if c.sectors else "idle",
                error=c.error,
                runs=stats[c.id][0],
                cost_usd=round(stats[c.id][1], 4),
            )
            for c in chapters
        ],
    )


def ocr_out(db: Session, source: SourceFile) -> OcrOut:
    """Stand der Texterkennung für Hinweis, Fortschritt und Zusammenfassung (AN7, 3.2)."""
    empty = sorted(source.empty_pages)
    rows = (
        db.execute(
            select(
                SourcePage.page,
                SourcePage.ocr_confidence,
                func.char_length(func.regexp_replace(SourcePage.text, r"\s+", "", "g")).label("chars"),
            ).where(
                SourcePage.source_file_id == source.id,
                SourcePage.page.in_(empty),
                SourcePage.ocr_confidence.is_not(None),
            )
        ).all()
        if empty
        else []
    )
    readable = {row.page for row in rows if row.chars >= pdf.EMPTY_PAGE_CHARS}
    state: Any = source.ocr_state
    return OcrOut(
        state=state,
        pages_total=len(empty),
        pages_done=len(rows),
        uncertain_pages=sorted(
            row.page
            for row in rows
            if row.page in readable and (row.ocr_confidence or 0.0) < OCR_UNCERTAIN_BELOW
        ),
        still_empty_pages=sorted(row.page for row in rows if row.page not in readable),
        estimated_seconds=round((len(empty) - len(rows)) * get_settings().ocr_seconds_per_page),
        error=source.ocr_error,
    )


def link_out(db: Session, link: ProjectRegulation) -> ProjectRegulationOut:
    plan = db.get(LandUsePlan, link.land_use_plan_id)
    assert plan is not None
    return ProjectRegulationOut(
        role="supplement" if link.role == "supplement" else "plu",
        zone_code=link.zone_code,
        chapter_code=link.chapter_code,
        document=_document_out(db, plan),
    )


def project_regulations(db: Session, project_id: uuid.UUID) -> list[ProjectRegulationOut]:
    """Das PLU zuerst, danach die Zusatzdokumente in der Reihenfolge des Hochladens."""
    links = db.execute(
        select(ProjectRegulation)
        .where(ProjectRegulation.project_id == project_id)
        .order_by(ProjectRegulation.created_at)
    ).scalars()
    return [link_out(db, link) for link in sorted(links, key=lambda link: link.role != "plu")]


def supplement_links(db: Session, project_id: uuid.UUID) -> list[ProjectRegulation]:
    return list(
        db.execute(
            select(ProjectRegulation)
            .where(ProjectRegulation.project_id == project_id, ProjectRegulation.role == "supplement")
            .order_by(ProjectRegulation.created_at)
        ).scalars()
    )


def file_content(
    db: Session, file_id: uuid.UUID, organisation_id: uuid.UUID | None = None
) -> tuple[bytes, str]:
    """Datei einer Planunterlage. Mit `organisation_id` nur, wenn ein Projekt dieser Organisation das
    Dokument nutzt (AN6, docs/PLAN_AN6_MANDANTEN.md 3.3); sonst `404` wie eine unbekannte Datei."""
    source = db.get(SourceFile, file_id)
    if source is None:
        raise Problem(404, "not_found")
    if organisation_id is not None:
        used = db.execute(
            select(ProjectRegulation.id)
            .join(Project, Project.id == ProjectRegulation.project_id)
            .where(
                ProjectRegulation.land_use_plan_id == source.land_use_plan_id,
                Project.organisation_id == organisation_id,
            )
            .limit(1)
        ).first()
        if used is None:
            raise Problem(404, "not_found")
    return storage.get_bytes(source.storage_key), source.filename


# ---------------------------------------------------------------------------
# Hochladen
# ---------------------------------------------------------------------------


def upload(
    db: Session,
    project_id: uuid.UUID,
    *,
    file_name: str,
    data: bytes,
    title: str | None,
    du_type: UploadDuType,
    actor: str,
) -> ProjectRegulationOut:
    """Reglement als PLU des Projekts hinterlegen. Ein vorhandenes PLU des Projekts wird ersetzt (seine
    Zone entfällt); ist dasselbe PDF schon bekannt, wird das Dokument wiederverwendet (E-AN2-1).

    Ein Zusatzdokument (`lotissement`, `cahier_des_charges`) kommt dazu, statt etwas zu ersetzen; höchstens
    `MAX_SUPPLEMENTS` je Projekt (AN3). Dasselbe PDF einmal als PLU, einmal als Zusatzdokument: `409`,
    sonst liefe es mit dem falschen Prompt (7.1 Nr. 6)."""
    try:
        pdf.check(data)
    except pdf.PdfProblem as exc:
        raise Problem(422, str(exc)) from None
    sha256 = hashlib.sha256(data).hexdigest()
    role = "supplement" if document_kind(du_type) == "supplement" else "plu"
    # Immer und vor jeder Sperre ablegen: Der Schlüssel ist die Prüfsumme, doppeltes Ablegen schadet nicht,
    # ein erneuter Upload stellt eine verlorene Datei wieder her, und ein langsamer oder gestörter Speicher
    # hält keine Zeile der Datenbank fest
    storage.put_bytes(storage_key(sha256), data, "application/pdf")
    plan, created = _document_for_upload(db, sha256, file_name, title, du_type, actor)
    if not created and document_kind(plan.du_type) != document_kind(du_type):
        raise Problem(409, "document_type_conflict", du_type=plan.du_type)
    stuck = plan.status == "importing" and not created and _read_job_missing(db, plan.id)
    if created or plan.status == "failed" or stuck:
        # Neu, früher gescheitert oder ohne Job liegen geblieben: (noch einmal) lesen, das kostet nichts
        plan.status, plan.error = "importing", None
        retry = "" if created else f":{utcnow():%Y%m%d%H%M%S%f}"
        _enqueue_read(db, plan, file_name, actor, key_suffix=retry)

    if role == "supplement":
        link, before = _supplement_link(db, project_id, plan, actor)
    else:
        link, before = _plu_link(db, project_id, plan, actor)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="project_regulation.upload",
        entity_type="project",
        entity_id=str(project_id),
        before=before,
        after={"document": str(plan.id), "sha256": sha256, "file_name": file_name[:200], "role": role},
    )
    db.commit()
    return link_out(db, link)


def _plu_link(
    db: Session, project_id: uuid.UUID, plan: LandUsePlan, actor: str
) -> tuple[ProjectRegulation, dict[str, Any] | None]:
    link = project_plu(db, project_id)
    before = {"document": str(link.land_use_plan_id), "zone": link.zone_code} if link else None
    if link is not None and link.land_use_plan_id != plan.id:
        db.delete(link)
        db.flush()
        link = None
    if link is None:
        link = ProjectRegulation(
            project_id=project_id, land_use_plan_id=plan.id, role="plu", created_by=actor, updated_by=actor
        )
        db.add(link)
    return link, before


def _supplement_link(
    db: Session, project_id: uuid.UUID, plan: LandUsePlan, actor: str
) -> tuple[ProjectRegulation, dict[str, Any] | None]:
    """Zusatzdokument dazunehmen; dasselbe Dokument ein zweites Mal ändert nichts."""
    links = supplement_links(db, project_id)
    existing = next((link for link in links if link.land_use_plan_id == plan.id), None)
    if existing is not None:
        return existing, {"document": str(plan.id), "zone": existing.zone_code}
    if len(links) >= MAX_SUPPLEMENTS:
        raise Problem(422, "too_many_supplements", limit=MAX_SUPPLEMENTS)
    link = ProjectRegulation(
        project_id=project_id,
        land_use_plan_id=plan.id,
        role="supplement",
        created_by=actor,
        updated_by=actor,
    )
    db.add(link)
    return link, None


def _document_for_upload(
    db: Session, sha256: str, file_name: str, title: str | None, du_type: str, actor: str
) -> tuple[LandUsePlan, bool]:
    """Dokument zur Prüfsumme, sonst neu. Zwei gleichzeitige Uploads derselben Datei ergeben eines."""
    inserted = db.execute(
        insert(LandUsePlan)
        .values(
            id=uuid.uuid4(),
            origin="upload",
            document_sha256=sha256,
            gpu_doc_id=None,
            partition="",
            du_type=du_type,
            title=(title or file_name or sha256[:12]).strip()[:300],
            status="importing",
            created_by=actor,
        )
        .on_conflict_do_nothing(index_elements=["document_sha256"])
        .returning(LandUsePlan.id)
    ).scalar_one_or_none()
    plan = db.execute(
        select(LandUsePlan).where(LandUsePlan.document_sha256 == sha256).with_for_update()
    ).scalar_one()
    return plan, inserted is not None


_ACTIVE_READ_JOB = text(
    "SELECT id FROM job WHERE kind = 'rules_document_read' AND status IN ('queued', 'running') "
    "AND payload->>'document_id' = :document LIMIT 1"
)


def _read_job_missing(db: Session, plan_id: uuid.UUID) -> bool:
    return db.execute(_ACTIVE_READ_JOB, {"document": str(plan_id)}).scalar() is None


def _enqueue_read(db: Session, plan: LandUsePlan, file_name: str, actor: str, *, key_suffix: str) -> None:
    import app.rules.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    enqueue(
        db,
        "rules_document_read",
        {"document_id": str(plan.id), "file_name": file_name[:300]},
        idempotency_key=f"rules_document_read:{plan.id}{key_suffix}",
        created_by=actor,
    )


def read_document(db: Session, plan_id: uuid.UUID, file_name: str) -> dict[str, Any]:
    """Job `rules_document_read`: Seitentexte, Kapitel und Vorschläge für Zonencodes (3.2), über
    `index_document`. Ein Scan wartet auf die Bestätigung der Texterkennung (`scan`, `rules/ocr.py`)."""
    plan = db.execute(
        select(LandUsePlan).where(LandUsePlan.id == plan_id).with_for_update()
    ).scalar_one_or_none()
    if plan is None or plan.origin != "upload":
        return {"status": "skipped", "reason": "document_missing"}
    if plan.status != "importing":
        return {"status": "skipped", "reason": plan.status}
    assert plan.document_sha256 is not None
    data = storage.get_bytes(storage_key(plan.document_sha256))
    try:
        reader = pdf.read_text(data)
    except pdf.PdfProblem as exc:
        return _failed(db, plan, str(exc))
    if not reader.pages:
        return _failed(db, plan, "document_no_text")
    # Datei und Seiten immer speichern, auch bei einem Scan: Der Hinweis vor der Texterkennung nennt
    # Seitenzahl und Dauer, und die Erkennung schreibt in dieselben Seiten (AN7, docs/PLAN_AN7_SCAN.md 3.1)
    source_id = uuid.uuid4()
    source = store_source(
        db,
        plan,
        sha256=plan.document_sha256,
        filename=file_name or f"{plan.document_sha256[:12]}.pdf",
        url=file_url(source_id),
        storage_key=storage_key(plan.document_sha256),
        size_bytes=len(data),
        reader=reader,
        actor=READ_ACTOR,
        source_id=source_id,
    )
    if is_scan(len(reader.pages), len(reader.empty_pages)):
        source.ocr_state = "offered"
        plan.status, plan.error = "scan", None
        db.commit()
        log.info(
            "rules_document_scan",
            document=str(plan.id),
            pages=len(reader.pages),
            empty_pages=len(reader.empty_pages),
        )
        return {"status": "scan", "pages": len(reader.pages), "empty_pages": len(reader.empty_pages)}
    chapters = index_document(db, plan, source, reader.pages)
    plan.status, plan.error, plan.activated_at = "active", None, utcnow()
    db.commit()
    log.info(
        "rules_document_read",
        document=str(plan.id),
        pages=len(reader.pages),
        empty_pages=len(reader.empty_pages),
        chapters=chapters,
    )
    return {"status": "active", "pages": len(reader.pages), "chapters": chapters}


def is_scan(pages: int, empty_pages: int) -> bool:
    """Mehr als die Hälfte der Seiten ohne Text: gescanntes Dokument, erst nach der Texterkennung nutzbar."""
    return pages == 0 or empty_pages > NO_TEXT_SHARE * pages


def index_document(db: Session, plan: LandUsePlan, source: SourceFile, pages: dict[int, str]) -> int:
    """Kapitel anlegen, die noch fehlen; vorhandene bleiben unberührt (auch nach einer nachträglichen
    Texterkennung, AN7 3.2). Jedes Kapitel entsteht **ohne Sektoren**; solche Kapitel wertet niemand aus.
    Ein Reglement ohne erkennbare Kapitel ist trotzdem nutzbar – über einen Seitenbereich von Hand.

    Zusatzdokument: keine Zonenkapitel, sondern ein Kapitel `DOC` über das ganze Dokument, noch ohne
    Sektoren – es kostet erst, wenn ein Lot gewählt wird (AN3, 3.7).

    Liefert die Zahl der erkannten Kapitel."""
    existing = set(
        db.execute(
            select(RegulationChapter.code).where(RegulationChapter.land_use_plan_id == plan.id)
        ).scalars()
    )
    if document_kind(plan.du_type) == "supplement":
        if SUPPLEMENT_CHAPTER not in existing:
            db.add(
                RegulationChapter(
                    land_use_plan_id=plan.id,
                    source_file_id=source.id,
                    code=SUPPLEMENT_CHAPTER,
                    title=plan.title[:300],
                    first_page=1,
                    last_page=source.page_count,
                    general_pages=[],
                    sectors=[],
                    suggested_sectors=[],
                    detection="document",
                    created_by=READ_ACTOR,
                )
            )
        return 1
    structure = detect_structure(pages)
    codes = frozenset(c.code for c in structure.chapters)
    for chapter in structure.chapters:
        if chapter.code in existing:
            continue
        chapter_text = "\n".join(pages.get(page, "") for page in chapter.pages)
        db.add(
            RegulationChapter(
                land_use_plan_id=plan.id,
                source_file_id=source.id,
                code=chapter.code,
                title=chapter.title[:300],
                first_page=chapter.first_page,
                last_page=chapter.last_page,
                general_pages=structure.general_pages,
                sectors=[],
                suggested_sectors=sector_candidates(chapter_text, chapter.code, codes - {chapter.code}),
                detection=structure.method,
                created_by=READ_ACTOR,
            )
        )
    return len(structure.chapters)


def _failed(db: Session, plan: LandUsePlan, error: str) -> dict[str, Any]:
    plan.status, plan.error = "failed", error
    db.commit()
    log.warning("rules_document_unreadable", document=str(plan.id), error=error)
    return {"status": "failed", "error": error}


def mark_read_failed(db: Session, plan_id: uuid.UUID, error: str) -> None:
    """Letzter Versuch des Jobs gescheitert (Speicher, Absturz): Das Dokument bleibt nicht auf `importing`."""
    plan = db.get(LandUsePlan, plan_id)
    if plan is not None and plan.status == "importing":
        plan.status, plan.error = "failed", error[:300]
        db.commit()


# ---------------------------------------------------------------------------
# Zone wählen, Dokument entfernen
# ---------------------------------------------------------------------------


def project_link(db: Session, project_id: uuid.UUID, document_id: uuid.UUID) -> ProjectRegulation:
    link = db.execute(
        select(ProjectRegulation)
        .where(ProjectRegulation.project_id == project_id, ProjectRegulation.land_use_plan_id == document_id)
        .with_for_update()
    ).scalar_one_or_none()
    if link is None:
        raise Problem(404, "not_found")
    return link


def _ready_document(db: Session, document_id: uuid.UUID) -> tuple[LandUsePlan, SourceFile]:
    """Dokument gesperrt und gelesen; solange es gelesen wird oder gescheitert ist, keine Auswahl."""
    plan = db.execute(select(LandUsePlan).where(LandUsePlan.id == document_id).with_for_update()).scalar_one()
    if plan.status == "importing":
        raise Problem(409, "document_not_ready")
    if plan.status == "scan":
        raise Problem(409, "document_scan")
    if plan.status != "active":
        raise Problem(409, "document_failed", reason=plan.error)
    source = latest_source(db, plan.id)
    assert source is not None
    return plan, source


def _pages(first: int, last: int, page_count: int) -> list[int]:
    if last > page_count:
        raise Problem(422, "page_out_of_range", page_count=page_count)
    return list(range(first, last + 1))


def choose_zone(
    db: Session,
    settings: Settings,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    body: ZoneChoiceIn,
    actor: str,
) -> ProjectRegulationOut:
    """Zone des Grundstücks im hochgeladenen Reglement festlegen und das Kapitel einplanen (3.3).

    Hier entstehen die Kosten: Der Sektor kommt zu den Sektoren des Kapitels; geänderte Eingabe →
    `pending` und Job (Idempotenz über die Eingabe), unveränderte → nichts."""
    link = project_link(db, project_id, document_id)
    if link.role != "plu":
        raise Problem(409, "not_a_plu")
    plan, source = _ready_document(db, document_id)
    chapters = {
        c.code: c
        for c in db.execute(
            select(RegulationChapter).where(RegulationChapter.land_use_plan_id == plan.id).with_for_update()
        ).scalars()
    }
    detected_general = next(
        (list(c.general_pages) for c in chapters.values() if c.detection != "manual" and c.general_pages),
        [],
    )

    if body.first_page is not None and body.last_page is not None:
        code = body.chapter_code or body.zone_code
        pages = _pages(body.first_page, body.last_page, source.page_count)
        general = (
            _pages(body.general_first_page, body.general_last_page, source.page_count)
            if body.general_first_page is not None and body.general_last_page is not None
            else detected_general
        )
        current = chapters.get(code)
        title = current.title if current is not None else f"{code} (p. {pages[0]}–{pages[-1]})"
        detection = "manual"
    else:
        assert body.chapter_code is not None  # von ZoneChoiceIn erzwungen
        code = body.chapter_code
        current = chapters.get(code)
        if current is None:
            raise Problem(422, "chapter_not_found")
        pages = list(range(current.first_page, current.last_page + 1))
        general = list(current.general_pages)
        title, detection = current.title, current.detection
    chapter_pages = set(pages)
    general = [page for page in general if page not in chapter_pages]
    if len(pages) + len(general) > CHAPTER_MAX_PAGES:
        raise Problem(422, "chapter_too_long", pages=len(pages) + len(general), limit=CHAPTER_MAX_PAGES)

    sectors = sorted({*(current.sectors if current is not None else []), body.zone_code})
    values = ChapterValues(
        title=title,
        first_page=pages[0],
        last_page=pages[-1],
        general_pages=general,
        sectors=sectors,
        detection=detection,
    )
    ensure_chapter(
        db,
        settings,
        plan,
        source,
        code,
        values,
        current,
        actor=actor,
        reason="zone_choice",
    )
    before = {"zone": link.zone_code, "chapter": link.chapter_code}
    link.zone_code, link.chapter_code = body.zone_code, code
    link.updated_at, link.updated_by = utcnow(), actor
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="project_regulation.zone",
        entity_type="project",
        entity_id=str(project_id),
        before=before,
        after={
            "document": str(plan.id),
            "zone": body.zone_code,
            "chapter": code,
            "pages": [pages[0], pages[-1]],
            "detection": detection,
        },
    )
    db.commit()
    return link_out(db, link)


def choose_lot(
    db: Session,
    settings: Settings,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    body: LotChoiceIn,
    actor: str,
) -> ProjectRegulationOut:
    """Lot eines Zusatzdokuments wählen und das Kapitel `DOC` einplanen (AN3, 3.7).

    Wie bei der Zonenwahl entstehen hier die Kosten: Das Lot kommt zu den Sektoren des Kapitels; ein neues
    Lot wertet das Dokument neu aus, auch für die Lots anderer Projekte (E-AN3-4)."""
    link = project_link(db, project_id, document_id)
    if link.role != "supplement":
        raise Problem(409, "not_a_supplement")
    plan, source = _ready_document(db, document_id)
    chapter = db.execute(
        select(RegulationChapter)
        .where(RegulationChapter.land_use_plan_id == plan.id, RegulationChapter.code == SUPPLEMENT_CHAPTER)
        .with_for_update()
    ).scalar_one_or_none()
    if body.first_page is not None and body.last_page is not None:
        pages = _pages(body.first_page, body.last_page, source.page_count)
        detection = "manual"
    else:
        pages = list(range(1, source.page_count + 1))
        detection = "document"
    if len(pages) > CHAPTER_MAX_PAGES:
        raise Problem(422, "chapter_too_long", pages=len(pages), limit=CHAPTER_MAX_PAGES)
    sector = supplement_sector(body.lot)
    values = ChapterValues(
        title=plan.title,
        first_page=pages[0],
        last_page=pages[-1],
        general_pages=[],
        sectors=sorted({*(chapter.sectors if chapter is not None else []), sector}),
        detection=detection,
    )
    ensure_chapter(
        db,
        settings,
        plan,
        source,
        SUPPLEMENT_CHAPTER,
        values,
        chapter,
        actor=actor,
        reason="lot_choice",
    )
    before = {"lot": link.zone_code}
    link.zone_code, link.chapter_code = sector, SUPPLEMENT_CHAPTER
    link.updated_at, link.updated_by = utcnow(), actor
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="project_regulation.lot",
        entity_type="project",
        entity_id=str(project_id),
        before=before,
        after={"document": str(plan.id), "lot": sector, "pages": [pages[0], pages[-1]]},
    )
    db.commit()
    return link_out(db, link)


def remove(db: Session, project_id: uuid.UUID, document_id: uuid.UUID, actor: str) -> None:
    """Dokument vom Projekt lösen. Das Dokument selbst bleibt (E-AN2-4); Sektoren bleiben am Kapitel."""
    link = project_link(db, project_id, document_id)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="project_regulation.remove",
        entity_type="project",
        entity_id=str(project_id),
        before={"document": str(document_id), "zone": link.zone_code},
    )
    db.delete(link)
    db.commit()
