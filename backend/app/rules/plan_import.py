"""Planstand je Gemeinde aus dem GPU importieren (Plan 3.4, Spez. 5.2.1, 5.2.5).

Ablauf: Gemeinde → Zonen → Planwerk mit größter Fläche in der Gemeinde → Dokument → règlement écrit laden,
Text je Seite, Kapitel erkennen → in einer Transaktion speichern → Auswertung je Kapitel als Job.

- Ein unveränderter Planstand (Dokument, Datum, Zeitstempel der Zonen) wird nicht erneut geladen.
- Ein geändertes Datum desselben Dokuments oder `force` aktualisiert den Planstand an Ort und Stelle:
  Regelwerke, Korrekturen des Büros und gespeicherte Aufrufe bleiben erhalten, unveränderte Kapitel werden
  nicht neu ausgewertet (docs/ANNAHMEN.md RW20). Nichts wird gelöscht, bevor der neue Stand lesbar ist.
- Ein neues Dokument ist ein neuer Planstand. Bis er ausgewertet ist oder wenn er nicht lesbar ist, sehen
  Kunden den vorigen als „veraltet“ (`rules_commune.fallback_land_use_plan_id`, RW21).
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx2
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete, exists, insert, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations import gpu
from app.integrations.http import ExternalServiceError
from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.rules import pdf
from app.rules.domain.chapters import (
    CHAPTER_MAX_PAGES,
    Chapter,
    Structure,
    chapter_for_zone,
    detect_structure,
)
from app.rules.domain.extraction import DocumentKind, document_kind
from app.rules.extract import input_hash
from app.rules.models import (
    LandUsePlan,
    OverlayConstraint,
    RegulationChapter,
    RulesCommune,
    RuleSet,
    SourceFile,
    SourcePage,
    Zone,
)

log = get_logger("rules_import")
ACTOR = "system:plu_import"
OVERLAY_CATEGORY = {
    "prescription-surf": "prescription",
    "prescription-lin": "prescription",
    "prescription-pct": "prescription",
    "info-surf": "information",
    "assiette-sup-s": "servitude",
}


class GpuSource(Protocol):
    def municipality(self, insee: str) -> gpu.Municipality: ...
    def features(self, endpoint: str, geometry: dict[str, Any]) -> list[gpu.GpuFeature]: ...
    def document(self, gpu_doc_id: str) -> gpu.GpuDocument: ...
    def download(self, url: str) -> bytes: ...
    def file_url(self, doc: gpu.GpuDocument, name: str) -> str: ...


@dataclass
class ApiGpu:
    client: httpx2.Client
    settings: Settings

    def municipality(self, insee: str) -> gpu.Municipality:
        return gpu.municipality(self.client, self.settings, insee)

    def features(self, endpoint: str, geometry: dict[str, Any]) -> list[gpu.GpuFeature]:
        return gpu.features_in(self.client, self.settings, endpoint, geometry)

    def document(self, gpu_doc_id: str) -> gpu.GpuDocument:
        return gpu.document(self.client, self.settings, gpu_doc_id)

    def download(self, url: str) -> bytes:
        return gpu.download(self.client, self.settings, url, pdf.MAX_PDF_BYTES)

    def file_url(self, doc: gpu.GpuDocument, name: str) -> str:
        return gpu.file_url(self.settings, doc, name)


@dataclass
class DirectoryGpu:
    """Aufgezeichnete Antworten aus einem Ordner (Tests, Betrieb ohne Internet): `municipality-<insee>.json`,
    `<endpoint>-<insee>.json`, `document-<id>.json` (Details mit `files`), Dateien unter ihrem Namen."""

    directory: Path
    insee: str = ""

    def _json(self, name: str) -> Any:
        return json.loads((self.directory / name).read_text(encoding="utf-8"))

    def municipality(self, insee: str) -> gpu.Municipality:
        self.insee = insee
        props = self._json(f"municipality-{insee}.json")["features"][0]
        return gpu.Municipality(
            insee, props["properties"]["name"], bool(props["properties"]["is_rnu"]), props["geometry"]
        )

    def features(self, endpoint: str, geometry: dict[str, Any]) -> list[gpu.GpuFeature]:
        path = self.directory / f"{endpoint}-{self.insee}.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [gpu.GpuFeature(endpoint, f["properties"], f["geometry"]) for f in payload["features"]]

    def document(self, gpu_doc_id: str) -> gpu.GpuDocument:
        data = self._json(f"document-{gpu_doc_id}.json")
        return gpu.GpuDocument(
            id=data["id"],
            partition=data["name"],
            du_type=data["type"],
            title=data["title"],
            legal_status=data.get("legalStatus"),
            effective_status=data.get("effectiveStatus"),
            update_date=data.get("updateDate"),
            files=[gpu.GpuFile(f["name"], f["title"], f.get("path")) for f in data["files"]],
        )

    def download(self, url: str) -> bytes:
        return (self.directory / url.rsplit("/", 1)[-1]).read_bytes()

    def file_url(self, doc: gpu.GpuDocument, name: str) -> str:
        return f"https://data.geopf.fr/annexes/gpu/documents/{doc.partition}/{doc.id}/{name}"


@dataclass
class ImportResult:
    commune_insee: str
    status: str
    """`imported`, `refreshed`, `unchanged`, `extended`, `rnu`, `no_document`, `no_regulation`,
    `multiple_regulations`, `no_chapters`."""
    land_use_plan_id: str | None = None
    chapters: int = 0
    zones: int = 0
    notes: list[str] = field(default_factory=list)


def _geometry(value: dict[str, Any]) -> BaseGeometry | None:
    try:
        geom = shape(value)
        return geom if geom.is_valid else geom.buffer(0)
    except (ValueError, TypeError, AttributeError):
        return None


def choose_partition(commune: dict[str, Any], zones: list[gpu.GpuFeature]) -> tuple[str, str] | None:
    """Planwerk (Partition, Dokument) mit der größten Zonenfläche in der Gemeinde.

    Flächen in Grad² genügen für den Vergleich innerhalb einer Gemeinde. Innerhalb einer Partition gilt das
    Dokument mit dem jüngsten `gpu_timestamp`."""
    boundary = _geometry(commune)
    if boundary is None:
        return None
    areas: dict[str, float] = {}
    latest: dict[str, tuple[str, str]] = {}
    for feature in zones:
        partition = str(feature.properties.get("partition") or "")
        doc_id = str(feature.properties.get("gpu_doc_id") or "")
        geom = _geometry(feature.geometry)
        if not partition or not doc_id or geom is None:
            continue
        areas[partition] = areas.get(partition, 0.0) + geom.intersection(boundary).area
        stamp = str(feature.properties.get("gpu_timestamp") or "")
        if partition not in latest or stamp > latest[partition][0]:
            latest[partition] = (stamp, doc_id)
    if not areas:
        return None
    partition = max(areas, key=lambda p: areas[p])
    return partition, latest[partition][1]


def plan_has_results(session: Session, plan_id: Any) -> bool:
    return bool(
        session.execute(
            select(
                exists().where(RuleSet.land_use_plan_id == plan_id, RuleSet.current_version_id.is_not(None))
            )
        ).scalar()
    )


def _set_commune(
    session: Session, insee: str, status: str, plan_id: Any = None, error: str | None = None
) -> None:
    """Stand der Gemeinde setzen. Wechselt der Planstand, bleibt der vorige mit Ergebnissen als Rückfall."""
    row = session.get(RulesCommune, insee)
    if row is None:
        row = RulesCommune(commune_insee=insee, status=status)
        session.add(row)
    previous = row.land_use_plan_id
    if status == "rnu":
        row.fallback_land_use_plan_id = None  # Ohne Bebauungsplan gelten die alten Regeln nicht mehr
    elif previous is not None and previous != plan_id and plan_has_results(session, previous):
        row.fallback_land_use_plan_id = previous
    if plan_id is not None and row.fallback_land_use_plan_id == plan_id:
        row.fallback_land_use_plan_id = None
    row.status = status
    row.land_use_plan_id = plan_id
    row.error = error
    row.checked_at = utcnow()


def record_check_failed(session: Session, insee: str, error: str) -> None:
    """Prüfung im GPU nach allen Versuchen gescheitert (Netz, Dienst). Ein vorhandener Planstand bleibt
    gültig; Kunden verlieren ihre Simulation nicht, weil der GPU kurz nicht erreichbar war."""
    row = session.get(RulesCommune, insee)
    if row is not None and row.land_use_plan_id is not None:
        row.error = f"check_failed:{error}"[:2000]
        row.checked_at = utcnow()
        return
    _set_commune(session, insee, "failed", error=error)


_INSERT_ZONE = text(
    """
    INSERT INTO zone (id, created_by, land_use_plan_id, gpu_gid, code, label, zone_type, commune_insee,
                      chapter_code, geometry)
    SELECT gen_random_uuid(), :actor, :plan, :gid, :code, :label, :zone_type, :insee, :chapter,
           ST_Multi(ST_CollectionExtract(ST_MakeValid(
               ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326), 2154)), 3))
    ON CONFLICT (land_use_plan_id, gpu_gid) DO NOTHING
    """
)
_INSERT_OVERLAY = text(
    """
    INSERT INTO overlay_constraint (id, created_by, land_use_plan_id, commune_insee, endpoint, category,
                                    type_code, label, partition, gpu_gid, effect, geometry)
    SELECT gen_random_uuid(), :actor, :plan, :insee, :endpoint, :category, :type_code, :label, :partition,
           :gid, 'info', ST_MakeValid(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326), 2154))
    ON CONFLICT (land_use_plan_id, endpoint, gpu_gid) DO NOTHING
    """
)


def _overlay_label(props: dict[str, Any]) -> str:
    label = props.get("libelle") or props.get("typeass") or props.get("nomass") or props.get("txt") or ""
    if props.get("suptype"):
        label = f"{str(props['suptype']).upper()} – {label}"
    return str(label)[:500] or "–"


def _store_zones_and_overlays(
    session: Session,
    source: GpuSource,
    plan: LandUsePlan,
    insee: str,
    commune_geom: dict[str, Any],
    zones: list[gpu.GpuFeature],
    chapter_codes: dict[str, str | None],
    notes: list[str],
) -> int:
    """Zonen und Vorgaben der Gemeinde für diesen Planstand; ein früherer Stand derselben Gemeinde wird
    ersetzt (nichts verweist auf diese Zeilen)."""
    session.execute(delete(Zone).where(Zone.land_use_plan_id == plan.id, Zone.commune_insee == insee))
    count = 0
    for feature in zones:
        if feature.properties.get("partition") != plan.partition:
            continue
        code = str(feature.properties.get("libelle") or "").strip()
        gid = feature.properties.get("gid")
        if not code or gid is None:
            notes.append(f"zone_without_code_or_gid:{code or '?'}")
            continue
        session.execute(
            _INSERT_ZONE,
            {
                "actor": ACTOR,
                "plan": plan.id,
                "gid": int(gid),
                "code": code[:20],
                "label": (feature.properties.get("libelong") or None),
                "zone_type": feature.properties.get("typezone"),
                "insee": insee,
                "chapter": chapter_codes.get(code),
                "geojson": json.dumps(feature.geometry),
            },
        )
        count += 1
    for endpoint, category in OVERLAY_CATEGORY.items():
        try:
            overlays = source.features(endpoint, commune_geom)
        except ExternalServiceError as exc:
            notes.append(f"overlays_unavailable:{endpoint}:{exc.reason}")
            continue
        session.execute(
            delete(OverlayConstraint).where(
                OverlayConstraint.land_use_plan_id == plan.id,
                OverlayConstraint.commune_insee == insee,
                OverlayConstraint.endpoint == endpoint,
            )
        )
        for feature in overlays:
            partition = feature.properties.get("partition")
            if category != "servitude" and partition != plan.partition:
                continue
            session.execute(
                _INSERT_OVERLAY,
                {
                    "actor": ACTOR,
                    "plan": plan.id,
                    "insee": insee,
                    "endpoint": endpoint,
                    "category": category,
                    "type_code": str(
                        feature.properties.get("typepsc")
                        or feature.properties.get("typeinf")
                        or feature.properties.get("suptype")
                        or ""
                    )[:20]
                    or None,
                    "label": _overlay_label(feature.properties),
                    "partition": str(partition)[:80] if partition else None,
                    "gid": int(feature.properties.get("gid") or 0),
                    "geojson": json.dumps(feature.geometry),
                },
            )
    return count


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
    enqueue(
        session,
        "rules_extract",
        {"chapter_id": str(chapter.id)},
        idempotency_key=f"rules_extract:{chapter.id}:{input_hash(settings, source_sha256, chapter, kind)}",
        created_by=created_by,
    )


def _zone_stamp(plan_zones: list[gpu.GpuFeature]) -> str | None:
    stamps = [str(z.properties.get("gpu_timestamp") or "") for z in plan_zones]
    return max(stamps, default="") or None


@dataclass
class _Regulation:
    doc: gpu.GpuDocument
    url: str
    filename: str
    data: bytes
    sha256: str
    reader: pdf.PdfText
    structure: Structure


def import_commune(
    session: Session, source: GpuSource, settings: Settings, insee: str, *, force: bool = False
) -> ImportResult:
    municipality = source.municipality(insee)
    if municipality.is_rnu:
        _set_commune(session, insee, "rnu")
        session.commit()
        return ImportResult(insee, "rnu")
    zones = source.features("zone-urba", municipality.geometry)
    chosen = choose_partition(municipality.geometry, zones)
    if chosen is None:
        return _unusable(session, insee, None, "no_document", None)
    partition, doc_id = chosen
    plan_zones = [z for z in zones if z.properties.get("partition") == partition]
    zone_codes = sorted({str(z.properties.get("libelle") or "").strip() for z in plan_zones} - {""})
    stamp = _zone_stamp(plan_zones)

    existing = session.execute(
        select(LandUsePlan).where(LandUsePlan.gpu_doc_id == doc_id)
    ).scalar_one_or_none()
    doc = source.document(doc_id)
    if existing is not None and existing.status == "active" and not force:
        unchanged = existing.gpu_update_date == doc.update_date and existing.gpu_timestamp == stamp
        if unchanged and insee in existing.communes:
            row = session.get(RulesCommune, insee)
            previous_error = row.error if row is not None else None
            _set_commune(session, insee, "ok", existing.id, previous_error)
            session.commit()
            return ImportResult(
                insee, "unchanged", str(existing.id), notes=[previous_error] if previous_error else []
            )
        if unchanged:
            return _extend_plan(
                session, source, settings, existing, insee, municipality.geometry, plan_zones, zone_codes
            )

    regulations = gpu.regulation_files(doc)
    if len(regulations) != 1:
        status = "no_regulation" if not regulations else "multiple_regulations"
        detail = f"document:{doc_id}" + (
            "" if not regulations else ":" + ",".join(f.name for f in regulations)
        )
        return _unusable(session, insee, existing, status, detail)
    url = source.file_url(doc, regulations[0].name)
    data = source.download(url)
    reader = pdf.read_text(data)
    regulation = _Regulation(
        doc,
        url,
        regulations[0].name,
        data,
        hashlib.sha256(data).hexdigest(),
        reader,
        detect_structure(reader.pages),
    )
    chapter_codes = {code: _chapter_code(code, regulation.structure) for code in zone_codes}
    if not any(chapter_codes.values()):
        return _unusable(session, insee, existing, "no_chapters", f"detection:{regulation.structure.method}")

    if existing is not None:
        return _refresh_plan(
            session,
            source,
            settings,
            existing,
            insee,
            municipality.geometry,
            plan_zones,
            chapter_codes,
            regulation,
            stamp,
        )

    plan = LandUsePlan(
        gpu_doc_id=doc.id,
        partition=doc.partition or partition,
        du_type=doc.du_type,
        title=doc.title,
        gpu_timestamp=stamp,
        gpu_update_date=doc.update_date,
        communes=[insee],
        status="importing",
        created_by=ACTOR,
    )
    session.add(plan)
    session.flush()
    source_file = _store_source(session, plan, regulation)
    notes: list[str] = []
    stored_zones = _store_zones_and_overlays(
        session, source, plan, insee, municipality.geometry, plan_zones, chapter_codes, notes
    )
    chapters = _sync_chapters(session, settings, plan, source_file, regulation.structure, notes)
    _activate(session, plan, insee)
    unmatched = sorted(code for code, chapter_code in chapter_codes.items() if chapter_code is None)
    if unmatched:
        notes.append("zones_without_chapter:" + ",".join(unmatched))
    _set_commune(session, insee, "ok", plan.id, "; ".join(notes) or None)
    session.commit()
    log.info(
        "plu_imported", commune=insee, plan=doc.id, chapters=len(chapters), zones=stored_zones, notes=notes
    )
    return ImportResult(insee, "imported", str(plan.id), len(chapters), stored_zones, notes)


def _chapter_code(zone_code: str, structure: Structure) -> str | None:
    found = chapter_for_zone(zone_code, structure.chapters)
    return found.code if found else None


def _unusable(
    session: Session, insee: str, existing: LandUsePlan | None, status: str, error: str | None
) -> ImportResult:
    """Neuer Stand nicht lesbar. Aktualisierung desselben Planstands: der bisherige Stand bleibt unverändert.
    Neues Dokument oder kein Plan: Status der Gemeinde, der bisherige Stand bleibt als Rückfall."""
    row = session.get(RulesCommune, insee)
    if existing is not None and row is not None and row.land_use_plan_id == existing.id:
        row.error = f"{status}:{error}" if error else status
        row.checked_at = utcnow()
        log.warning("plu_refresh_unusable", commune=insee, status=status, error=error)
        session.commit()
        return ImportResult(insee, status, str(existing.id), notes=[row.error])
    _set_commune(session, insee, status, error=error)
    session.commit()
    return ImportResult(insee, status)


def _store_source(session: Session, plan: LandUsePlan, regulation: _Regulation) -> SourceFile:
    """Planunterlage aus dem GPU im Objektspeicher und ihre Seitentexte (`store_source`)."""
    return store_source(
        session,
        plan,
        sha256=regulation.sha256,
        filename=regulation.filename,
        url=regulation.url,
        storage_key=f"rules/{regulation.doc.partition}/{regulation.doc.id}/{regulation.sha256}.pdf",
        size_bytes=len(regulation.data),
        reader=regulation.reader,
        actor=ACTOR,
        data=regulation.data,
    )


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


def _sync_chapters(
    session: Session,
    settings: Settings,
    plan: LandUsePlan,
    source_file: SourceFile,
    structure: Structure,
    notes: list[str],
) -> list[RegulationChapter]:
    """Kapitel des Planstands an die erkannte Struktur und die Zonen aller Gemeinden angleichen
    (`ensure_chapter` je Kapitel mit Sektoren; entfallene Kapitel `failed: chapter_not_detected`)."""
    session.flush()
    zone_rows = session.execute(
        select(Zone.code).where(Zone.land_use_plan_id == plan.id).distinct()
    ).scalars()
    sectors: dict[str, set[str]] = {}
    for code in zone_rows:
        found = chapter_for_zone(code, structure.chapters)
        if found is not None:
            sectors.setdefault(found.code, set()).add(code)
    if sectors:
        # Zonen anderer Gemeinden folgen einer geänderten Kapitelstruktur
        session.execute(
            text(
                "UPDATE zone SET chapter_code = :chapter WHERE land_use_plan_id = :plan AND code = :code "
                "AND chapter_code IS DISTINCT FROM :chapter"
            ),
            [
                {"plan": plan.id, "code": code, "chapter": chapter}
                for chapter, codes in sectors.items()
                for code in codes
            ],
        )
    existing = {
        c.code: c
        for c in session.execute(
            select(RegulationChapter).where(RegulationChapter.land_use_plan_id == plan.id)
        ).scalars()
    }
    detected: dict[str, Chapter] = {c.code: c for c in structure.chapters}
    result: list[RegulationChapter] = []
    for code in sorted(set(existing) | set(sectors)):
        chapter = existing.get(code)
        found = detected.get(code)
        if found is None or code not in sectors:
            if chapter is not None and chapter.sectors:
                chapter.sectors = []
                chapter.status, chapter.error, chapter.updated_at = "failed", "chapter_not_detected", utcnow()
            continue
        values = ChapterValues(
            title=found.title,
            first_page=found.first_page,
            last_page=found.last_page,
            general_pages=structure.general_pages,
            sectors=sorted(sectors[code]),
            detection=structure.method,
        )
        result.append(
            ensure_chapter(
                session,
                settings,
                plan,
                source_file,
                code,
                values,
                chapter,
                actor=ACTOR,
                reason="import",
                notes=notes,
            )
        )
    return result


def _activate(session: Session, plan: LandUsePlan, insee: str) -> None:
    """Planstand für die Gemeinde aktivieren und frühere Planstände dieser Gemeinde ablösen."""
    previous = session.execute(
        select(LandUsePlan).where(
            LandUsePlan.status == "active",
            LandUsePlan.communes.contains([insee]),
            LandUsePlan.id != plan.id,
        )
    ).scalars()
    for old in previous:
        old.communes = [c for c in old.communes if c != insee]
        if not old.communes:
            old.status = "superseded"
            old.superseded_by = plan.id
    plan.communes = sorted({*plan.communes, insee})
    plan.status = "active"
    plan.activated_at = plan.activated_at or utcnow()


def _refresh_plan(
    session: Session,
    source: GpuSource,
    settings: Settings,
    plan: LandUsePlan,
    insee: str,
    commune_geom: dict[str, Any],
    plan_zones: list[gpu.GpuFeature],
    chapter_codes: dict[str, str | None],
    regulation: _Regulation,
    stamp: str | None,
) -> ImportResult:
    """Denselben Planstand an Ort und Stelle aktualisieren (geändertes Datum, `force`, wieder aktiv)."""
    plan.partition = regulation.doc.partition or plan.partition
    plan.du_type = regulation.doc.du_type
    plan.title = regulation.doc.title
    plan.gpu_update_date = regulation.doc.update_date
    plan.gpu_timestamp = stamp
    plan.error = None
    source_file = _store_source(session, plan, regulation)
    notes: list[str] = []
    stored = _store_zones_and_overlays(
        session, source, plan, insee, commune_geom, plan_zones, chapter_codes, notes
    )
    chapters = _sync_chapters(session, settings, plan, source_file, regulation.structure, notes)
    _activate(session, plan, insee)
    unmatched = sorted(code for code, chapter_code in chapter_codes.items() if chapter_code is None)
    if unmatched:
        notes.append("zones_without_chapter:" + ",".join(unmatched))
    _set_commune(session, insee, "ok", plan.id, "; ".join(notes) or None)
    session.commit()
    log.info("plu_refreshed", commune=insee, plan=plan.gpu_doc_id, chapters=len(chapters), notes=notes)
    return ImportResult(insee, "refreshed", str(plan.id), len(chapters), stored, notes)


def _extend_plan(
    session: Session,
    source: GpuSource,
    settings: Settings,
    plan: LandUsePlan,
    insee: str,
    commune_geom: dict[str, Any],
    plan_zones: list[gpu.GpuFeature],
    zone_codes: list[str],
) -> ImportResult:
    """Weitere Gemeinde desselben Planwerks (z. B. PLUi): Zonen ergänzen, Kapitel um Sektoren erweitern."""
    source_file = (
        session.execute(
            select(SourceFile)
            .where(SourceFile.land_use_plan_id == plan.id)
            .order_by(SourceFile.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert source_file is not None
    pages = {
        p.page: p.text
        for p in session.execute(
            select(SourcePage).where(SourcePage.source_file_id == source_file.id)
        ).scalars()
    }
    structure = detect_structure(pages)
    chapter_codes = {code: _chapter_code(code, structure) for code in zone_codes}
    notes: list[str] = []
    stored = _store_zones_and_overlays(
        session, source, plan, insee, commune_geom, plan_zones, chapter_codes, notes
    )
    chapters = _sync_chapters(session, settings, plan, source_file, structure, notes)
    _activate(session, plan, insee)
    _set_commune(session, insee, "ok", plan.id, "; ".join(notes) or None)
    session.commit()
    return ImportResult(insee, "extended", str(plan.id), len(chapters), stored, notes)
