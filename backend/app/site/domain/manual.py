"""Grundstück aus freier Zeichnung und Bemaßung bilden, ohne Kataster (Weg E, Plan 3.3).

Jede Kante trägt Länge und Azimut ihrer Laufrichtung (0° = Norden im Uhrzeigersinn, wie im übrigen Modul).
Bei `n` Kanten legen Länge und Azimut von `n − 1` Kanten das Polygon eindeutig fest; ein vollständig
bemaßtes Polygon wäre überbestimmt (zwei Schließungsbedingungen: Summe der Verschiebung in Ost und Nord
muss null ergeben). Die letzte Kante schließt das Polygon deshalb automatisch (Plan 3.3, Prüfprotokoll
10.4 Nr. 34).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from app.site.domain import tolerances as tol


class ManualPolygonInvalid(ValueError):
    """Das bemaßte Polygon ist nicht gültig (Code `manual_polygon_invalid`)."""


@dataclass(frozen=True)
class ManualEdgeInput:
    length_m: float
    angle_deg: float
    """Azimut der Laufrichtung dieser Kante (nicht der Normalen), 0° = Norden im Uhrzeigersinn."""


@dataclass(frozen=True)
class ManualOutline:
    polygon: Polygon
    """Äußerer Ring gegen den Uhrzeigersinn, wie bei Grundstücken aus Parzellen (`outline.merge_parcels`)."""
    area_m2: float
    local_origin: tuple[float, float]


def build_manual_polygon(edges: Sequence[ManualEdgeInput]) -> ManualOutline:
    """`n − 1` bemaßte Kanten ergeben das Polygon; die letzte Kante schließt es automatisch."""
    if not tol.MANUAL_MIN_EDGES - 1 <= len(edges) <= tol.MANUAL_MAX_EDGES - 1:
        raise ManualPolygonInvalid(
            f"{tol.MANUAL_MIN_EDGES - 1} bis {tol.MANUAL_MAX_EDGES - 1} bemaßte Kanten erwartet"
        )
    for edge in edges:
        if not tol.MANUAL_MIN_EDGE_M <= edge.length_m <= tol.MANUAL_MAX_EDGE_M:
            raise ManualPolygonInvalid("Kantenlänge außerhalb des plausiblen Bereichs")

    # Auf Mikrometer gerundet: sin/cos runder Winkel (90°, 180°, …) treffen sonst wegen der binären
    # Darstellung von math.pi eine ganze Koordinate um ~1e-13 m, und math.floor() beim Ursprung springt
    # dann eine ganze Zahl daneben. Weit unter der Bemaßungsgenauigkeit, ändert also keinen echten Wert.
    vertices = [(0.0, 0.0)]
    x, y = 0.0, 0.0
    for edge in edges:
        rad = math.radians(edge.angle_deg)
        x = round(x + edge.length_m * math.sin(rad), 6)
        y = round(y + edge.length_m * math.cos(rad), 6)
        vertices.append((x, y))

    closing_length = math.dist(vertices[-1], vertices[0])
    if not tol.MANUAL_MIN_EDGE_M <= closing_length <= tol.MANUAL_MAX_EDGE_M:
        raise ManualPolygonInvalid("Das Polygon schließt sich nicht sinnvoll")

    ring = [*vertices, vertices[0]]
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.is_empty:
        raise ManualPolygonInvalid("Der Umriss überschneidet sich selbst")
    polygon = orient(polygon, sign=1.0)

    area = float(polygon.area)
    if not tol.MANUAL_MIN_AREA_M2 <= area <= tol.MANUAL_MAX_AREA_M2:
        raise ManualPolygonInvalid("Fläche außerhalb des plausiblen Bereichs")

    min_x, min_y, _, _ = polygon.bounds
    return ManualOutline(
        polygon=polygon,
        area_m2=area,
        local_origin=(float(math.floor(min_x)), float(math.floor(min_y))),
    )
