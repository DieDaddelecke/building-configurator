"""Schnellstellungen `street_near`, `set_back`, `garden_max` (Plan H2 3.3; Spez. 5.3.5).

Gesucht wird auf der Fläche zulässiger Ursprünge: in ihren Ecken, den Mitten ihrer Kanten und einem groben
Raster im Inneren. Die Zielfunktion entscheidet, bei Gleichstand die straßenzugewandte Drehung.
"""

import math
from collections.abc import Callable
from itertools import pairwise

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.geometry import place, polygons
from app.configuration.domain.house import HouseType
from app.configuration.domain.placement import Placement
from app.configuration.domain.rotations import allowed_rotations
from app.configuration.domain.surface import BoundaryOptions, surface_by_rotation

PRESETS = ("street_near", "set_back", "garden_max")

XY = tuple[float, float]
Score = tuple[float, ...]


def candidates(surface: BaseGeometry) -> list[tuple[float, float]]:
    """Ecken, Kantenmitten und ein grobes Raster der Fläche."""
    points: list[tuple[float, float]] = []
    for polygon in polygons(surface):
        for ring in (polygon.exterior, *polygon.interiors):
            coords = [(float(x), float(y)) for x, y, *_ in ring.coords]
            points.extend(coords[:-1])
            points.extend(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in pairwise(coords))
    if surface.is_empty:
        return points
    min_x, min_y, max_x, max_y = surface.bounds
    step = tol.PRESET_GRID_M
    while ((max_x - min_x) / step + 1) * ((max_y - min_y) / step + 1) > tol.PRESET_CANDIDATES_MAX:
        step *= 1.5
    xs = np.arange(min_x, max_x + step, step)
    ys = np.arange(min_y, max_y + step, step)
    grid_x, grid_y = np.meshgrid(xs, ys)
    flat_x, flat_y = grid_x.ravel(), grid_y.ravel()
    inside = shapely.contains_xy(surface, flat_x, flat_y)
    points.extend((float(x), float(y)) for x, y in zip(flat_x[inside], flat_y[inside], strict=True))
    return points


def street_edge_line(ctx: SiteContext) -> BaseGeometry | None:
    for edge in ctx.edges:
        if edge.seq == ctx.street_seq:
            return edge.geometry
    return None


def compute(
    house: HouseType,
    ctx: SiteContext,
    preset: str,
    boundary_options: BoundaryOptions,
    parts: list[PartContext] | None = None,
) -> Placement | None:
    """Schnellstellung oder `None`, wenn es keine zulässige Lage gibt.

    `parts`: nur diese Teilflächen kommen in Betracht (der Dienst lässt jene aus, in denen der Typ schon aus
    anderem Grund scheitert).
    """
    usable = ctx.parts if parts is None else parts
    rotations: list[float] = []
    for part in usable:
        for rotation in allowed_rotations(house, part, ctx):
            if rotation not in rotations:
                rotations.append(rotation)
    exact = surface_by_rotation(house, usable, rotations, ctx, boundary_options, exact=True)
    tolerant = surface_by_rotation(house, usable, rotations, ctx, boundary_options, exact=False)
    surfaces = {r: (exact[r] if not exact[r].is_empty else tolerant[r]) for r in rotations}
    scorer = _SCORERS[preset]
    best: tuple[Score, Placement] | None = None
    reference = street_edge_line(ctx)
    site_area = ctx.polygon
    for rotation in rotations:
        surface = surfaces[rotation]
        if surface.is_empty:
            continue
        points = candidates(surface)
        if preset == "garden_max" and len(points) > tol.GARDEN_CANDIDATES_MAX:
            points = _thin(points, tol.GARDEN_CANDIDATES_MAX)
        scored = scorer(house, ctx, rotation, points, surface, reference, site_area)
        if scored is None:
            continue
        score, origin = scored
        if best is None or _better(score, best[0]):
            best = (
                score,
                Placement(origin=(round(origin[0], 3), round(origin[1], 3)), rotation_deg=rotation),
            )
    return best[1] if best else None


