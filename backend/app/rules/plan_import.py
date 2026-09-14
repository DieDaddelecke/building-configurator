"""Planstand je Gemeinde aus dem GPU importieren (Plan 3.4, Spez. 5.2.1, 5.2.5).

Ablauf: Gemeinde → Zonen → Planwerk mit größter Fläche in der Gemeinde → Dokument → règlement écrit laden,
Text je Seite, Kapitel erkennen → in einer Transaktion speichern → Auswertung je Kapitel als Job.
Ein unveränderter Planstand wird nicht erneut geladen. Ein neuer Stand ersetzt den alten für die Gemeinde;
abgesendete Anfragen behalten ihren Snapshot, offene Projekte sehen beim nächsten Abruf den neuen Stand.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx2
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete, insert, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations import gpu
from app.integrations.http import ExternalServiceError
from app.platform import storage
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.rules import pdf
from app.rules.domain.chapters import CHAPTER_MAX_PAGES, chapter_for_zone, detect_structure
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    RulesCommune,
    SourceFile,
    SourcePage,
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
    """`imported`, `unchanged`, `extended`, `rnu`, `no_document`, `no_regulation`, `no_chapters`."""
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


def _set_commune(
    session: Session, insee: str, status: str, plan_id: Any = None, error: str | None = None
) -> None:
    row = session.get(RulesCommune, insee)
    if row is None:
        row = RulesCommune(commune_insee=insee, status=status)
        session.add(row)
    row.status = status
    row.land_use_plan_id = plan_id
    row.error = error
    row.checked_at = utcnow()


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
    count = 0
    for feature in zones:
        if feature.properties.get("partition") != plan.partition:
            continue
        code = str(feature.properties.get("libelle") or "").strip()
        if not code:
            continue
        session.execute(
            _INSERT_ZONE,
            {
                "actor": ACTOR,
                "plan": plan.id,
                "gid": int(feature.properties.get("gid") or 0),
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


def _enqueue_extraction(session: Session, chapter: RegulationChapter, reason: str) -> None:
    import app.rules.jobs  # noqa: F401  Jobart anmelden (lokal, sonst Importzyklus)

    enqueue(
        session,
        "rules_extract",
        {"chapter_id": str(chapter.id)},
        idempotency_key=f"rules_extract:{chapter.id}:{','.join(sorted(chapter.sectors))}",
        created_by=f"{ACTOR}:{reason}",
    )


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
        _set_commune(session, insee, "no_document")
        session.commit()
        return ImportResult(insee, "no_document")
    partition, doc_id = chosen
    plan_zones = [z for z in zones if z.properties.get("partition") == partition]
    zone_codes = sorted({str(z.properties.get("libelle") or "").strip() for z in plan_zones} - {""})

    existing = session.execute(
        select(LandUsePlan).where(LandUsePlan.gpu_doc_id == doc_id)
    ).scalar_one_or_none()
    if existing is not None and existing.status == "active" and not force:
        if insee in existing.communes:
            row = session.get(RulesCommune, insee)
            previous_error = row.error if row is not None else None
            _set_commune(session, insee, "ok", existing.id, previous_error)
            session.commit()
            return ImportResult(
                insee, "unchanged", str(existing.id), notes=[previous_error] if previous_error else []
            )
        return _extend_plan(session, source, existing, insee, municipality.geometry, plan_zones, zone_codes)
    if existing is not None:
        # Abgebrochener oder erzwungener Import desselben Dokuments: neu aufbauen
        session.execute(delete(LandUsePlan).where(LandUsePlan.id == existing.id))
        session.flush()

    doc = source.document(doc_id)
    regulation = gpu.regulation_file(doc)
    if regulation is None:
        _set_commune(session, insee, "no_regulation", error=f"document:{doc_id}")
        session.commit()
        return ImportResult(insee, "no_regulation")
    url = source.file_url(doc, regulation.name)
    data = source.download(url)
    sha256 = hashlib.sha256(data).hexdigest()
    reader = pdf.read_text(data)
    structure = detect_structure(reader.pages)
    chapters_by_code = {c.code: c for c in structure.chapters}
    chapter_codes: dict[str, str | None] = {}
    sectors: dict[str, list[str]] = {}
    for code in zone_codes:
        found_chapter = chapter_for_zone(code, structure.chapters)
        chapter_codes[code] = found_chapter.code if found_chapter else None
        if found_chapter is not None:
            sectors.setdefault(found_chapter.code, []).append(code)
    if not sectors:
        _set_commune(session, insee, "no_chapters", error=f"detection:{structure.method}")
        session.commit()
        return ImportResult(insee, "no_chapters")

    storage_key = f"rules/{doc.partition}/{doc.id}/{sha256}.pdf"
    storage.put_bytes(storage_key, data, "application/pdf")

    plan = LandUsePlan(
        gpu_doc_id=doc.id,
        partition=doc.partition or partition,
        du_type=doc.du_type,
        title=doc.title,
        gpu_timestamp=str(plan_zones[0].properties.get("gpu_timestamp") or "") or None,
        gpu_update_date=doc.update_date,
        communes=[insee],
        status="importing",
        created_by=ACTOR,
    )
    session.add(plan)
    session.flush()
    source_file = SourceFile(
        land_use_plan_id=plan.id,
        kind="regulation_pdf",
        filename=regulation.name,
        url=url,
        sha256=sha256,
        storage_key=storage_key,
        size_bytes=len(data),
        page_count=len(reader.pages),
        empty_pages=reader.empty_pages,
        created_by=ACTOR,
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
    notes: list[str] = []
    stored_zones = _store_zones_and_overlays(
        session, source, plan, insee, municipality.geometry, plan_zones, chapter_codes, notes
    )
    chapters: list[RegulationChapter] = []
    for code, codes in sorted(sectors.items()):
        found = chapters_by_code[code]
        if len(found.pages) + len(structure.general_pages) > CHAPTER_MAX_PAGES:
            notes.append(f"chapter_too_long:{code}")
        chapter = RegulationChapter(
            land_use_plan_id=plan.id,
            source_file_id=source_file.id,
            code=code,
            title=found.title[:300],
            first_page=found.first_page,
            last_page=found.last_page,
            general_pages=structure.general_pages,
            sectors=sorted(codes),
            detection=structure.method,
            created_by=ACTOR,
        )
        session.add(chapter)
        chapters.append(chapter)
    session.flush()

    # Frühere Planstände dieser Gemeinde ablösen
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
    plan.status = "active"
    plan.activated_at = utcnow()
    unmatched = sorted(code for code, chapter_code in chapter_codes.items() if chapter_code is None)
    if unmatched:
        notes.append("zones_without_chapter:" + ",".join(unmatched))
    _set_commune(session, insee, "ok", plan.id, "; ".join(notes) or None)
    for chapter in chapters:
        _enqueue_extraction(session, chapter, "import")
    session.commit()
    log.info(
        "plu_imported", commune=insee, plan=doc.id, chapters=len(chapters), zones=stored_zones, notes=notes
    )
    return ImportResult(insee, "imported", str(plan.id), len(chapters), stored_zones, notes)


def _extend_plan(
    session: Session,
    source: GpuSource,
    plan: LandUsePlan,
    insee: str,
    commune_geom: dict[str, Any],
    plan_zones: list[gpu.GpuFeature],
    zone_codes: list[str],
) -> ImportResult:
    """Weitere Gemeinde desselben Planwerks (z. B. PLUi): Zonen ergänzen, Kapitel um Sektoren erweitern."""
    chapters = list(
        session.execute(
            select(RegulationChapter).where(RegulationChapter.land_use_plan_id == plan.id)
        ).scalars()
    )
    source_file = session.execute(
        select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)
    ).scalar_one()
    pages = {
        p.page: p.text
        for p in session.execute(
            select(SourcePage).where(SourcePage.source_file_id == source_file.id)
        ).scalars()
    }
    structure = detect_structure(pages)
    chapter_codes: dict[str, str | None] = {}
    by_code = {c.code: c for c in chapters}
    for code in zone_codes:
        found = chapter_for_zone(code, structure.chapters)
        chapter_codes[code] = found.code if found else None
        if found is None:
            continue
        chapter = by_code.get(found.code)
        if chapter is None:
            chapter = RegulationChapter(
                land_use_plan_id=plan.id,
                source_file_id=source_file.id,
                code=found.code,
                title=found.title[:300],
                first_page=found.first_page,
                last_page=found.last_page,
                general_pages=structure.general_pages,
                sectors=[],
                detection=structure.method,
                created_by=ACTOR,
            )
            session.add(chapter)
            by_code[found.code] = chapter
        if code not in chapter.sectors:
            chapter.sectors = sorted({*chapter.sectors, code})
            chapter.status = "pending"
    notes: list[str] = []
    stored = _store_zones_and_overlays(
        session, source, plan, insee, commune_geom, plan_zones, chapter_codes, notes
    )
    plan.communes = sorted({*plan.communes, insee})
    session.flush()
    for chapter in by_code.values():
        if chapter.status == "pending":
            _enqueue_extraction(session, chapter, "extend")
    _set_commune(session, insee, "ok", plan.id, "; ".join(notes) or None)
    session.commit()
    return ImportResult(insee, "extended", str(plan.id), len(by_code), stored, notes)
