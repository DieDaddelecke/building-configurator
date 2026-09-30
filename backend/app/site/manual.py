"""Grundstück ohne Kataster: frei zeichnen (Weg E, Plan 3.3), aus einer Datei hochladen (AN1) oder nach
einem Scan nachzeichnen (AN7; aus `service.py` gelöst, REFACTORING_PLAN S20)."""

import base64
import json
import math
import uuid
from collections.abc import Sequence
from typing import Any

import shapely
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.platform import scan
from app.platform.logging import get_logger
from app.platform.models import Project
from app.platform.problems import Problem
from app.site.domain import ENGINE_VERSION, pdfplan
from app.site.domain import tolerances as tol
from app.site.domain.edges import (
    Classification,
    EdgeFacts,
    classify,
    split_edges,
)
from app.site.domain.local import rings as local_rings
from app.site.domain.manual import ManualEdgeInput, ManualPolygonInvalid, build_manual_polygon
from app.site.domain.upload import (
    Candidate,
    ParcelFile,
    UploadInvalid,
    build_candidates,
    merge_candidates,
    read_parcel_file,
    upload_provenance,
)
from app.site.models import L93, Site
from app.site.schemas import (
    ScanPreviewOut,
    SiteOut,
    UploadCandidateOut,
    UploadResultOut,
)
from app.site.service import (
    SKETCH_ORIGINS,
    load_site,
)
from app.site.store import (
    add_edges,
    apply_classification,
    db_now,
    enqueue_enrichment,
    hash_outline,
    renewed_site,
)

log = get_logger("site")


def _sketch_classification(polygon: Polygon, area_m2: float, short_piece_m: float = 0.0) -> Classification:
    """Kanten eines Grundstücks ohne Kataster: Geometrie ja, Beobachtungen nein.

    Ohne Nachbarn und ohne Straßenachsen ordnet `classify` jede Kante als `other` mit Vertrauen 0 ein
    und warnt (`no_neighbour_data`, `no_street_edge`, `edges_need_review`). Der Architekt setzt die
    Arten von Hand; erst eine Straßenkante ergibt Hauptstraße und Azimute (UP02). Bei hochgeladenen
    Plänen bilden Stücke unter `short_piece_m` keine eigene Kante (UP18).
    """
    edges = split_edges(polygon, short_piece_m)
    facts = [
        EdgeFacts(neighbour_share=0.0, adjacent=(), street_candidate="none", probe_in_parcel=False)
        for _ in edges
    ]
    return classify(edges, facts, site_area_m2=area_m2, neighbour_coverage="none")


def _store_sketch_site(
    db: Session,
    project_id: uuid.UUID,
    *,
    polygon: Polygon,
    area_m2: float,
    local_origin: tuple[float, float],
    origin: str,
    address_label: str,
    georeferenced: bool,
    source_info: dict[str, Any],
    actor: str,
    short_piece_m: float = 0.0,
) -> SiteOut:
    """Grundstück ohne Kataster speichern, mit Kanten (UP02).

    G2 und G3 werden dafür nicht aufgerufen (D13, G29): kein Baurahmen, kein Steckbrief. Ein
    vorhandenes Grundstück aus dem Kataster wird nicht überschrieben (`site_origin_mismatch`); dafür
    ist ein neues Projekt vorgesehen.
    """
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update())
    site = db.execute(
        select(Site).where(Site.project_id == project_id).with_for_update()
    ).scalar_one_or_none()
    if site is not None and site.origin not in SKETCH_ORIGINS:
        raise Problem(409, "site_origin_mismatch")
    outline_hash = hash_outline(polygon)
    if (
        site is not None
        and site.origin == origin
        and site.outline_hash == outline_hash
        and site.address_label == address_label
    ):
        return load_site(db, project_id)

    site = renewed_site(db, site, project_id, actor)
    classification = _sketch_classification(polygon, area_m2, short_piece_m)
    site.origin = origin
    site.georeferenced = georeferenced
    site.source_info = source_info
    site.address_label = address_label
    site.geometry = from_shape(polygon, srid=L93)
    site.area_m2 = round(area_m2, tol.STORAGE_DECIMALS)
    site.area_official_m2 = None
    site.local_origin_e, site.local_origin_n = local_origin
    site.parcel_idus = []
    site.outline_hash = outline_hash
    site.neighbour_coverage = "none"
    site.road_data = False
    # Gelände und Risiken nur mit echter Lage (AN5, docs/PLAN_AN5_AUSGABE.md 3.2): ohne Lage nie `pending`,
    # weil dann kein site_enrich-Job eingeplant wird
    site.terrain_status = site.risks_status = "pending" if georeferenced else "unavailable"
    site.engine_version = ENGINE_VERSION
    site.updated_by = actor
    site.updated_at = db_now(db)
    apply_classification(site, classification, list(classification.warnings))
    db.flush()
    add_edges(db, site, classification, actor)
    if georeferenced:
        enqueue_enrichment(db, site, project_id, actor)
    db.commit()
    return load_site(db, project_id)


