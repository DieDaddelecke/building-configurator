"""Lage eines Grundstücks ohne Kataster setzen (AN5, docs/PLAN_AN5_AUSGABE.md 3.2).

Starre Transformation: Das Grundstück wird um seinen Schwerpunkt gedreht und verschoben, Maße und Fläche
bleiben. Winkel im Uhrzeigersinn, Azimute ab Norden der jeweiligen Achsen. Die Umrechnung zwischen WGS84
und Lambert-93 und die Gitterkonvergenz liefert der Dienst über PostGIS; hier wird nur gerechnet.
"""

import math

from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

Point = tuple[float, float]

LON_RANGE = (-6.0, 10.0)
LAT_RANGE = (41.0, 52.0)
"""Frankreich (Festland und Korsika): Außerhalb ist Lambert-93 nicht definiert."""


def pivot(polygon: Polygon) -> Point:
    """Drehpunkt: Schwerpunkt des Umrisses. Liegt er bei einer L-Form außerhalb, stört das nicht – er ist nur
    der Bezugspunkt, an dem die Karte das Grundstück festhält."""
    centre = polygon.centroid
    return (round(centre.x, 3), round(centre.y, 3))


def turn(geometry: BaseGeometry, centre: Point, target: Point, theta_deg: float) -> BaseGeometry:
    """Um `centre` im Uhrzeigersinn um `theta_deg` drehen und `centre` auf `target` legen."""
    rotated = affinity.rotate(geometry, -theta_deg, origin=centre)  # shapely dreht gegen den Uhrzeigersinn
    return affinity.translate(rotated, target[0] - centre[0], target[1] - centre[1])


def turn_azimuth(azimuth_deg: float | None, theta_deg: float) -> float | None:
    """Ein Azimut dreht mit dem Grundstück."""
    if azimuth_deg is None:
        return None
    return round((azimuth_deg + theta_deg) % 360.0, 2)


def azimuth(start: Point, end: Point) -> float:
    """Richtung von `start` nach `end` im Uhrzeigersinn ab der Nordachse (y), 0–360°."""
    return math.degrees(math.atan2(end[0] - start[0], end[1] - start[1])) % 360.0


def signed(angle_deg: float) -> float:
    """Winkel auf −180° bis 180°."""
    return (angle_deg + 180.0) % 360.0 - 180.0


def rotation(map_rotation_deg: float, delta_deg: float, convergence_deg: float) -> float:
    """Drehung der lokalen Koordinaten ins Gitter von Lambert-93: `θ = map_rotation + Δ + γ`.

    `map_rotation`: wie die Karte die lokalen Achsen zeigt (0 ohne Lage, `−γ_alt` mit Lage); `Δ`: vom
    Architekten eingestellt; `γ`: Gitterazimut der geografischen Nordrichtung am neuen Drehpunkt."""
    return signed(map_rotation_deg + delta_deg + convergence_deg)


def inside_france(lon: float, lat: float) -> bool:
    return LON_RANGE[0] <= lon <= LON_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]