def _better(score: Score, current: Score) -> bool:
    """Kleiner ist besser; ein Gleichstand innerhalb der Toleranz bleibt bei der früheren Drehung."""
    for new, old in zip(score, current, strict=True):
        if new < old - tol.PRESET_TIE_M:
            return True
        if new > old + tol.PRESET_TIE_M:
            return False
    return False


def _thin(points: list[tuple[float, float]], limit: int) -> list[tuple[float, float]]:
    step = math.ceil(len(points) / limit)
    return points[::step]


def _street_distance(house: HouseType, rotation: float, origin: XY, street: BaseGeometry | None) -> float:
    if street is None:
        return 0.0
    return float(place(house.facade, (origin[0], origin[1]), rotation).distance(street))


def _lateral(house: HouseType, rotation: float, origin: XY, street: BaseGeometry | None) -> float:
    """Abstand der Hausmitte von der Mitte der Straßenkante, entlang der Kante."""
    if not isinstance(street, LineString):
        return 0.0
    centre = place(house.facade, (origin[0], origin[1]), rotation).centroid
    return abs(float(street.project(centre)) - float(street.length) / 2.0)


def _street_near(
    house: HouseType,
    ctx: SiteContext,
    rotation: float,
    points: list[tuple[float, float]],
    surface: BaseGeometry,
    street: BaseGeometry | None,
    site: Polygon,
) -> tuple[Score, XY] | None:
    best: tuple[Score, XY] | None = None
    for origin in points:
        score = (
            round(_street_distance(house, rotation, origin, street), 2),
            round(_lateral(house, rotation, origin, street), 2),
        )
        if best is None or score < best[0]:
            best = (score, origin)
    return best


def _set_back(
    house: HouseType,
    ctx: SiteContext,
    rotation: float,
    points: list[tuple[float, float]],
    surface: BaseGeometry,
    street: BaseGeometry | None,
    site: Polygon,
) -> tuple[Score, XY] | None:
    """Mitte der Tiefe: Abstand zur Straße möglichst genau zwischen kleinstem und größtem Wert."""
    depths = [(_street_distance(house, rotation, p, street), p) for p in points]
    if not depths:
        return None
    lowest = min(d for d, _ in depths)
    highest = max(d for d, _ in depths)
    target = (lowest + highest) / 2.0
    best: tuple[Score, XY] | None = None
    for depth, origin in depths:
        score = (round(abs(depth - target), 2), round(_lateral(house, rotation, origin, street), 2))
        if best is None or score < best[0]:
            best = (score, origin)
    return best


def _garden_max(
    house: HouseType,
    ctx: SiteContext,
    rotation: float,
    points: list[tuple[float, float]],
    surface: BaseGeometry,
    street: BaseGeometry | None,
    site: Polygon,
) -> tuple[Score, XY] | None:
    """Größte zusammenhängende unbebaute Fläche (Spez. 5.3.5); Score negativ, weil kleiner besser ist."""
    best: tuple[Score, XY] | None = None
    for origin in points:
        placed = place(house.projection, (origin[0], origin[1]), rotation)
        rest = polygons(site.difference(placed))
        largest = max((p.area for p in rest), default=0.0)
        score = (-round(largest, 1), round(_street_distance(house, rotation, origin, street), 2), origin[0])
        if best is None or _better(score, best[0]):
            best = (score, origin)
    return best


_SCORERS: dict[str, Callable[..., tuple[Score, XY] | None]] = {
    "street_near": _street_near,
    "set_back": _set_back,
    "garden_max": _garden_max,
}


def all_presets(
    house: HouseType,
    ctx: SiteContext,
    boundary_options: BoundaryOptions,
    parts: list[PartContext] | None = None,
) -> dict[str, Placement | None]:
    return {name: compute(house, ctx, name, boundary_options, parts) for name in PRESETS}


__all__ = ["PRESETS", "all_presets", "candidates", "compute"]
