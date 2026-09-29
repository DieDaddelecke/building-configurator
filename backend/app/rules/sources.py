"""Planunterlagen und Kapitel speichern: gemeinsam für den GPU-Import (`plan_import`) und hochgeladene
Dokumente (`documents`, AN2).

Aus `plan_import` gelöst (REFACTORING_PLAN S10), damit der Upload den GPU-Import mit seinen Anbindungen nicht
lädt.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.rules import pdf
from app.rules.domain.chapters import CHAPTER_MAX_PAGES
from app.rules.domain.extraction import DocumentKind, document_kind
from app.rules.extract import input_hash, ocr_stamp
from app.rules.models import LandUsePlan, RegulationChapter, SourceFile, SourcePage


def store_source(
    session: Session,
    plan: LandUsePlan,
    *,
    sha256: str,
    filename: str,
    url: str,
    storage_key: str,
    size_bytes: int,
    reader: pdf.PdfText,
    actor: str,
    data: bytes | None = None,
    source_id: uuid.UUID | None = None,
) -> SourceFile:
    """Planunterlage und ihre Seitentexte speichern; eine Datei mit gleicher Prüfsumme wird
    wiederverwendet. Frühere Dateien bleiben: Regeln verweisen auf sie.

    `data` legt die Datei in den Objektspeicher; ein Upload liegt dort schon (AN2). `source_id` vergibt
    die Kennung vorab, wenn die Adresse der Datei sie enthält (`/api/v1/regulation-files/<id>`)."""
    existing = (
        session.execute(
            select(SourceFile)
            .where(SourceFile.land_use_plan_id == plan.id, SourceFile.sha256 == sha256)
            .order_by(SourceFile.created_at.desc())
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing
    if data is not None:
        storage.put_bytes(storage_key, data, "application/pdf")
    source_file = SourceFile(
        id=source_id or uuid.uuid4(),
        land_use_plan_id=plan.id,
        kind="regulation_pdf",
        filename=filename[:300],
        url=url,
        sha256=sha256,
        storage_key=storage_key,
        size_bytes=size_bytes,
        page_count=len(reader.pages),
        empty_pages=reader.empty_pages,
        created_by=actor,
    )
    session.add(source_file)
    session.flush()
    session.execute(
        insert(SourcePage),
        [
            {"source_file_id": source_file.id, "page": n, "text": t.replace("\x00", "")}
            for n, t in reader.pages.items()
        ],
    )
    return source_file


@dataclass(frozen=True)
class ChapterValues:
    """Eingabe eines Kapitels: was die Auswertung liest und für welche Sektoren."""

    title: str
    first_page: int
    last_page: int
    general_pages: list[int]
    sectors: list[str]
    detection: str

    @property
    def page_count(self) -> int:
        return self.last_page - self.first_page + 1 + len(self.general_pages)


def ensure_chapter(
    session: Session,
    settings: Settings,
    plan: LandUsePlan,
    source_file: SourceFile,
    code: str,
    values: ChapterValues,
    chapter: RegulationChapter | None,
    *,
    actor: str,
    reason: str,
    notes: list[str] | None = None,
) -> RegulationChapter:
    """Kapitel anlegen oder an die Eingabe angleichen (RW20).

    Unveränderte Kapitel behalten Status und Läufe. Geänderte werden `pending` und neu eingeplant; die
    Wiederverwendung gespeicherter Aufrufe hängt an der Eingabe, nicht an der Kapitelzeile. Zu lange
    Kapitel werden nicht ausgewertet (`chapter_too_long`, RW23). Gemeinsam für GPU-Import und Upload (AN2).
    """
    fields = {
        "source_file_id": source_file.id,
        "title": values.title[:300],
        "first_page": values.first_page,
        "last_page": values.last_page,
        "general_pages": values.general_pages,
        "sectors": values.sectors,
        "detection": values.detection,
    }
    if chapter is None:
        chapter = RegulationChapter(land_use_plan_id=plan.id, code=code, created_by=actor, **fields)
        session.add(chapter)
        changed = True
    else:
        changed = any(getattr(chapter, key) != value for key, value in fields.items())
        for key, value in fields.items():
            setattr(chapter, key, value)
    session.flush()
    if values.page_count > CHAPTER_MAX_PAGES:
        if notes is not None:
            notes.append(f"chapter_too_long:{code}")
        chapter.status, chapter.error, chapter.updated_at = "failed", "chapter_too_long", utcnow()
        return chapter
    if values.sectors and (changed or chapter.status == "pending"):
        if chapter.status != "extracting":
            chapter.status, chapter.error, chapter.updated_at = "pending", None, utcnow()
        enqueue_extraction(
            session,
            settings,
            chapter,
            source_file.sha256,
            f"{actor}:{reason}",
            document_kind(plan.du_type),
        )
    return chapter


def enqueue_extraction(
    session: Session,
    settings: Settings,
    chapter: RegulationChapter,
    source_sha256: str,
    created_by: str,
    kind: DocumentKind = "plu",
) -> None:
    import app.rules.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    # Schlüssel über die Eingabe: geänderte Seiten oder Sektoren ergeben einen neuen Job, gleiche keinen
    stamp = ocr_stamp(session.get(SourceFile, chapter.source_file_id)) if chapter.source_file_id else None
    digest = input_hash(settings, source_sha256, chapter, kind, stamp)
    enqueue(
        session,
        "rules_extract",
        {"chapter_id": str(chapter.id)},
        idempotency_key=f"rules_extract:{chapter.id}:{digest}",
        created_by=created_by,
    )