def form_manual_site(
    db: Session,
    project_id: uuid.UUID,
    edges: Sequence[ManualEdgeInput],
    address_label: str,
    actor: str,
    trace: dict[str, Any] | None = None,
) -> SiteOut:
    """Grundstück aus freier Zeichnung und Bemaßung bilden, ohne Kataster (Weg E, Plan 3.3). `trace`: nach
    einem Scan nachgezeichnet, mit Datei, Seite und Maßstabsweg (AN7, PLAN_AN7_SCAN 3.5)."""
    try:
        outline = build_manual_polygon(edges)
    except ManualPolygonInvalid as exc:
        raise Problem(422, "manual_polygon_invalid", detail=str(exc)) from None
    return _store_sketch_site(
        db,
        project_id,
        polygon=outline.polygon,
        area_m2=outline.area_m2,
        local_origin=outline.local_origin,
        origin="manual_sketch",
        address_label=address_label,
        georeferenced=False,
        source_info={"trace": trace} if trace else {},
        actor=actor,
    )


SCAN_RENDER_PX = 4000
"""Lange Seite beim Rendern für die Maßstabssuche: A3 bei etwa 240 dpi (PLAN_AN7_SCAN 3.5)."""


SCAN_PREVIEW_PX = 2500
"""Lange Seite des Bilds zum Nachzeichnen: bei A3 etwa 150 dpi, genug für die Ecken, 0,3–0,8 MB."""


def scan_preview(data: bytes, page: int) -> ScanPreviewOut:
    """Seite eines gescannten Plans als Vorlage zum Nachzeichnen (AN7, PLAN_AN7_SCAN 3.5). Der Maßstab kommt
    aus dem erkannten Text wie bei einem vektoriellen PDF (`scales_in_text`);
    Meter je Pixel nur mit Papiermaß.
    Nichts wird gespeichert: Pläne des Geometers können Namen der Eigentümer enthalten (3.6)."""
    try:
        count = scan.page_count(data)
        if page > count:
            raise Problem(422, "page_out_of_range", page_count=count)
        rendered = scan.render(data, page, max_side_px=SCAN_RENDER_PX)
    except scan.ScanProblem as exc:
        raise Problem(422, str(exc)) from None
    try:
        text_found = scan.recognize(rendered).text
    except scan.ScanProblem as exc:
        # Ohne Texterkennung kein Maßstab aus dem Plan; Kalibrieren über zwei Punkte geht trotzdem
        log.warning("site_scan_ocr_failed", error=str(exc))
        text_found = ""
    found, edition = pdfplan.scales_in_text(text_found)
    scale = edition if edition is not None else (found[0] if len(found) == 1 else None)
    jpeg, (width, height) = scan.to_jpeg(rendered, max_side_px=SCAN_PREVIEW_PX)
    paper = rendered.paper_mm
    metres = paper[0] / 1000 * scale / width if paper is not None and scale is not None else None
    return ScanPreviewOut(
        page=page,
        page_count=count,
        image="data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
        width_px=width,
        height_px=height,
        paper_mm=list(paper) if paper is not None else None,
        scales=sorted(found),
        scale=scale,
        metres_per_px=round(metres, 6) if metres is not None else None,
    )


