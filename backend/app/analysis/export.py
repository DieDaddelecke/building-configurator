"""Dateien der Analyse (AN5, docs/PLAN_AN5_AUSGABE.md 3.4, 3.5): DXF lokal und in Lambert-93, GeoJSON.

Beide entstehen im Request aus der gerechneten Analyse und werden nicht abgelegt (E-AN5-10). Ohne Lage gibt
es nur das lokale DXF (E-AN5-6). Die Texte in der DXF sind französisch wie die Ebenen und die Dateien von V.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis import service
from app.analysis.report import ascii_text, file_stem
from app.plan import dxf
from app.plan.geometry import Area, Constraint, Cut, Edge, Plan, Point, Ring, Stage, rings
from app.platform.db import utcnow
from app.platform.i18n import translate
from app.platform.models import Project
from app.platform.problems import Problem
from app.site import service as site_service
from app.site.domain import local as local_coords
from app.site.schemas import SiteOut

Variant = Literal["local", "L93"]
EFFECTS = ("no_build", "restricts")
"""Vorgaben, die Fläche wegnehmen; `info` steht nur im Bericht."""
GEOJSON_DECIMALS = 7


@dataclass(frozen=True)
class Source:
    """Was die Dateien brauchen: die gerechnete Analyse, das Grundstück und eine Bezeichnung."""

    computed: service.Computed
    site: SiteOut
    project: Project
    label: str
    """Name des Projekts, sonst Adresse, sonst Parzellen."""


def load(db: Session, project_id: uuid.UUID) -> Source:
    project = db.get(Project, project_id)
    if project is None:
        raise Problem(404, "not_found")
    site = site_service.load_site(db, project_id)
    label = service.project_label(project, site)
    return Source(
        computed=service.compute(db, project_id),
        site=site,
        project=project,
        label=label,
    )


# ---------------------------------------------------------------------------
# Lageplan
# ---------------------------------------------------------------------------


def _ring(raw: list[list[float]]) -> Ring:
    return [(float(p[0]), float(p[1])) for p in raw]


def _point(coordinate: tuple[float, float], origin: tuple[float, float]) -> Point:
    x, y = local_coords.point(coordinate, origin)
    return (x, y)


def _areas(geometry: BaseGeometry | None, origin: tuple[float, float]) -> list[Area]:
    def local(coords: Any) -> Ring:
        return [_point((float(x), float(y)), origin) for x, y, *_ in coords]

    return [
        Area(exterior=local(p.exterior.coords), holes=[local(h.coords) for h in p.interiors])
        for p in local_coords.polygons(geometry)
    ]


def plan_for(computed: service.Computed, georeferenced: bool) -> Plan:
    """Lageplan mit Baurahmen, Bauband, Vorgaben, Schnitten und Gabarit in lokalen Metern (3.4)."""
    data, envelope, result = computed.data, computed.envelope, computed.result
    origin = data.site.local_origin
    contours = envelope.contours if envelope is not None else {}

    def contour(reading: str) -> list[Ring]:
        return rings(local_coords.rings(contours[reading].geometry, origin)) if reading in contours else []

    terrain = data.site.terrain
    return Plan(
        origin=origin,
        georeferenced=georeferenced,
        parcel=rings(local_coords.rings(data.site.polygon, origin)),
        edges=[
            Edge(seq=edge.seq, kind=edge.kind, coords=_ring(line))
            for edge in data.site.edges
            for line in local_coords.lines(edge.geometry, origin)
        ],
        lenient=contour("lenient"),
        strict=contour("strict"),
        bands=[
            ring
            for band in (envelope.bands if envelope is not None else [])
            for ring in rings(local_coords.rings(band.polygon, origin))
        ],
        constraints=[
            Constraint(
                effect=item.effect,
                label=item.label,
                rings=rings(local_coords.rings(item.geometry, origin)),
                lines=[_ring(line) for line in local_coords.lines(item.geometry, origin)],
            )
            for item in (envelope.constraints if envelope is not None else [])
            if item.effect in EFFECTS
        ],
        cuts=[
            Cut(key=s.key, start=_point(s.start, origin), end=_point(s.end, origin)) for s in result.sections
        ],
        stages=[
            Stage(
                reading=reading,
                from_m=level.from_m,
                to_m=level.to_m,
                roof=level.roof,
                areas=_areas(contour.geometry, origin),
            )
            for level in (result.gabarit.levels if result.gabarit is not None else [])
            for reading, contour in level.contours.items()
        ],
        reference_ngf=terrain.reference_altitude_ngf if terrain.status == "ok" else None,
    )


# ---------------------------------------------------------------------------
# DXF
# ---------------------------------------------------------------------------


def _notes(source: Source, plan: Plan, variant: Variant) -> list[str]:
    """Textzeilen der Datei: Projekt, Stand, Koordinaten, Höhenbezug, Hinweis (3.4, E-A5)."""
    out = source.computed.out
    e, n = f"{plan.origin[0]:.3f}", f"{plan.origin[1]:.3f}"
    if variant == "L93":
        coordinates = translate("dossier.dxf.L93", "fr")
    elif plan.georeferenced:
        coordinates = translate("dossier.dxf.local", "fr", e=e, n=n)
    else:
        coordinates = translate("export.dxf.local_free", "fr")
    reference = plan.reference_ngf
    if reference is None:
        heights = translate("export.dxf.z_unknown", "fr")
    elif variant == "L93":
        heights = translate("export.dxf.z_ngf", "fr", ref=f"{reference:.2f}")
    else:
        heights = translate("export.dxf.z_relative", "fr", ref=f"{reference:.2f}")
    lines = [
        f"{ascii_text(source.label) or 'Emprise Analyse'} - {utcnow():%Y-%m-%d}",
        translate(
            "export.dxf.state",
            "fr",
            engine=out.engine_version,
            hash=out.input_hash.removeprefix("sha256:")[:12],
        ),
        coordinates,
        heights,
    ]
    if plan.georeferenced and source.site.origin != "parcel":
        # Genauigkeit der Lage nennen (3.2): von Hand eingepasst oder aus der Datei
        method = (source.site.source_info.get("position") or {}).get("method")
        lines.append(translate(f"export.dxf.position_{'map' if method == 'map' else 'file'}", "fr"))
    return [*lines, translate("export.disclaimer", "fr")]


def dxf_file(source: Source, variant: Variant) -> tuple[bytes, str]:
    """DXF und Dateiname `<Name>_<Datum>_<local|L93>.dxf`; Lambert-93 nur mit Lage."""
    if variant == "L93" and not source.site.georeferenced:
        raise Problem(409, "export_not_georeferenced")
    plan = plan_for(source.computed, source.site.georeferenced)
    data = dxf.render(plan, variant, _notes(source, plan, variant), all_layers=False)
    return data, f"{file_stem(source.label)}_{utcnow():%Y-%m-%d}_{variant}.dxf"


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def oriented(geometry: BaseGeometry) -> BaseGeometry:
    """Außenring gegen, Löcher im Uhrzeigersinn (RFC 7946 3.1.6). Die Umrechnung nach WGS84 erhält den
    Drehsinn, weil beide Systeme Ost vor Nord zählen."""
    if isinstance(geometry, Polygon):
        return orient(geometry, 1.0)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([orient(p, 1.0) for p in geometry.geoms])
    if isinstance(geometry, GeometryCollection):
        return GeometryCollection([oriented(g) for g in geometry.geoms])
    return geometry


def features(computed: service.Computed) -> list[tuple[BaseGeometry, dict[str, Any]]]:
    """Merkmale in Lambert-93 mit Eigenschaften; `layer` wie die DXF-Ebenen (3.5)."""
    data, envelope, result = computed.data, computed.envelope, computed.result
    items: list[tuple[BaseGeometry, dict[str, Any]]] = [
        (data.site.polygon, {"layer": "PARCELLE", "area_m2": round(data.site.area_m2, 2)})
    ]
    derived = {edge.seq: edge for edge in envelope.edges} if envelope is not None else {}
    for edge in data.site.edges:
        result_edge = derived.get(edge.seq)
        items.append(
            (
                edge.geometry,
                {
                    "layer": dxf.EDGE_LAYERS.get(edge.kind, "LIMITE_AUTRE"),
                    "seq": edge.seq,
                    "kind": edge.kind,
                    "lenient_m": result_edge.lenient_m if result_edge else None,
                    "strict_m": result_edge.strict_m if result_edge else None,
                },
            )
        )
    if envelope is not None:
        for reading, contour in envelope.contours.items():
            layer = "ZONE_CONSTRUCTIBLE_LARGE" if reading == "lenient" else "ZONE_CONSTRUCTIBLE_STRICTE"
            props = {
                "layer": layer,
                "reading": reading,
                "area_m2": contour.area_m2,
                "complete": contour.complete,
            }
            items.append((contour.geometry, props))
        for band in envelope.bands:
            props = {
                "layer": "BANDE_CONSTRUCTIBLE",
                "edge_seq": band.edge_seq,
                "zone_code": band.zone_code,
                "min_m": band.min_m,
                "max_m": band.max_m,
            }
            items.append((band.polygon, props))
        for item in envelope.constraints:
            if item.effect in EFFECTS:
                layer = dxf.CONSTRAINT_LAYERS[item.effect]
                items.append((item.geometry, {"layer": layer, "effect": item.effect, "label": item.label}))
    terrain = data.site.terrain
    reference = terrain.reference_altitude_ngf if terrain.status == "ok" else None
    for level in result.gabarit.levels if result.gabarit is not None else []:
        for reading, level_contour in level.contours.items():
            props = {
                "layer": dxf.stage_layer(reading, "COURBES", level.roof),
                "reading": reading,
                "from_m": level.from_m,
                "to_m": level.to_m,
                "roof": level.roof,
                "z_ngf_top": round(reference + level.to_m, 2) if reference is not None else None,
            }
            items.append((level_contour.geometry, props))
    for section in result.sections:
        items.append((LineString([section.start, section.end]), {"layer": "COUPE", "key": section.key}))
    return [(geometry, props) for geometry, props in items if not geometry.is_empty]


def geojson(db: Session, source: Source) -> dict[str, Any]:
    """FeatureCollection in WGS84, in **einer** PostGIS-Abfrage umgerechnet (3.5); nur mit Lage."""
    if not source.site.georeferenced:
        raise Problem(409, "export_not_georeferenced")
    items = features(source.computed)
    collection = GeometryCollection([oriented(geometry) for geometry, _ in items])
    raw = db.execute(
        text("SELECT ST_AsGeoJSON(ST_Transform(ST_GeomFromWKB(:wkb, 2154), 4326), :digits)"),
        {"wkb": collection.wkb, "digits": GEOJSON_DECIMALS},
    ).scalar_one()
    geometries = json.loads(raw)["geometries"]
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": geometry, "properties": props}
            for geometry, (_, props) in zip(geometries, items, strict=True)
        ],
    }
