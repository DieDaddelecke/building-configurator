"""Grundstück aus Katasterparzellen bilden und die Lesemodelle des Moduls G1 (Plan 3.3): Anzeige, Umriss
für G2, Eingaben für G3. Andere Module rufen nur die öffentlichen Funktionen auf (Plan 3.2).

Geometrie wird in PostGIS gesucht und transformiert, in Shapely (Lambert-93) berechnet. Suche: `search.py`;
ohne Kataster (Zeichnen, Upload, Scan): `manual.py`; Lage: `position.py`; Kanten und Prüfliste:
`corrections.py`; gemeinsame Speicherhilfen: `store.py`.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any, cast

import shapely
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.platform import projects as platform_projects
from app.platform.models import Project
from app.platform.problems import Problem
from app.site.domain import ENGINE_VERSION, position
from app.site.domain import tolerances as tol
from app.site.domain.edges import (
    NeighbourCoverage,
    NeighbourParcel,
    RoadLine,
    classify,
    edge_facts,
    split_edges,
)
from app.site.domain.local import rings as local_rings
from app.site.domain.outline import ParcelInput, SiteNotContiguous, merge_parcels, to_local
from app.site.models import L93, Site, SiteEdge, SiteParcel, SiteRisk, Terrain
from app.site.schemas import (
    ContextOut,
    EdgeOut,
    LocalOrigin,
    ParcelOut,
    RiskOut,
    RisksOut,
    SiteOut,
    SitePlacementOut,
    TerrainOut,
)
from app.site.store import (
    add_edges,
    apply_classification,
    db_now,
    enqueue_enrichment,
    hash_outline,
    l93_and_convergence,
    renewed_site,
    wgs84_of,
)

FEATURE_FLAG = "site_selection"
SOURCE = "etalab_cadastre"
ACCURACY_CLASS = "cadastre_vector"
SKETCH_ORIGINS = ("manual_sketch", "upload")
"""Herkünfte ohne Kataster: keine Nachbarn, kein Gelände, keine Risiken, keine Zonensuche."""


# ---------------------------------------------------------------------------
# Grundstück bilden
# ---------------------------------------------------------------------------


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
    outline_hash = hash_outline(outline.polygon)
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

    site = renewed_site(db, site, project_id, actor)
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
    site.updated_at = db_now(db)
    apply_classification(site, classification, warnings)
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
    add_edges(db, site, classification, actor)
    enqueue_enrichment(db, site, project_id, actor)
    db.commit()
    return load_site(db, project_id)


# ---------------------------------------------------------------------------
# Ansicht
# ---------------------------------------------------------------------------


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


def _placement(db: Session, site: Site) -> SitePlacementOut:
    """Drehpunkt und Darstellung auf der Karte: ohne Lage Blattoben = Norden, mit Lage folgen die lokalen
    Achsen Gitternord, die Karte dreht sie um −γ."""
    centre = position.pivot(cast(Polygon, to_shape(site.geometry)))
    local = list(to_local(centre, (site.local_origin_e, site.local_origin_n)))
    if not site.georeferenced:
        return SitePlacementOut(pivot_local=local, map_rotation_deg=0.0)
    lon, lat = wgs84_of(db, centre)
    _, gamma = l93_and_convergence(db, lon, lat)
    return SitePlacementOut(
        pivot_local=local, pivot_wgs84=[round(lon, 7), round(lat, 7)], map_rotation_deg=round(-gamma, 4)
    )


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
        outline_local=local_rings(polygon, origin),
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
        outline_local=local_rings(polygon, origin),
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
                ring for r in context_parcels for ring in local_rings(shapely.from_wkb(bytes(r.wkb)), origin)
            ],
            buildings=[
                ring
                for r in context_buildings
                for ring in local_rings(shapely.from_wkb(bytes(r.wkb)), origin)
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
