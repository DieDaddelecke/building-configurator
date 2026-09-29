"""Anwendungsfälle des Moduls G1 (Plan 3.3). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Geometrie wird in PostGIS gesucht und transformiert, in Shapely (Lambert-93) berechnet.
"""

import base64
import hashlib
import json
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import shapely
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.platform import audit, scan
from app.platform import projects as platform_projects
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.platform.models import Project
from app.platform.problems import Problem
from app.site.domain import ENGINE_VERSION, pdfplan, position
from app.site.domain import tolerances as tol
from app.site.domain.edges import (
    Classification,
    EdgeFacts,
    EdgeGeometry,
    NeighbourCoverage,
    NeighbourParcel,
    Override,
    OverrideKind,
    RoadLine,
    classify,
    edge_facts,
    split_edges,
)
from app.site.domain.manual import ManualEdgeInput, ManualPolygonInvalid, build_manual_polygon
from app.site.domain.outline import ParcelInput, SiteNotContiguous, merge_parcels, to_local
from app.site.domain.upload import (
    Candidate,
    ParcelFile,
    UploadInvalid,
    build_candidates,
    merge_candidates,
    read_parcel_file,
    short_piece_m_for,
)
from app.site.models import L93, Site, SiteEdge, SiteParcel, SiteRisk, Terrain
from app.site.schemas import (
    CommuneOut,
    ContextOut,
    EdgeOut,
    LocalOrigin,
    LocalRing,
    LookupIn,
    LookupOut,
    ParcelOut,
    ParcelSummary,
    PositionIn,
    RiskOut,
    RisksOut,
    ScanPreviewOut,
    SiteOut,
    SitePlacementOut,
    SiteReviewItem,
    TerrainOut,
    UploadCandidateOut,
    UploadResultOut,
)

FEATURE_FLAG = "site_selection"
SOURCE = "etalab_cadastre"
ACCURACY_CLASS = "cadastre_vector"
MAX_BBOX_DEG = (0.03, 0.02)
"""Größte Kartenausdehnung für Parzellen (Längen- und Breitengrad), rund 2,3 × 2,2 km."""
MAX_BBOX_FEATURES = 4000
REVIEW_WARNINGS = [
    "customer_corrections_unconfirmed",
    "edges_need_review",
    "corner_lot",
    "flag_lot",
    "no_street_edge",
    "no_neighbour_data",
    "neighbour_data_incomplete",
]

log = get_logger("site")


# ---------------------------------------------------------------------------
# Einzugsgebiet und Parzellensuche
# ---------------------------------------------------------------------------


def service_area(db: Session) -> list[CommuneOut]:
    rows = db.execute(
        text(
            "SELECT insee, name, release, imported_at, ST_XMin(b) AS x0, ST_YMin(b) AS y0, "
            "ST_XMax(b) AS x1, ST_YMax(b) AS y1 "
            "FROM (SELECT *, Box2D(ST_Transform(geometry, 4326)) AS b FROM ref_commune) AS c ORDER BY name"
        )
    ).all()
    return [
        CommuneOut(
            insee=r.insee,
            name=r.name,
            bbox=(round(r.x0, 6), round(r.y0, 6), round(r.x1, 6), round(r.y1, 6)),
            release=r.release,
            imported_at=r.imported_at,
        )
        for r in rows
    ]


def communes_in_service_area(db: Session, codes: set[str]) -> set[str]:
    if not codes:
        return set()
    rows = db.execute(text("SELECT insee FROM ref_commune WHERE insee = ANY(:codes)"), {"codes": list(codes)})
    return {r.insee for r in rows}


