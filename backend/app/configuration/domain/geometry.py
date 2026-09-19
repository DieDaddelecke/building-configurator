"""Geometrie der Lage (Plan H2 3.3): Drehen, Verschieben, Überstreichen und Sperrflächen.

Alles in lokalen Metern (Ost, Nord). Ein Haus steht mit Ursprung `p` und Drehung `θ`, wenn jeder Modellpunkt
`(x, y)` auf `(p_e + x·cosθ + y·sinθ, p_n − x·sinθ + y·cosθ)` liegt (Spez. 5.3.4). Die Menge aller Ursprünge,
für die ein Haus eine Kante berührt, ist die Kante, mit dem am Ursprung gespiegelten Haus überstrichen; das
ergibt die Sperrflächen ohne Rastersuche.
"""

from collections.abc import Iterable

import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from app.configuration.domain import tolerances as tol

Point = tuple[float, float]


def place(geometry: BaseGeometry, origin: Point, rotation_deg: float) -> BaseGeometry:
    """Modellgeometrie in die Lage bringen: erst im Uhrzeigersinn drehen, dann verschieben."""
    return affinity.translate(turn(geometry, rotation_deg), origin[0], origin[1])


def turn(geometry: BaseGeometry, rotation_deg: float) -> BaseGeometry:
    """Nur drehen (im Uhrzeigersinn um den Modellursprung); `shapely` dreht gegen den Uhrzeigersinn."""
    return affinity.rotate(geometry, -rotation_deg, origin=(0.0, 0.0))


def mirror(geometry: BaseGeometry) -> BaseGeometry:
    """Am Ursprung gespiegelt (Punktspiegelung), Grundlage der Sperrflächen."""
    return affinity.scale(geometry, xfact=-1.0, yfact=-1.0, origin=(0.0, 0.0))


def polygons(geometry: BaseGeometry | None) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon) or hasattr(geometry, "geoms"):
        found: list[Polygon] = []
        for part in geometry.geoms:
            found.extend(polygons(part))
        return found
    return []


def segments(geometry: BaseGeometry) -> list[tuple[Point, Point]]:
    """Alle Strecken einer Linie oder des Randes einer Fläche."""
    result: list[tuple[Point, Point]] = []
    lines: list[LineString] = []
    boundary = geometry.boundary if geometry.geom_type in ("Polygon", "MultiPolygon") else geometry
    if isinstance(boundary, LineString):
        lines = [boundary]
    elif hasattr(boundary, "geoms"):
        lines = [g for g in boundary.geoms if isinstance(g, LineString)]
    for line in lines:
        coords = [(float(x), float(y)) for x, y, *_ in line.coords]
        result.extend(
            (coords[i], coords[i + 1]) for i in range(len(coords) - 1) if coords[i] != coords[i + 1]
        )
    return result


def sweep(polygon: Polygon, start: Point, end: Point) -> BaseGeometry:
    """Fläche, die `polygon` überstreicht, wenn es von `start` nach `end` verschoben wird.

    Die beiden Endlagen und ein Parallelogramm je Umrisskante ergeben die Fläche; das Innere zwischen
    den Endlagen ist dabei mit abgedeckt.
    """
    pieces: list[BaseGeometry] = [
        affinity.translate(polygon, start[0], start[1]),
        affinity.translate(polygon, end[0], end[1]),
    ]
    ring = [(float(x), float(y)) for x, y, *_ in polygon.exterior.coords]
    for i in range(len(ring) - 1):
        p, q = ring[i], ring[i + 1]
        quad = Polygon(
            [
                (p[0] + start[0], p[1] + start[1]),
                (q[0] + start[0], q[1] + start[1]),
                (q[0] + end[0], q[1] + end[1]),
                (p[0] + end[0], p[1] + end[1]),
            ]
        )
        if quad.is_valid and quad.area > 1e-12:
            pieces.append(quad)
    return shapely.union_all(pieces)


def sweep_along(geometry: BaseGeometry, moving: Polygon) -> BaseGeometry:
    """`moving` entlang jeder Strecke der Linie (oder des Randes) überstrichen: `geometry ⊕ moving`, soweit
    es den Rand betrifft."""
    pieces = [sweep(moving, a, b) for a, b in segments(geometry)]
    return shapely.union_all(pieces) if pieces else Polygon()


def erode(region: BaseGeometry, footprint: Polygon) -> BaseGeometry:
    """Alle Ursprünge, bei denen `footprint` (am Ursprung gedreht) ganz in `region` liegt.

    Der Bezugspunkt muss in `region` liegen, und der Umriss darf keine Kante von `region` schneiden.
    """
    reference = _reference(footprint)
    base = affinity.translate(region, -reference[0], -reference[1])
    return base.difference(sweep_along(region, mirror(footprint)))


def touching(region: BaseGeometry, footprint: Polygon) -> BaseGeometry:
    """Alle Ursprünge, bei denen `footprint` `region` berührt oder überdeckt (Sperrfläche)."""
    reference = _reference(footprint)
    base = affinity.translate(region, -reference[0], -reference[1])
    return shapely.union_all([base, sweep_along(region, mirror(footprint))])


def keep_distance(edge: BaseGeometry, footprint: Polygon, distance_m: float) -> BaseGeometry:
    """Ursprünge, bei denen `footprint` näher als `distance_m` an `edge` liegt (Sperrfläche).

    `buffer(edge, d) ⊕ −F = buffer(edge ⊕ −F, d)`: Runden und Summieren vertauschen.
    """
    swept = sweep_along(edge, mirror(footprint))
    return swept.buffer(distance_m, quad_segs=16) if distance_m > 0 else swept


def _reference(footprint: Polygon) -> Point:
    x, y = footprint.exterior.coords[0][:2]
    return float(x), float(y)


def clean(geometry: BaseGeometry) -> BaseGeometry:
    """Rechenstaub entfernen: nur Flächen ab 1 cm²."""
    kept = [p for p in polygons(shapely.make_valid(geometry)) if p.area >= tol.MIN_SURFACE_AREA_M2]
    return shapely.union_all(kept) if kept else Polygon()


def distance(a: BaseGeometry, b: BaseGeometry) -> float:
    return float(a.distance(b))


def angle_between_axes(a_deg: float, b_deg: float) -> float:
    """Kleinster Winkel zwischen zwei ungerichteten Achsen, 0–90°."""
    diff = abs(a_deg - b_deg) % 180.0
    return min(diff, 180.0 - diff)


def union(geometries: Iterable[BaseGeometry]) -> BaseGeometry:
    items = [g for g in geometries if g is not None and not g.is_empty]
    return shapely.union_all(items) if items else Polygon()


def rounded(value: float) -> float:
    return round(value, tol.STORAGE_DECIMALS)


def normalize_deg(value: float) -> float:
    return round(value % 360.0, 2)


__all__ = [
    "angle_between_axes",
    "clean",
    "distance",
    "erode",
    "keep_distance",
    "mirror",
    "normalize_deg",
    "place",
    "polygons",
    "rounded",
    "segments",
    "sweep",
    "sweep_along",
    "touching",
    "turn",
    "union",
]
