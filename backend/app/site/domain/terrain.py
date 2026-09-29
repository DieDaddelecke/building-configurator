"""Geländehöhen des Grundstücks auswerten (Spez. 5.9.4, Version 1).

Vor der Typwahl gibt es noch keine Grundfläche; die Stichproben liegen deshalb gleichmäßig im
Grundstück. G3 und H2 können später Punkte unter dem Haus nachfragen.
Koordinaten Lambert-93, Höhen in m NGF.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Point, Polygon

from app.site.domain import tolerances as tol

Coord = tuple[float, float]


@dataclass(frozen=True)
class TerrainResult:
    reference_altitude_ngf: float
    """Mittelwert der gültigen Stichproben."""
    slope_percent: float
    """Neigung der Ausgleichsebene."""
    flat: bool
    samples: tuple[tuple[float, float, float], ...]


def sample_points(polygon: Polygon, count: int = tol.TERRAIN_SAMPLES) -> list[Coord]:
    """Bis zu `count` Punkte im Grundstück: Raster über dem umschließenden Rechteck, feiner werdend,
    bis genug Punkte innen liegen. Deterministisch."""
    min_x, min_y, max_x, max_y = polygon.bounds
    for steps in (3, 5, 7, 9):
        fractions = [(2 * i + 1) / (2 * steps) for i in range(steps)]
        inside = [
            (round(min_x + fx * (max_x - min_x), 3), round(min_y + fy * (max_y - min_y), 3))
            for fy in fractions
            for fx in fractions
        ]
        inside = [p for p in inside if polygon.contains(Point(p))]
        if len(inside) >= count:
            return _spread(inside, count)
    point = polygon.representative_point()
    return [(round(point.x, 3), round(point.y, 3))]


def grid_points(
    polygon: Polygon,
    max_points: int = tol.TERRAIN_GRID_MAX_POINTS,
    min_step_m: float = tol.TERRAIN_GRID_MIN_STEP_M,
) -> list[Coord]:
    """Dichtes Raster im Grundstück für das Profil im Schnitt (AN5, PLAN_AN5 3.3): Rasterweite
    `max(2 m, √(Fläche / 200))`, Punkte in Zellmitten, deterministisch. Liegen mehr als `max_points` innen
    (unregelmäßige Form), werden sie gleichmäßig ausgedünnt; zu wenige (sehr schmal): die 9 Stichproben."""
    step = max(min_step_m, math.sqrt(polygon.area / max_points))
    min_x, min_y, max_x, max_y = polygon.bounds
    columns = max(1, math.ceil((max_x - min_x) / step))
    rows = max(1, math.ceil((max_y - min_y) / step))
    offset_x = (max_x - min_x - (columns - 1) * step) / 2
    offset_y = (max_y - min_y - (rows - 1) * step) / 2
    inside = [
        (round(min_x + offset_x + i * step, 3), round(min_y + offset_y + j * step, 3))
        for j in range(rows)
        for i in range(columns)
    ]
    inside = [p for p in inside if polygon.contains(Point(p))]
    if len(inside) < tol.TERRAIN_SAMPLES:
        return sample_points(polygon)
    return _spread(inside, max_points)


def _spread(points: list[Coord], count: int) -> list[Coord]:
    if len(points) <= count:
        return points
    step = len(points) / count
    return [points[int(i * step)] for i in range(count)]


def evaluate(points: Sequence[Coord], altitudes: Sequence[float | None]) -> TerrainResult | None:
    """Ausgleichsebene `z = a·x + b·y + c`. `None`, wenn weniger als drei gültige Höhen vorliegen."""
    valid = [(p[0], p[1], z) for p, z in zip(points, altitudes, strict=True) if z is not None]
    if len(valid) < 3:
        return None
    data = np.array(valid, dtype=float)
    mean = float(data[:, 2].mean())
    centred = data[:, :2] - data[:, :2].mean(axis=0)
    design = np.column_stack([centred, np.ones(len(valid))])
    coefficients, *_ = np.linalg.lstsq(design, data[:, 2], rcond=None)
    slope = float(np.hypot(coefficients[0], coefficients[1]) * 100.0)
    return TerrainResult(
        reference_altitude_ngf=round(mean, 2),
        slope_percent=round(slope, 2),
        flat=slope <= tol.FLAT_SLOPE_MAX_PERCENT,
        samples=tuple((round(x, 3), round(y, 3), round(z, 2)) for x, y, z in valid),
    )