def parcels_in_bbox(db: Session, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Parzellen als GeoJSON (WGS84) für die Karte. Dieselben Daten, die ausgewählt werden (Plan 3.3)."""
    x0, y0, x1, y1 = bbox
    if not (x0 < x1 and y0 < y1) or x1 - x0 > MAX_BBOX_DEG[0] or y1 - y0 > MAX_BBOX_DEG[1]:
        raise Problem(422, "bbox_too_large")
    rows = db.execute(
        text(
            """
            WITH env AS (SELECT ST_Transform(ST_MakeEnvelope(:x0, :y0, :x1, :y1, 4326), 2154) AS g)
            SELECT p.idu, p.section, p.number, p.commune_insee, p.area_official_m2,
                   ST_AsGeoJSON(ST_Transform(p.geometry, 4326), 7) AS geojson
            FROM ref_parcel p, env
            WHERE p.geometry && env.g AND ST_Intersects(p.geometry, env.g)
            ORDER BY p.idu
            LIMIT :limit
            """
        ),
        {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "limit": MAX_BBOX_FEATURES + 1},
    ).all()
    truncated = len(rows) > MAX_BBOX_FEATURES
    return {
        "type": "FeatureCollection",
        "truncated": truncated,
        "features": [
            {
                "type": "Feature",
                "id": r.idu,
                "geometry": json.loads(r.geojson),
                "properties": {
                    "idu": r.idu,
                    "section": r.section,
                    "number": r.number,
                    "commune_insee": r.commune_insee,
                    "area_official_m2": r.area_official_m2,
                },
            }
            for r in rows[:MAX_BBOX_FEATURES]
        ],
    }


def lookup(db: Session, body: LookupIn) -> LookupOut:
    """Parzelle am Punkt, sonst alle im Umkreis von 20 m (Adresspunkte liegen oft auf der Straße, 5.1.1)."""
    select_cols = (
        "p.idu, p.commune_insee, p.prefix, p.section, p.number, p.area_official_m2, "
        "ST_AsGeoJSON(ST_Transform(p.geometry, 4326), 7) AS geojson"
    )
    if body.lon is not None and body.lat is not None:
        point = "ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 2154)"
        params: dict[str, Any] = {"lon": body.lon, "lat": body.lat, "radius": tol.LOOKUP_RADIUS_M}
        in_area = bool(
            db.execute(
                text(f"SELECT EXISTS (SELECT 1 FROM ref_commune WHERE ST_Intersects(geometry, {point}))"),  # noqa: S608
                params,
            ).scalar()
        )
        rows = db.execute(
            text(
                f"""
                SELECT {select_cols}, ST_Distance(p.geometry, pt.g) AS distance
                FROM ref_parcel p, (SELECT {point} AS g) AS pt
                WHERE ST_DWithin(p.geometry, pt.g, :radius)
                ORDER BY distance, p.idu LIMIT 10
                """  # noqa: S608  feste Ausdrücke, Werte gebunden
            ),
            params,
        ).all()
    else:
        assert body.commune_insee and body.section and body.number
        params = {
            "commune": body.commune_insee,
            "section": body.section.upper().rjust(2, "0"),
            "number": body.number.rjust(4, "0"),
        }
        in_area = bool(
            db.execute(
                text("SELECT EXISTS (SELECT 1 FROM ref_commune WHERE insee = :commune)"), params
            ).scalar()
        )
        rows = db.execute(
            text(
                f"SELECT {select_cols}, 0.0 AS distance FROM ref_parcel p "  # noqa: S608
                "WHERE p.commune_insee = :commune AND p.section = :section AND p.number = :number "
                "ORDER BY p.prefix LIMIT 10"
            ),
            params,
        ).all()
    candidates = [
        ParcelSummary(
            idu=r.idu,
            commune_insee=r.commune_insee,
            prefix=r.prefix,
            section=r.section,
            number=r.number,
            area_official_m2=r.area_official_m2,
            distance_m=round(float(r.distance), 2),
            geometry_geojson=json.loads(r.geojson),
        )
        for r in rows
    ]
    contained = candidates[0].idu if candidates and candidates[0].distance_m == 0 else None
    return LookupOut(in_service_area=in_area, contained_idu=contained, candidates=candidates)


# ---------------------------------------------------------------------------
# Grundstück bilden
# ---------------------------------------------------------------------------


def _outline_hash(geometry: BaseGeometry) -> str:
    return hashlib.sha256(shapely.to_wkb(geometry, hex=False)).hexdigest()


def _neighbour_coverage(db: Session, site_wkb: bytes, count: int) -> NeighbourCoverage:
    if count == 0:
        return "none"
    covered = db.execute(
        text(
            "SELECT ST_Covers(ST_Union(geometry), ST_Buffer(ST_GeomFromWKB(:site, 2154), :radius)) "
            "FROM ref_commune WHERE ST_DWithin(geometry, ST_GeomFromWKB(:site, 2154), :radius)"
        ),
        {"site": site_wkb, "radius": tol.NEIGHBOUR_SEARCH_M},
    ).scalar()
    return "complete" if covered else "partial"


def form_site(db: Session, project_id: uuid.UUID, idus: list[str], actor: str) -> SiteOut:
    """Grundstück aus Parzellen bilden oder ersetzen (`PUT …/site`); gleiche Auswahl ändert nichts."""
    rows = db.execute(
        text(
            "SELECT idu, commune_insee, prefix, section, number, area_official_m2, release, "
            "ST_AsBinary(geometry) AS wkb FROM ref_parcel WHERE idu = ANY(:idus) ORDER BY idu"
        ),
        {"idus": idus},
    ).all()
    missing = sorted(set(idus) - {r.idu for r in rows})
    if missing:
        raise Problem(422, "parcel_not_found", missing=missing)
    shapes = {r.idu: shapely.from_wkb(bytes(r.wkb)) for r in rows}
    try:
        outline = merge_parcels([ParcelInput(r.idu, shapes[r.idu], r.area_official_m2) for r in rows])
    except SiteNotContiguous:
        raise Problem(422, "site_not_contiguous") from None

    # Projektzeile sperren: zwei gleichzeitige erste PUT (Doppelklick) legten sonst beide ein Grundstück an
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update())
    site = db.execute(
        select(Site).where(Site.project_id == project_id).with_for_update()
    ).scalar_one_or_none()
    if site is not None and site.origin in SKETCH_ORIGINS:
        raise Problem(409, "site_origin_mismatch")
    outline_hash = _outline_hash(outline.polygon)
    if site is not None and site.outline_hash == outline_hash and sorted(site.parcel_idus) == idus:
        return load_site(db, project_id)

    site_wkb = shapely.to_wkb(outline.polygon, hex=False)
    neighbour_rows = db.execute(
        text(
            """
            SELECT p.idu, ST_AsBinary(p.geometry) AS wkb,
                   EXISTS (SELECT 1 FROM ref_building b
                           WHERE b.geometry && p.geometry
                             AND ST_Area(ST_Intersection(b.geometry, p.geometry)) >= 5) AS has_building
            FROM ref_parcel p
            WHERE ST_DWithin(p.geometry, ST_GeomFromWKB(:site, 2154), :radius) AND p.idu <> ALL(:idus)
            """
        ),
        {"site": site_wkb, "radius": tol.NEIGHBOUR_SEARCH_M, "idus": idus},
    ).all()
    neighbours = [
        NeighbourParcel(r.idu, shapely.from_wkb(bytes(r.wkb)), bool(r.has_building)) for r in neighbour_rows
    ]
    coverage = _neighbour_coverage(db, site_wkb, len(neighbours))
    communes = sorted({r.commune_insee for r in rows})
    road_data = bool(
        db.execute(
            text("SELECT EXISTS (SELECT 1 FROM ref_road WHERE commune_insee = ANY(:communes))"),
            {"communes": communes},
        ).scalar()
    )
    roads: list[RoadLine] | None = None
    if road_data:
        road_rows = db.execute(
            text(
                "SELECT DISTINCT ON (cleabs) name, ST_AsBinary(geometry) AS wkb FROM ref_road "
                "WHERE ST_DWithin(geometry, ST_GeomFromWKB(:site, 2154), :radius) ORDER BY cleabs"
            ),
            {"site": site_wkb, "radius": tol.NEIGHBOUR_SEARCH_M},
        ).all()
        roads = [RoadLine(r.name, cast(Any, shapely.from_wkb(bytes(r.wkb)))) for r in road_rows]
    edges = split_edges(outline.polygon)
    facts = edge_facts(edges, neighbours, roads, outline.polygon)
    classification = classify(edges, facts, site_area_m2=outline.area_m2, neighbour_coverage=coverage)
    warnings = [*classification.warnings, *(["area_mismatch"] if outline.area_mismatch else [])]

    if site is None:
        site = Site(project_id=project_id, created_by=actor, revision=1)
        db.add(site)
    else:
        site.revision += 1
        for model in (SiteParcel, SiteEdge, Terrain, SiteRisk):
            db.execute(delete(model).where(model.site_id == site.id))
    site.geometry = from_shape(outline.polygon, srid=L93)
    site.area_m2 = round(outline.area_m2, tol.STORAGE_DECIMALS)
    site.area_official_m2 = outline.area_official_m2
    site.local_origin_e, site.local_origin_n = outline.local_origin
    site.parcel_idus = idus
    site.outline_hash = outline_hash
    site.neighbour_coverage = coverage
    site.road_data = road_data
    site.terrain_status = "pending"
    site.risks_status = "pending"
    site.engine_version = ENGINE_VERSION
    site.updated_by = actor
    site.updated_at = _db_now(db)
    _apply_classification(site, classification, warnings)
    db.flush()

    for r in rows:
        geometry = shapes[r.idu]
        db.add(
            SiteParcel(
                site_id=site.id,
                idu=r.idu,
                commune_insee=r.commune_insee,
                prefix=r.prefix,
                section=r.section,
                number=r.number,
                geometry=from_shape(geometry, srid=L93),
                area_official_m2=r.area_official_m2,
                area_geometric_m2=round(float(geometry.area), tol.STORAGE_DECIMALS),
                source=SOURCE,
                release=r.release,
                accuracy_class=ACCURACY_CLASS,
                created_by=actor,
            )
        )
    for edge in classification.edges:
        geometry = edge.geometry
        db.add(
            SiteEdge(
                site_id=site.id,
                seq=geometry.seq,
                ring=geometry.ring,
                geometry=from_shape(shapely.LineString(geometry.coords), srid=L93),
                length_m=round(geometry.length_m, tol.STORAGE_DECIMALS),
                normal_azimuth_deg=round(geometry.normal_azimuth_deg, 2),
                kind=edge.kind,
                kind_auto=edge.kind_auto,
                override_kind=None,
                classification_source="auto",
                confidence=edge.confidence,
                neighbour_share=edge.facts.neighbour_share,
                street_candidate=edge.facts.street_candidate,
                probe_in_parcel=edge.facts.probe_in_parcel,
                road_share=edge.facts.road_share,
                street_name=edge.facts.street_name,
                adjacent=list(edge.facts.adjacent),
                created_by=actor,
            )
        )
    enqueue(
        db,
        "site_enrich",
        {"site_id": str(site.id), "outline_hash": outline_hash},
        idempotency_key=f"site_enrich:{site.id}:{site.revision}",
        project_id=project_id,
        created_by=actor,
    )
    db.commit()
    return load_site(db, project_id)


def _db_now(db: Session) -> Any:
    """Zeitstempel der Datenbank, damit `updated_at` und Transaktionszeit übereinstimmen."""
    return db.execute(text("SELECT now()")).scalar_one()


def _apply_classification(site: Site, classification: Classification, warnings: list[str]) -> None:
    site.main_street_seq = classification.main_street_seq
    site.street_azimuth_deg = classification.street_azimuth_deg
    site.garden_azimuth_deg = classification.garden_azimuth_deg
    site.warnings = list(dict.fromkeys(warnings))


# ---------------------------------------------------------------------------
# Grundstück ohne Kataster: frei zeichnen (Weg E, Plan 3.3) oder hochladen (AN1)
# ---------------------------------------------------------------------------

SKETCH_ORIGINS = ("manual_sketch", "upload")
"""Herkünfte ohne Kataster: keine Nachbarn, kein Gelände, keine Risiken, keine Zonensuche."""


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
    outline_hash = _outline_hash(polygon)
    if (
        site is not None
        and site.origin == origin
        and site.outline_hash == outline_hash
        and site.address_label == address_label
    ):
        return load_site(db, project_id)

    if site is None:
        site = Site(project_id=project_id, created_by=actor, revision=1)
        db.add(site)
    else:
        site.revision += 1
        for model in (SiteParcel, SiteEdge, Terrain, SiteRisk):
            db.execute(delete(model).where(model.site_id == site.id))
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
    site.updated_at = _db_now(db)
    _apply_classification(site, classification, list(classification.warnings))
    db.flush()
    for edge in classification.edges:
        geometry = edge.geometry
        db.add(
            SiteEdge(
                site_id=site.id,
                seq=geometry.seq,
                ring=geometry.ring,
                geometry=from_shape(shapely.LineString(geometry.coords), srid=L93),
                length_m=round(geometry.length_m, tol.STORAGE_DECIMALS),
                normal_azimuth_deg=round(geometry.normal_azimuth_deg, 2),
                kind=edge.kind,
                kind_auto=edge.kind_auto,
                override_kind=None,
                classification_source="auto",
                confidence=edge.confidence,
                neighbour_share=edge.facts.neighbour_share,
                street_candidate=edge.facts.street_candidate,
                probe_in_parcel=edge.facts.probe_in_parcel,
                road_share=edge.facts.road_share,
                street_name=edge.facts.street_name,
                adjacent=list(edge.facts.adjacent),
                created_by=actor,
            )
        )
    if georeferenced:
        _enqueue_enrichment(db, site, project_id, actor)
    db.commit()
    return load_site(db, project_id)


def _enqueue_enrichment(db: Session, site: Site, project_id: uuid.UUID, actor: str) -> None:
    enqueue(
        db,
        "site_enrich",
        {"site_id": str(site.id), "outline_hash": site.outline_hash},
        idempotency_key=f"site_enrich:{site.id}:{site.revision}",
        project_id=project_id,
        created_by=actor,
    )


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
        outline_local=_rings(candidate.polygon, origin),
        outline_overview=_rings(candidate.polygon, overview_origin),
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
    source_info: dict[str, Any] = {
        "file_name": file_name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "format": parcel_file.format,
        "layer": chosen.layer,
        "name": chosen.name,
        "index": chosen.index,
        "crs": chosen.crs,
        # Kurze Stücke bilden keine eigene Kante (UP18); die Schwelle gehört zur Herkunft
        "short_piece_m": short_piece_m_for(parcel_file.scale),
    }
    if len(wanted) > 1:
        # Herkunft der Vereinigung (UP17, L3): welche Konturen der Datei das Grundstück bilden
        source_info |= {"index": None, "indices": wanted}
    if parcel_file.format == "pdf":
        source_info |= {**scale_info, "page": parcel_file.page}
    if chosen.georeferenced:
        # Lage aus der Datei, bis der Architekt sie korrigiert (AN5, 3.2)
        source_info["position"] = {"method": "file"}
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


# ---------------------------------------------------------------------------
# Lage setzen (AN5, docs/PLAN_AN5_AUSGABE.md 3.2)
# ---------------------------------------------------------------------------


def _l93_and_convergence(db: Session, lon: float, lat: float) -> tuple[tuple[float, float], float]:
    """Punkt in Lambert-93 und Gitterkonvergenz γ dort: Gitterazimut der Strecke 100 m nach Norden."""
    row = db.execute(
        text(
            "WITH p AS (SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS g), "
            "t AS (SELECT ST_Transform(g, 2154) AS a, "
            "ST_Transform(ST_Project(g::geography, 100, 0)::geometry, 2154) AS b FROM p) "
            "SELECT ST_X(a) AS ax, ST_Y(a) AS ay, ST_X(b) AS bx, ST_Y(b) AS by FROM t"
        ),
        {"lon": lon, "lat": lat},
    ).one()
    start = (float(row.ax), float(row.ay))
    return start, position.signed(position.azimuth(start, (float(row.bx), float(row.by))))


def _wgs84_of(db: Session, point: tuple[float, float]) -> tuple[float, float]:
    row = db.execute(
        text(
            "SELECT ST_X(g) AS lon, ST_Y(g) AS lat FROM "
            "(SELECT ST_Transform(ST_SetSRID(ST_MakePoint(:x, :y), 2154), 4326) AS g) AS s"
        ),
        {"x": point[0], "y": point[1]},
    ).one()
    return float(row.lon), float(row.lat)


def _placement(db: Session, site: Site) -> SitePlacementOut:
    """Drehpunkt und Darstellung auf der Karte: ohne Lage Blattoben = Norden, mit Lage folgen die lokalen
    Achsen Gitternord, die Karte dreht sie um −γ."""
    centre = position.pivot(cast(Polygon, to_shape(site.geometry)))
    local = list(to_local(centre, (site.local_origin_e, site.local_origin_n)))
    if not site.georeferenced:
        return SitePlacementOut(pivot_local=local, map_rotation_deg=0.0)
    lon, lat = _wgs84_of(db, centre)
    _, gamma = _l93_and_convergence(db, lon, lat)
    return SitePlacementOut(
        pivot_local=local, pivot_wgs84=[round(lon, 7), round(lat, 7)], map_rotation_deg=round(-gamma, 4)
    )


def position_site(db: Session, project_id: uuid.UUID, body: PositionIn, actor: str) -> SiteOut:
    """Grundstück ohne Kataster verorten oder die Lage korrigieren: starr drehen und verschieben, Maße,
    Fläche und Einordnung der Kanten bleiben. Danach Gelände und Risiken abfragen (3.2, 3.3)."""
    site = _locked_site(db, project_id, body.expected_revision)
    if site.origin not in SKETCH_ORIGINS:
        raise Problem(409, "site_position_parcel")
    polygon = cast(Polygon, to_shape(site.geometry))
    centre = position.pivot(polygon)
    map_rotation = 0.0
    if site.georeferenced:
        _, gamma_old = _l93_and_convergence(db, *_wgs84_of(db, centre))
        map_rotation = -gamma_old
    target, gamma = _l93_and_convergence(db, body.lon, body.lat)
    theta = position.rotation(map_rotation, body.rotation_deg, gamma)

    moved = cast(Polygon, position.turn(polygon, centre, target, theta))
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    for edge in edges:
        edge.geometry = from_shape(position.turn(to_shape(edge.geometry), centre, target, theta), srid=L93)
        edge.normal_azimuth_deg = cast(float, position.turn_azimuth(edge.normal_azimuth_deg, theta))
    site.street_azimuth_deg = position.turn_azimuth(site.street_azimuth_deg, theta)
    site.garden_azimuth_deg = position.turn_azimuth(site.garden_azimuth_deg, theta)

    previous = dict((site.source_info or {}).get("position") or {})
    was_georeferenced = site.georeferenced
    turned = float(previous.get("rotation_deg") or 0.0) + body.rotation_deg
    min_x, min_y, _, _ = moved.bounds
    site.geometry = from_shape(moved, srid=L93)
    site.local_origin_e, site.local_origin_n = float(math.floor(min_x)), float(math.floor(min_y))
    site.georeferenced = True
    site.outline_hash = _outline_hash(moved)
    site.revision += 1
    site.source_info = {
        **(site.source_info or {}),
        "position": {
            "method": "map",
            "lon": round(body.lon, 7),
            "lat": round(body.lat, 7),
            "rotation_deg": round(position.signed(turned), 2),
            "convergence_deg": round(gamma, 4),
            "at": _db_now(db).isoformat(),
            "by": actor,
        },
    }
    for model in (Terrain, SiteRisk):
        db.execute(delete(model).where(model.site_id == site.id))
    site.terrain_status = site.risks_status = "pending"
    site.updated_by = actor
    site.updated_at = _db_now(db)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="site.position",
        entity_type="site",
        entity_id=str(site.id),
        before={"georeferenced": was_georeferenced, "position": previous or None},
        after={"position": site.source_info["position"]},
    )
    db.flush()
    _enqueue_enrichment(db, site, project_id, actor)
    db.commit()
    return load_site(db, project_id)


# ---------------------------------------------------------------------------
# Kanten korrigieren
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Actor:
    type: str  # "customer" | "staff"
    id: str
    role: str  # "customer" | "architect"


def _locked_site(db: Session, project_id: uuid.UUID, expected_revision: int | None) -> Site:
    site = db.execute(
        select(Site).where(Site.project_id == project_id).with_for_update()
    ).scalar_one_or_none()
    if site is None:
        raise Problem(404, "site_not_found")
    if expected_revision is not None and expected_revision != site.revision:
        raise Problem(409, "revision_conflict", revision=site.revision)
    return site


def _reclassify(
    db: Session, site: Site, edges: list[SiteEdge], overrides: dict[int, Override]
) -> Classification:
    geometries = [
        EdgeGeometry(
            seq=e.seq,
            ring=e.ring,
            coords=tuple((float(x), float(y)) for x, y, *_ in to_shape(e.geometry).coords),
        )
        for e in edges
    ]
    facts = [
        EdgeFacts(
            neighbour_share=e.neighbour_share,
            adjacent=tuple(e.adjacent),
            street_candidate=cast(Any, e.street_candidate),
            probe_in_parcel=e.probe_in_parcel,
            road_share=e.road_share,
            street_name=e.street_name,
        )
        for e in edges
    ]
    return classify(
        geometries,
        facts,
        overrides,
        site_area_m2=site.area_m2,
        neighbour_coverage=cast(NeighbourCoverage, site.neighbour_coverage),
    )


def _current_overrides(edges: list[SiteEdge]) -> dict[int, Override]:
    return {
        e.seq: Override(cast(OverrideKind, e.override_kind), cast(Any, e.classification_source))
        for e in edges
        if e.override_kind is not None
    }


def _store(
    db: Session, site: Site, edges: list[SiteEdge], classification: Classification, actor: Actor
) -> None:
    by_seq = {e.geometry.seq: e for e in classification.edges}
    for row in edges:
        result = by_seq[row.seq]
        changed = (row.kind, row.classification_source, row.override_kind, row.confidence) != (
            result.kind,
            result.source,
            result.override,
            result.confidence,
        )
        row.kind = result.kind
        row.kind_auto = result.kind_auto
        row.classification_source = result.source
        row.override_kind = result.override
        row.confidence = result.confidence
        if changed:
            row.updated_at = _db_now(db)
            row.updated_by = actor.id
    warnings = [*classification.warnings]
    if "area_mismatch" in site.warnings:
        warnings.append("area_mismatch")
    _apply_classification(site, classification, warnings)
    site.engine_version = ENGINE_VERSION  # vollständig neu eingeordnet
    site.revision += 1
    site.updated_at = _db_now(db)
    site.updated_by = actor.id


def correct_edge(
    db: Session,
    project_id: uuid.UUID,
    seq: int,
    kind: OverrideKind | None,
    actor: Actor,
    expected_revision: int | None = None,
) -> SiteOut:
    """Kantenart überschreiben oder mit `None` auf automatisch zurücksetzen (Spez. 5.1.4.6, Plan 3.3)."""
    site = _locked_site(db, project_id, expected_revision)
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    target = next((e for e in edges if e.seq == seq), None)
    if target is None:
        raise Problem(404, "edge_not_found")
    if actor.role == "customer":
        if target.ring > 0:
            raise Problem(422, "edge_not_correctable")
        if target.classification_source == "architect":
            raise Problem(409, "edge_confirmed_by_architect")
    overrides = _current_overrides(edges)
    before = {"seq": seq, "kind": target.kind, "source": target.classification_source}
    if kind is None:
        overrides.pop(seq, None)
    else:
        overrides[seq] = Override(kind, "customer" if actor.role == "customer" else "architect")
    classification = _reclassify(db, site, edges, overrides)
    _store(db, site, edges, classification, actor)
    audit.record(
        db,
        actor_type="customer" if actor.role == "customer" else "staff",
        actor_id=actor.id,
        action="site_edge.correct",
        entity_type="site",
        entity_id=str(site.id),
        before=before,
        after={
            "seq": seq,
            "kind": target.kind,
            "source": target.classification_source,
            "revision": site.revision,
        },
    )
    db.commit()
    return load_site(db, project_id)


def confirm_customer_edges(
    db: Session, project_id: uuid.UUID, actor: Actor, expected_revision: int | None = None
) -> SiteOut:
    """Architekt übernimmt alle Kundenkorrekturen; der Baurahmen wird damit bindend (Plan 3.3)."""
    site = _locked_site(db, project_id, expected_revision)
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    confirmed = [e.seq for e in edges if e.classification_source == "customer"]
    if not confirmed:
        return load_site(db, project_id)
    overrides = {
        seq: Override(o.kind, "architect" if o.source == "customer" else o.source)
        for seq, o in _current_overrides(edges).items()
    }
    classification = _reclassify(db, site, edges, overrides)
    _store(db, site, edges, classification, actor)
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor.id,
        action="site_edge.confirm_customer",
        entity_type="site",
        entity_id=str(site.id),
        after={"seqs": confirmed, "revision": site.revision},
    )
    db.commit()
    return load_site(db, project_id)


def retry_enrichment(db: Session, actor: str) -> int:
    """Gelände und Risiken erneut abfragen, wo sie nach einem Ausfall `unavailable` sind (BETRIEB.md 8)."""
    sites = list(
        db.execute(
            select(Site)
            .where((Site.terrain_status == "unavailable") | (Site.risks_status == "unavailable"))
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for site in sites:
        if site.terrain_status == "unavailable":
            site.terrain_status = "pending"
        if site.risks_status == "unavailable":
            site.risks_status = "pending"
        enqueue(
            db,
            "site_enrich",
            {"site_id": str(site.id), "outline_hash": site.outline_hash},
            idempotency_key=f"site_enrich_retry:{site.id}:{site.revision}:{_db_now(db).isoformat()}",
            project_id=site.project_id,
            created_by=actor,
        )
    db.commit()
    return len(sites)


def review_queue(
    db: Session, *, only_corrections: bool = True, require_inquiry: bool = True, limit: int = 200
) -> list[SiteReviewItem]:
    """Prüfliste des Büros. Standard: nur unbestätigte Kundenkorrekturen, nur Projekte mit Anfrage (G21,
    Modul A). Mit `only_corrections=False` auch unsichere Einordnungen; `require_inquiry=False` zeigt wie
    vor Modul A auch Grundstücke anonymer Besucher (nur zum Testen, keine Büro-Route)."""
    warnings = ["customer_corrections_unconfirmed"] if only_corrections else REVIEW_WARNINGS
    base_query = """
        SELECT s.project_id, s.parcel_idus, s.revision, s.warnings, s.updated_at,
               (SELECT count(*) FROM site_edge e
                WHERE e.site_id = s.id AND e.classification_source = 'customer') AS customer_corrections
        FROM site s
        WHERE s.warnings && CAST(:warnings AS varchar[])
        ORDER BY (s.warnings && ARRAY['customer_corrections_unconfirmed']::varchar[]) DESC,
                 s.updated_at DESC
        LIMIT :limit
        """
    with_inquiry_query = """
        SELECT s.project_id, s.parcel_idus, s.revision, s.warnings, s.updated_at,
               (SELECT count(*) FROM site_edge e
                WHERE e.site_id = s.id AND e.classification_source = 'customer') AS customer_corrections
        FROM site s
        WHERE s.warnings && CAST(:warnings AS varchar[])
          AND EXISTS (SELECT 1 FROM inquiry i WHERE i.project_id = s.project_id)
        ORDER BY (s.warnings && ARRAY['customer_corrections_unconfirmed']::varchar[]) DESC,
                 s.updated_at DESC
        LIMIT :limit
        """
    rows = db.execute(
        text(with_inquiry_query if require_inquiry else base_query),
        {"warnings": warnings, "limit": limit},
    ).all()
    return [
        SiteReviewItem(
            project_id=r.project_id,
            parcel_idus=list(r.parcel_idus),
            revision=r.revision,
            warnings=list(r.warnings),
            customer_corrections=r.customer_corrections,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Ansicht
# ---------------------------------------------------------------------------


def _rings(geometry: BaseGeometry, origin: tuple[float, float]) -> list[LocalRing]:
    polygons: list[Polygon] = []
    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = list(geometry.geoms)
    elif hasattr(geometry, "geoms"):
        polygons = [g for g in geometry.geoms if isinstance(g, Polygon)]
    rings: list[LocalRing] = []
    for polygon in polygons:
        if polygon.is_empty:  # Zuschnitt der Umgebung kann leere Teile liefern
            continue
        for ring in (polygon.exterior, *polygon.interiors):
            if len(ring.coords) >= 4:
                rings.append([list(to_local((float(x), float(y)), origin)) for x, y, *_ in ring.coords])
    return rings


@dataclass(frozen=True)
class SiteFootprint:
    """Für andere Module (Plan 3.2): Umriss in Lambert-93 als WKB, Fläche, Gemeinden, Revision."""

    site_id: uuid.UUID
    wkb: bytes
    area_m2: float
    commune_insees: list[str]
    revision: int


@dataclass(frozen=True)
class EnvelopeEdge:
    """Kante für den Baurahmen (Modul G3): Einordnung, Sicherheit, Geometrie in Lambert-93."""

    seq: int
    ring: int
    kind: str
    kind_auto: str
    classification_source: str
    confidence: float
    length_m: float
    normal_azimuth_deg: float
    street_name: str | None
    geometry: BaseGeometry


@dataclass(frozen=True)
class EnvelopeSite:
    """Eingabe des Baurahmens aus G1 (Plan G3 4.2). Ohne Umgebung und GeoJSON, damit der Abruf schlank
    bleibt; Geometrie in Lambert-93, Ausgabe rechnet G3 in lokale Meter um."""

    site_id: uuid.UUID
    origin: str
    """`parcel` oder `manual_sketch` (Weg E, Plan 3.3): G3 leitet für `manual_sketch` keinen Baurahmen
    ab und ruft G2 dafür nicht auf (D13)."""
    revision: int
    engine_version: str
    updated_at: Any
    polygon: Polygon
    area_m2: float
    local_origin: tuple[float, float]
    edges: list[EnvelopeEdge]
    main_street_seq: int | None
    street_azimuth_deg: float | None
    garden_azimuth_deg: float | None
    warnings: list[str]
    customer_edges_unconfirmed: bool
    terrain_status: str
    terrain_slope_percent: float | None
    terrain_reference_altitude_ngf: float | None
    terrain_method: str | None
    commune_insees: list[str]
    parcel_idus: list[str]
    terrain_samples: tuple[tuple[float, float, float], ...] = ()


def envelope_site(db: Session, project_id: uuid.UUID) -> EnvelopeSite:
    """Grundstück, Kanten und Gelände für Modul G3.

    Module rufen einander nur über `service` auf (Plan 3.2).
    """
    site = db.execute(select(Site).where(Site.project_id == project_id)).scalar_one_or_none()
    if site is None:
        raise Problem(404, "site_not_found")
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    terrain = db.execute(select(Terrain).where(Terrain.site_id == site.id)).scalar_one_or_none()
    communes = list(
        db.execute(
            select(SiteParcel.commune_insee)
            .where(SiteParcel.site_id == site.id)
            .distinct()
            .order_by(SiteParcel.commune_insee)
        ).scalars()
    )
    return EnvelopeSite(
        site_id=site.id,
        origin=site.origin,
        revision=site.revision,
        engine_version=site.engine_version,
        updated_at=site.updated_at,
        polygon=cast(Polygon, to_shape(site.geometry)),
        area_m2=float(site.area_m2),
        local_origin=(site.local_origin_e, site.local_origin_n),
        edges=[
            EnvelopeEdge(
                seq=e.seq,
                ring=e.ring,
                kind=e.kind,
                kind_auto=e.kind_auto,
                classification_source=e.classification_source,
                confidence=e.confidence,
                length_m=e.length_m,
                normal_azimuth_deg=e.normal_azimuth_deg,
                street_name=e.street_name,
                geometry=to_shape(e.geometry),
            )
            for e in edges
        ],
        main_street_seq=site.main_street_seq,
        street_azimuth_deg=site.street_azimuth_deg,
        garden_azimuth_deg=site.garden_azimuth_deg,
        warnings=list(site.warnings),
        customer_edges_unconfirmed=any(e.classification_source == "customer" for e in edges),
        terrain_status=site.terrain_status,
        terrain_slope_percent=terrain.slope_percent if terrain else None,
        terrain_reference_altitude_ngf=terrain.reference_altitude_ngf if terrain else None,
        terrain_method=terrain.method if terrain else None,
        commune_insees=communes,
        parcel_idus=list(site.parcel_idus),
        terrain_samples=(
            tuple((float(s[0]), float(s[1]), float(s[2])) for s in terrain.samples) if terrain else ()
        ),
    )


def site_footprint(db: Session, project_id: uuid.UUID) -> SiteFootprint | None:
    row = db.execute(
        text("SELECT id, ST_AsBinary(geometry) AS wkb, area_m2, revision FROM site WHERE project_id = :p"),
        {"p": project_id},
    ).first()
    if row is None:
        return None
    communes = db.execute(
        select(SiteParcel.commune_insee)
        .where(SiteParcel.site_id == row.id)
        .distinct()
        .order_by(SiteParcel.commune_insee)
    ).scalars()
    return SiteFootprint(row.id, bytes(row.wkb), float(row.area_m2), list(communes), int(row.revision))


def _sketch_site_out(db: Session, site: Site) -> SiteOut:
    """Grundstück ohne Kataster (Weg E und Upload): keine Parzellen und keine Umgebung – aber Kanten, damit
    ein Abstand überhaupt gerechnet werden kann (UP02). Gelände und Risiken erst mit Lage (AN5).

    `outline_geojson` bleibt leer, solange die Geometrie keine echte Lage hat (G26); bei einem Upload
    mit erkanntem Koordinatensystem oder nach dem Einpassen wird sie wie beim Kataster-Grundstück
    berechnet (UP04, AN5)."""
    origin = (site.local_origin_e, site.local_origin_n)
    polygon = to_shape(site.geometry)
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    terrain = db.execute(select(Terrain).where(Terrain.site_id == site.id)).scalar_one_or_none()
    risks = list(
        db.execute(select(SiteRisk).where(SiteRisk.site_id == site.id).order_by(SiteRisk.kind)).scalars()
    )
    outline_geojson: dict[str, Any] = {"type": "Polygon", "coordinates": []}
    if site.georeferenced:
        outline_geojson = json.loads(
            db.execute(
                text("SELECT ST_AsGeoJSON(ST_Transform(geometry, 4326), 7) FROM site WHERE id = :id"),
                {"id": site.id},
            ).scalar_one()
        )
    return SiteOut(
        project_id=site.project_id,
        origin=cast(Any, site.origin),
        georeferenced=site.georeferenced,
        source_info=dict(site.source_info or {}),
        address_label=site.address_label,
        revision=site.revision,
        engine_version=site.engine_version,
        updated_at=site.updated_at,
        area_m2=site.area_m2,
        area_official_m2=None,
        local_origin=LocalOrigin(e=origin[0], n=origin[1]),
        outline_local=_rings(polygon, origin),
        outline_geojson=outline_geojson,
        parcels=[],
        edges=[_edge_out(e, origin) for e in edges],
        main_street_seq=site.main_street_seq,
        street_azimuth_deg=site.street_azimuth_deg,
        garden_azimuth_deg=site.garden_azimuth_deg,
        binding=not any(e.classification_source == "customer" for e in edges),
        warnings=list(site.warnings),
        notices=[f"notice.{site.origin}", *(["notice.risks_public_data"] if risks else [])],
        terrain=_terrain_out(site, terrain),
        risks=_risks_out(site, risks),
        context=ContextOut(parcels=[], buildings=[]),
        placement=_placement(db, site),
    )


def _terrain_out(site: Site, terrain: Terrain | None) -> TerrainOut:
    return TerrainOut(
        status=cast(Any, site.terrain_status),
        method=terrain.method if terrain else None,
        reference_altitude_ngf=terrain.reference_altitude_ngf if terrain else None,
        slope_percent=terrain.slope_percent if terrain else None,
        flat=terrain.slope_percent <= tol.FLAT_SLOPE_MAX_PERCENT if terrain else None,
        samples=len(terrain.samples) if terrain else 0,
    )


def _risks_out(site: Site, risks: list[SiteRisk]) -> RisksOut:
    return RisksOut(
        status=cast(Any, site.risks_status),
        items=[
            RiskOut(kind=r.kind, level=cast(Any, r.level), scope=cast(Any, r.scope), label=r.label)
            for r in risks
        ],
    )


def _edge_out(edge: SiteEdge, origin: tuple[float, float]) -> EdgeOut:
    return EdgeOut(
        seq=edge.seq,
        ring=edge.ring,
        kind=cast(Any, edge.kind),
        kind_auto=cast(Any, edge.kind_auto),
        override_kind=edge.override_kind,
        classification_source=cast(Any, edge.classification_source),
        confidence=edge.confidence,
        length_m=edge.length_m,
        normal_azimuth_deg=edge.normal_azimuth_deg,
        adjacent=list(edge.adjacent),
        street_name=edge.street_name,
        road_share=edge.road_share,
        coords_local=[
            list(to_local((float(x), float(y)), origin)) for x, y, *_ in to_shape(edge.geometry).coords
        ],
    )


def load_site(db: Session, project_id: uuid.UUID) -> SiteOut:
    site = db.execute(select(Site).where(Site.project_id == project_id)).scalar_one_or_none()
    if site is None:
        raise Problem(404, "site_not_found")
    if site.origin in SKETCH_ORIGINS:
        return _sketch_site_out(db, site)
    origin = (site.local_origin_e, site.local_origin_n)
    polygon = to_shape(site.geometry)
    outline_geojson = db.execute(
        text("SELECT ST_AsGeoJSON(ST_Transform(geometry, 4326), 7) FROM site WHERE id = :id"), {"id": site.id}
    ).scalar_one()
    parcels = db.execute(
        select(SiteParcel).where(SiteParcel.site_id == site.id).order_by(SiteParcel.idu)
    ).scalars()
    edges = list(
        db.execute(select(SiteEdge).where(SiteEdge.site_id == site.id).order_by(SiteEdge.seq)).scalars()
    )
    terrain = db.execute(select(Terrain).where(Terrain.site_id == site.id)).scalar_one_or_none()
    risks = list(
        db.execute(select(SiteRisk).where(SiteRisk.site_id == site.id).order_by(SiteRisk.kind)).scalars()
    )
    context_params = {"id": site.id, "radius": tol.CONTEXT_RADIUS_M, "idus": site.parcel_idus}
    context_parcels = db.execute(
        text(
            """
            SELECT ST_AsBinary(ST_Intersection(p.geometry, ST_Expand(s.geometry, :radius))) AS wkb
            FROM ref_parcel p, site s
            WHERE s.id = :id AND p.geometry && ST_Expand(s.geometry, :radius) AND p.idu <> ALL(:idus)
            """
        ),
        context_params,
    ).all()
    context_buildings = db.execute(
        text(
            """
            SELECT ST_AsBinary(ST_Intersection(b.geometry, ST_Expand(s.geometry, :radius))) AS wkb
            FROM ref_building b, site s
            WHERE s.id = :id AND b.geometry && ST_Expand(s.geometry, :radius)
            """
        ),
        context_params,
    ).all()

    notices = ["notice.cadastre_accuracy"]
    if risks:
        notices.append("notice.risks_public_data")
    return SiteOut(
        project_id=site.project_id,
        origin=cast(Any, site.origin),
        georeferenced=site.georeferenced,
        source_info=dict(site.source_info or {}),
        address_label=site.address_label,
        revision=site.revision,
        engine_version=site.engine_version,
        updated_at=site.updated_at,
        area_m2=site.area_m2,
        area_official_m2=site.area_official_m2,
        local_origin=LocalOrigin(e=site.local_origin_e, n=site.local_origin_n),
        outline_local=_rings(polygon, origin),
        outline_geojson=json.loads(outline_geojson),
        parcels=[
            ParcelOut(
                idu=p.idu,
                commune_insee=p.commune_insee,
                prefix=p.prefix,
                section=p.section,
                number=p.number,
                area_official_m2=p.area_official_m2,
                area_geometric_m2=p.area_geometric_m2,
                release=p.release,
                accuracy_class=p.accuracy_class,
            )
            for p in parcels
        ],
        edges=[_edge_out(e, origin) for e in edges],
        main_street_seq=site.main_street_seq,
        street_azimuth_deg=site.street_azimuth_deg,
        garden_azimuth_deg=site.garden_azimuth_deg,
        binding=not any(e.classification_source == "customer" for e in edges),
        warnings=list(site.warnings),
        notices=notices,
        terrain=_terrain_out(site, terrain),
        risks=_risks_out(site, risks),
        context=ContextOut(
            parcels=[
                ring for r in context_parcels for ring in _rings(shapely.from_wkb(bytes(r.wkb)), origin)
            ],
            buildings=[
                ring for r in context_buildings for ring in _rings(shapely.from_wkb(bytes(r.wkb)), origin)
            ],
        ),
    )


def project_summaries(
    db: Session, project_ids: list[uuid.UUID]
) -> dict[uuid.UUID, platform_projects.ProjectSummary]:
    """Bezeichnung, Herkunft und Fläche je Projekt für die Projektliste des Architekten (AN1)."""
    if not project_ids:
        return {}
    rows = db.execute(
        select(Site.project_id, Site.address_label, Site.origin, Site.area_m2).where(
            Site.project_id.in_(project_ids)
        )
    ).all()
    return {
        r.project_id: platform_projects.ProjectSummary(
            address_label=r.address_label, site_origin=r.origin, area_m2=float(r.area_m2)
        )
        for r in rows
    }
