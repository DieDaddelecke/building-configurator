"""Umrechnung Lambert-93 → lokale Meter (Ost, Nord) für Anzeige und Steckbrief (Spez. 4.2).

Der Ursprung gehört dem Grundstück; Grundstück, Baurahmen, Analyse und Konfiguration rechnen damit."""

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.site.domain import tolerances as tol

Ring = list[list[float]]


def point(coordinate: tuple[float, float], origin: tuple[float, float]) -> list[float]:
    return [
        round(coordinate[0] - origin[0], tol.STORAGE_DECIMALS),
        round(coordinate[1] - origin[1], tol.STORAGE_DECIMALS),
    ]


def rings(geometry: BaseGeometry | None, origin: tuple[float, float]) -> list[Ring]:
    """Alle Ringe (äußere und Löcher) einer Fläche in lokalen Metern."""
    result: list[Ring] = []
    for polygon in polygons(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            if len(ring.coords) >= 4:
                result.append([point((float(x), float(y)), origin) for x, y, *_ in ring.coords])
    return result


def lines(geometry: BaseGeometry | None, origin: tuple[float, float]) -> list[Ring]:
    """Linienhafte Geometrie (Kanten, Baulinien) in lokalen Metern."""
    if geometry is None or geometry.is_empty:
        return []
    parts: list[LineString] = []
    if isinstance(geometry, LineString):
        parts = [geometry]
    elif isinstance(geometry, MultiLineString):
        parts = list(geometry.geoms)
    elif hasattr(geometry, "geoms"):
        parts = [g for g in geometry.geoms if isinstance(g, LineString)]
    return [[point((float(x), float(y)), origin) for x, y, *_ in line.coords] for line in parts]


def points(geometry: BaseGeometry | None, origin: tuple[float, float]) -> list[list[float]]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [point((geometry.x, geometry.y), origin)]
    if hasattr(geometry, "geoms"):
        return [point((g.x, g.y), origin) for g in geometry.geoms if isinstance(g, Point)]
    return []


def polygons(geometry: BaseGeometry | None) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return [g for g in geometry.geoms if not g.is_empty]
    if hasattr(geometry, "geoms"):
        return [g for g in geometry.geoms if isinstance(g, Polygon) and not g.is_empty]
    return []
