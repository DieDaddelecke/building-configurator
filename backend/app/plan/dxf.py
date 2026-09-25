"""Lageplan als DXF (V 3.7, Umsetzungsplan 3.10): einmal in Lambert-93, einmal in lokalen Metern.

Ebenen französisch, weil das Büro in Frankreich arbeitet; Einheit Meter, Format R2010, geschlossene
Polylinien. Die lokale Datei trägt ihren Ursprung als Punkt und Text mit den Lambert-93-Koordinaten, damit
das Büro sie lagerichtig einsetzen kann (Vorgehen in docs/BETRIEB.md).
"""

import io
from typing import Literal

from app.plan.geometry import Plan, Ring

Variant = Literal["L93", "local"]

LAYERS: dict[str, int] = {
    "PARCELLE": 7,
    "LIMITE_VOIE": 5,
    "LIMITE_SEPARATIVE": 8,
    "LIMITE_FOND": 8,
    "LIMITE_AUTRE": 8,
    "VOISINS_PARCELLES": 9,
    "VOISINS_BATI": 9,
    "ZONE_CONSTRUCTIBLE_LARGE": 3,
    "ZONE_CONSTRUCTIBLE_STRICTE": 3,
    "MAISON_FACADE": 1,
    "MAISON_DEBORD": 1,
    "TERRASSE": 30,
    "CARPORT": 40,
    "ACCES": 42,
    "ORIGINE": 6,
    "TEXTE": 7,
}
EDGE_LAYERS = {"street": "LIMITE_VOIE", "side": "LIMITE_SEPARATIVE", "rear": "LIMITE_FOND"}
TEXT_HEIGHT_M = 0.5


def render(plan: Plan, variant: Variant, notes: list[str]) -> bytes:
    """DXF als Bytes. `notes` sind Textzeilen (Vorgang, Quelle, Ursprung) oben links am Plan."""
    import ezdxf  # lokal: nur der Worker braucht die Bibliothek
    from ezdxf import units

    if variant == "L93" and not plan.georeferenced:
        raise ValueError("Ein frei gezeichnetes Grundstück hat keine Lage in Lambert-93")
    dx, dy = plan.origin if variant == "L93" else (0.0, 0.0)
    doc = ezdxf.new("R2010")
    doc.units = units.M
    doc.header["$MEASUREMENT"] = 1
    for name, color in LAYERS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def shifted(ring: Ring) -> list[tuple[float, float]]:
        return [(round(x + dx, 3), round(y + dy, 3)) for x, y in ring]

    def polygon(ring: Ring | None, layer: str) -> None:
        if ring and len(ring) >= 3:
            points = shifted(ring[:-1] if ring[0] == ring[-1] else ring)
            msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})

    for ring in plan.neighbour_parcels:
        polygon(ring, "VOISINS_PARCELLES")
    for ring in plan.neighbour_buildings:
        polygon(ring, "VOISINS_BATI")
    for ring in plan.parcel:
        polygon(ring, "PARCELLE")
    for edge in plan.edges:
        msp.add_lwpolyline(
            shifted(edge.coords), dxfattribs={"layer": EDGE_LAYERS.get(edge.kind, "LIMITE_AUTRE")}
        )
    for ring in plan.lenient:
        polygon(ring, "ZONE_CONSTRUCTIBLE_LARGE")
    for ring in plan.strict:
        polygon(ring, "ZONE_CONSTRUCTIBLE_STRICTE")
    polygon(plan.projection, "MAISON_DEBORD")
    polygon(plan.facade, "MAISON_FACADE")
    polygon(plan.terrace, "TERRASSE")
    polygon(plan.carport, "CARPORT")
    for ring in plan.driveways:
        polygon(ring, "ACCES")

    msp.add_point((dx, dy), dxfattribs={"layer": "ORIGINE"})
    min_x, _min_y, _max_x, max_y = plan.bounds()
    for index, line in enumerate(notes):
        msp.add_text(line, height=TEXT_HEIGHT_M, dxfattribs={"layer": "TEXTE"}).set_placement(
            (round(min_x + dx, 3), round(max_y + dy + (len(notes) - index) * 0.8, 3))
        )

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")
