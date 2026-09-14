"""Grundstück aus Parzellen bilden (Spez. 5.1.3).

Alle Geometrien in Lambert-93 (EPSG:2154), Flächen in m².
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from app.site.domain import tolerances as tol


class SiteNotContiguous(ValueError):
    """Die gewählten Parzellen bilden kein zusammenhängendes Polygon (Code `site_not_contiguous`)."""


@dataclass(frozen=True)
class ParcelInput:
    idu: str
    geometry: BaseGeometry
    area_official_m2: int | None


@dataclass(frozen=True)
class Outline:
    polygon: Polygon
    """Vereinigung, vereinfacht, äußerer Ring gegen den Uhrzeigersinn (Inneres links der Laufrichtung)."""
    area_m2: float
    area_official_m2: int | None
    area_mismatch: bool
    local_origin: tuple[float, float]
    """Südwestecke des umschließenden Rechtecks, auf ganze Meter abgerundet (Spez. 4.2 `local_origin`)."""


def merge_parcels(parcels: Sequence[ParcelInput]) -> Outline:
    """Vereinigt die Parzellen zu einem Grundstück. Löcher bleiben erhalten.

    Mehrere Parzellen: Spalten bis `2 × SLIVER_CLOSE_M` werden geschlossen, damit Rundungsfehler
    der Katastergeometrie keine Scheinlücken erzeugen. Ergebnis MUSS zusammenhängend sein.
    """
    if not parcels:
        raise ValueError("mindestens eine Parzelle")
    merged = shapely.unary_union([p.geometry for p in parcels])
    if len(parcels) > 1:
        merged = merged.buffer(tol.SLIVER_CLOSE_M, join_style="mitre").buffer(
            -tol.SLIVER_CLOSE_M, join_style="mitre"
        )
    merged = shapely.make_valid(merged)
    polygon = _single_polygon(merged)
    simplified = polygon.simplify(tol.SIMPLIFY_TOLERANCE_M, preserve_topology=True)
    polygon = orient(_single_polygon(simplified), sign=1.0)

    area = float(polygon.area)
    official_values = [p.area_official_m2 for p in parcels]
    official = sum(v for v in official_values if v) if all(official_values) else None
    mismatch = official is not None and abs(area - official) > tol.AREA_MISMATCH_RATIO * official
    min_x, min_y, _, _ = polygon.bounds
    return Outline(
        polygon=polygon,
        area_m2=area,
        area_official_m2=official,
        area_mismatch=mismatch,
        local_origin=(float(math.floor(min_x)), float(math.floor(min_y))),
    )


def _single_polygon(geometry: BaseGeometry) -> Polygon:
    if isinstance(geometry, Polygon) and not geometry.is_empty:
        return geometry
    if isinstance(geometry, MultiPolygon):
        parts = [g for g in geometry.geoms if g.area > 0]
        if len(parts) == 1:
            return cast(Polygon, parts[0])
        raise SiteNotContiguous(f"{len(parts)} Teilflächen")
    if hasattr(geometry, "geoms"):
        polygons = [g for g in geometry.geoms if isinstance(g, Polygon) and g.area > 0]
        if len(polygons) == 1:
            return polygons[0]
    raise SiteNotContiguous(geometry.geom_type)


def to_local(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    """Lambert-93 → lokale Meter (Ost, Nord) relativ zu `origin`, auf Millimeter gerundet."""
    return (
        round(point[0] - origin[0], tol.STORAGE_DECIMALS),
        round(point[1] - origin[1], tol.STORAGE_DECIMALS),
    )
