"""Geländeprofil entlang eines Schnitts (AN5, docs/PLAN_AN5_AUSGABE.md 3.3).

Aus den Stichproben (x, y in Lambert-93, z in m NGF) entsteht ein Dreiecksnetz; im Netz wird linear im
Dreieck interpoliert, eine Ebene wird also genau wiedergegeben. Die Stichproben liegen in Zellmitten, das
Netz endet deshalb bis zu einer halben Rasterweite vor der Grenze. Dort wird vom letzten Punkt im Netz mit
der Neigung der Ausgleichsebene längs des Schnitts weitergeführt – für eine Ebene wieder genau, sonst eine
kurze, ruhige Fortsetzung statt einer Lücke an der Grenze, wo die Abstände liegen.
"""

from collections.abc import Sequence

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Point
from shapely.strtree import STRtree

Sample = tuple[float, float, float]
Interval = tuple[float, float]

STEP_M = 0.5
KEY_DECIMALS = 3


class _Tin:
    def __init__(self, samples: Sequence[Sample]) -> None:
        self.z = {(round(x, KEY_DECIMALS), round(y, KEY_DECIMALS)): z for x, y, z in samples}
        triangles = shapely.delaunay_triangles(MultiPoint([(x, y) for x, y, _ in samples]))
        self.triangles = [t for t in getattr(triangles, "geoms", []) if t.area > 1e-9]
        self.tree = STRtree(self.triangles)

    def at(self, x: float, y: float) -> float | None:
        point = Point(x, y)
        for index in self.tree.query(point, predicate="intersects"):
            triangle = self.triangles[int(index)]
            corners = list(triangle.exterior.coords)[:3]
            values = [self.z.get((round(cx, KEY_DECIMALS), round(cy, KEY_DECIMALS))) for cx, cy in corners]
            if any(v is None for v in values):
                continue
            (x1, y1), (x2, y2), (x3, y3) = corners
            det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(det) < 1e-12:
                continue
            w1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
            w2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
            w3 = 1.0 - w1 - w2
            return float(w1 * values[0] + w2 * values[1] + w3 * values[2])
        return None


def _plane(samples: Sequence[Sample]) -> tuple[float, float, float]:
    """Ausgleichsebene `z = a·x + b·y + c` (wie `site/domain/terrain.evaluate`)."""
    data = np.array(samples, dtype=float)
    design = np.column_stack([data[:, 0], data[:, 1], np.ones(len(data))])
    (a, b, c), *_ = np.linalg.lstsq(design, data[:, 2], rcond=None)
    return float(a), float(b), float(c)


def _positions(intervals: Sequence[Interval], step: float) -> list[float]:
    values: set[float] = set()
    for start, end in intervals:
        values.update((round(start, 3), round(end, 3)))
        s = (int(start / step) + 1) * step
        while s < end:
            values.add(round(s, 3))
            s += step
    return sorted(values)


def profile(
    samples: Sequence[Sample],
    start: tuple[float, float],
    end: tuple[float, float],
    intervals: Sequence[Interval],
    reference_ngf: float,
    step: float = STEP_M,
) -> list[tuple[float, float]]:
    """`[(s, dz)]` über den Abschnitten des Grundstücks, `dz` = Höhe − Bezugshöhe; ohne drei Stichproben
    leer."""
    if len(samples) < 3 or not intervals:
        return []
    length = float(np.hypot(end[0] - start[0], end[1] - start[1]))
    if length <= 0:
        return []
    ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    a, b, c = _plane(samples)
    gradient = a * ux + b * uy
    positions = _positions(intervals, step)
    tin = _Tin(samples)
    covered: dict[float, float] = {}
    for s in positions:
        z = tin.at(start[0] + ux * s, start[1] + uy * s)
        if z is not None:
            covered[s] = z
    result: list[tuple[float, float]] = []
    anchors = sorted(covered)
    for s in positions:
        if s in covered:
            z = covered[s]
        elif anchors:
            nearest = min(anchors, key=lambda known: abs(known - s))
            z = covered[nearest] + gradient * (s - nearest)
        else:
            z = a * (start[0] + ux * s) + b * (start[1] + uy * s) + c
        result.append((round(s, 3), round(z - reference_ngf, 3)))
    return result