def _to_l93(db: Session, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """WGS84 nach Lambert-93 über PostGIS, wie überall im Modul."""
    line = json.dumps({"type": "LineString", "coordinates": [[x, y] for x, y in points]})
    wkb = db.execute(
        text("SELECT ST_AsBinary(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326), 2154))"),
        {"g": line},
    ).scalar_one()
    return [(float(x), float(y)) for x, y, *_ in shapely.from_wkb(bytes(wkb)).coords]


def _candidate_out(candidate: Candidate, overview_origin: tuple[float, float]) -> UploadCandidateOut:
    origin = (math.floor(candidate.polygon.bounds[0]), math.floor(candidate.polygon.bounds[1]))
    return UploadCandidateOut(
        index=candidate.index,
        area_m2=round(candidate.area_m2, tol.STORAGE_DECIMALS),
        layer=candidate.layer,
        name=candidate.name,
        crs=candidate.crs,
        georeferenced=candidate.georeferenced,
        outline_local=local_rings(candidate.polygon, origin),
        outline_overview=local_rings(candidate.polygon, overview_origin),
    )


def read_parcel_upload(
    db: Session, file_name: str, data: bytes, scale: int | None = None
) -> tuple[ParcelFile, list[Candidate]]:
    """Konturen einer hochgeladenen Datei, benannte und größte zuerst (AN1, PLAN_AN1 3.2 und 8)."""
    try:
        parcel_file = read_parcel_file(file_name, data, scale)
        return parcel_file, build_candidates(parcel_file.rings, lambda points: _to_l93(db, points))
    except UploadInvalid as exc:
        raise Problem(422, exc.code, detail=str(exc), **exc.extra) from None


def form_uploaded_site(
    db: Session,
    project_id: uuid.UUID,
    *,
    file_name: str,
    data: bytes,
    address_label: str,
    indices: Sequence[int] | None,
    scale: int | None,
    actor: str,
) -> UploadResultOut:
    """Parzelle aus DXF, GeoJSON oder vektoriellem PDF übernehmen (AN1).

    Mehrere Konturen und keine Auswahl: die Kandidaten kommen zurück, das Grundstück entsteht erst im
    zweiten Aufruf mit `indices`. Mehrere gewählte Konturen werden vereinigt (UP17). Die Datei wird nicht
    gespeichert, ihre Herkunft schon (E-AN1-1); bei PDF gehören Maßstab und Seite dazu, damit der Umriss
    nachvollziehbar bleibt (UP14).
    """
    parcel_file, candidates = read_parcel_upload(db, file_name, data, scale)
    scale_info = {"scale": parcel_file.scale, "scale_source": parcel_file.scale_source}
    if not indices:
        if len(candidates) > 1:
            min_x = min(c.polygon.bounds[0] for c in candidates)
            min_y = min(c.polygon.bounds[1] for c in candidates)
            overview = (float(math.floor(min_x)), float(math.floor(min_y)))
            return UploadResultOut(
                site=None,
                candidates=[_candidate_out(c, overview) for c in candidates],
                format=parcel_file.format,
                **scale_info,
            )
        chosen = candidates[0]
        wanted = [chosen.index]
    else:
        by_index = {c.index: c for c in candidates}
        wanted = list(dict.fromkeys(indices))
        if any(i not in by_index for i in wanted):
            raise Problem(422, "upload_outline_not_found")
        try:
            chosen = merge_candidates([by_index[i] for i in wanted])
        except UploadInvalid as exc:
            raise Problem(422, exc.code, detail=str(exc), **exc.extra) from None
    min_x, min_y, _, _ = chosen.polygon.bounds
    source_info = upload_provenance(file_name, data, parcel_file, chosen, wanted)
    site = _store_sketch_site(
        db,
        project_id,
        polygon=chosen.polygon,
        area_m2=chosen.area_m2,
        local_origin=(float(math.floor(min_x)), float(math.floor(min_y))),
        origin="upload",
        address_label=address_label,
        georeferenced=chosen.georeferenced,
        source_info=source_info,
        actor=actor,
        short_piece_m=source_info["short_piece_m"],
    )
    return UploadResultOut(site=site, candidates=[], format=parcel_file.format, **scale_info)
