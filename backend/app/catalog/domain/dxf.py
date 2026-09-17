"""Umriss-Polygone aus DXF lesen (Plan H1 3.3).

Zwei Layer, je ein geschlossenes Polygon in lokalen Metern, Y-Achse = Modellnord (Spez. 5.4.4): die
Fassadenhülle (`EMPRISE_FOOTPRINT_FACADE`) und die Projektion mit Dachüberstand und Vorsprüngen
(`EMPRISE_FOOTPRINT_PROJECTION`). Kein Freihandeintippen von Koordinaten (wie beim Kataster-Import).
"""

import io

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import LWPolyline
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from app.catalog.domain import tolerances as tol


class FootprintDxfInvalid(ValueError):
    """Das DXF trägt keinen gültigen Umriss (Code `footprint_dxf_invalid`)."""


def _read(data: bytes) -> Drawing:
    try:
        return ezdxf.read(io.StringIO(data.decode("utf-8", errors="replace")))
    except ezdxf.DXFError as exc:
        raise FootprintDxfInvalid("Datei ist keine gültige DXF-Zeichnung") from exc


def _polygon_on_layer(doc: Drawing, layer: str) -> Polygon:
    msp = doc.modelspace()
    candidates = [
        e for e in msp.query(f'LWPOLYLINE[layer=="{layer}"]') if isinstance(e, LWPolyline) and e.closed
    ]
    if not candidates:
        raise FootprintDxfInvalid(f"Kein geschlossenes Polygon auf Layer {layer}")
    if len(candidates) > 1:
        raise FootprintDxfInvalid(f"Mehr als ein Polygon auf Layer {layer}")
    points = [(x, y) for x, y, *_ in candidates[0].get_points("xyb")]
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.is_empty:
        raise FootprintDxfInvalid(f"Polygon auf Layer {layer} überschneidet sich selbst")
    area = float(polygon.area)
    if not tol.FOOTPRINT_MIN_AREA_M2 <= area <= tol.FOOTPRINT_MAX_AREA_M2:
        raise FootprintDxfInvalid(
            f"Fläche auf Layer {layer} außerhalb des plausiblen Bereichs ({area:.0f} m²)"
        )
    return orient(polygon, sign=1.0)


def read_footprints(data: bytes) -> tuple[Polygon, Polygon]:
    """`(footprint_facade, footprint_projection)`, beide gegen den Uhrzeigersinn orientiert."""
    doc = _read(data)
    facade = _polygon_on_layer(doc, tol.FOOTPRINT_LAYER_FACADE)
    projection = _polygon_on_layer(doc, tol.FOOTPRINT_LAYER_PROJECTION)
    if projection.area < facade.area:
        raise FootprintDxfInvalid("Projektion (mit Dachüberstand) ist kleiner als die Fassadenhülle")
    return facade, projection
