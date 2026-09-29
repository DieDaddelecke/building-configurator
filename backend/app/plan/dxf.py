"""Lageplan als DXF (V 3.7, Umsetzungsplan 3.10): einmal in Lambert-93, einmal in lokalen Metern.

Ebenen französisch, weil das Büro in Frankreich arbeitet; Einheit Meter, Format R2010, geschlossene
Polylinien. Die lokale Datei trägt ihren Ursprung als Punkt und Text mit den Lambert-93-Koordinaten, damit
das Büro sie lagerichtig einsetzen kann (Vorgehen in docs/BETRIEB.md).

Seit AN5 (docs/PLAN_AN5_AUSGABE.md 3.4) auch Bauband, Vorgaben, Schnittlinien und der Gabarit: je Stufe die
Kontur als Höhenlinie und ein geschlossener Körper (Polyface). Diese Ebenen entstehen nur, wenn sie belegt
sind; die Datei von V bleibt damit inhaltlich gleich.
"""

import io
from typing import Any, Literal

from app.plan.geometry import Area, Plan, Ring

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
"""Ebenen von V; `render` legt sie alle an, solange `all_layers` gilt."""
EXTRA_LAYERS: dict[str, int] = {
    "BANDE_CONSTRUCTIBLE": 4,
    "ZONE_NON_AEDIFICANDI": 1,
    "ZONE_CONTRAINTE": 30,
    "COUPE": 6,
}
STAGE_COLORS = {"lenient": 3, "strict": 5}
EDGE_LAYERS = {"street": "LIMITE_VOIE", "side": "LIMITE_SEPARATIVE", "rear": "LIMITE_FOND"}
CONSTRAINT_LAYERS = {"no_build": "ZONE_NON_AEDIFICANDI", "restricts": "ZONE_CONTRAINTE"}
TEXT_HEIGHT_M = 0.5
CUT_TEXT_HEIGHT_M = 1.0
DECIMALS = 3
COLLINEAR_M2 = 1e-7
"""Dreiecksfläche, unter der drei Punkte eines Rings als auf einer Geraden gelten."""


def stage_layer(reading: str, kind: Literal["COURBES", "VOLUME"], roof: bool) -> str:
    """`GABARIT_LARGE_COURBES`, `GABARIT_STRICT_VOLUME_TOIT` …; auch die Ebenen im GeoJSON (3.5)."""
    name = f"GABARIT_{'LARGE' if reading == 'lenient' else 'STRICT'}_{kind}"
    return f"{name}_TOIT" if roof else name


def render(
    plan: Plan,
    variant: Variant,
    notes: list[str],
    *,
    all_layers: bool = True,
    cartouche: list[str] | None = None,
) -> bytes:
    """DXF als Bytes. `notes` sind Textzeilen (Vorgang, Quelle, Ursprung) oben links am Plan.

    `all_layers=False` legt auch die Ebenen von V nur an, wenn sie belegt sind (Analyse, AN5). `cartouche`
    ist das Schriftfeld der Organisation unten links auf der Ebene `CARTOUCHE` (AN6, PLAN_AN6_MANDANTEN 3.5);
    ohne Angaben entsteht die Ebene nicht."""
    import ezdxf  # lokal: nur der Worker braucht die Bibliothek
    from ezdxf import units

    if variant == "L93" and not plan.georeferenced:
        raise ValueError("Ein frei gezeichnetes Grundstück hat keine Lage in Lambert-93")
    dx, dy = plan.origin if variant == "L93" else (0.0, 0.0)
    dz = plan.reference_ngf if variant == "L93" and plan.reference_ngf is not None else 0.0
    doc = ezdxf.new("R2010")
    doc.units = units.M
    doc.header["$MEASUREMENT"] = 1
    if all_layers:
        for name, color in LAYERS.items():
            doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def layer(name: str, color: int | None = None) -> dict[str, Any]:
        if not doc.layers.has_entry(name):
            doc.layers.add(name, color=color or LAYERS.get(name) or EXTRA_LAYERS.get(name) or 7)
        return {"layer": name}

    def shifted(ring: Ring) -> list[tuple[float, float]]:
        return [(round(x + dx, DECIMALS), round(y + dy, DECIMALS)) for x, y in ring]

    def polygon(ring: Ring | None, name: str, elevation: float | None = None) -> None:
        if ring and len(ring) >= 3:
            points = shifted(_open(ring))
            attribs = layer(name)
            if elevation is not None:
                attribs["elevation"] = round(elevation + dz, DECIMALS)
            msp.add_lwpolyline(points, close=True, dxfattribs=attribs)

    for ring in plan.neighbour_parcels:
        polygon(ring, "VOISINS_PARCELLES")
    for ring in plan.neighbour_buildings:
        polygon(ring, "VOISINS_BATI")
    for ring in plan.parcel:
        polygon(ring, "PARCELLE")
    for edge in plan.edges:
        msp.add_lwpolyline(shifted(edge.coords), dxfattribs=layer(EDGE_LAYERS.get(edge.kind, "LIMITE_AUTRE")))
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

    for ring in plan.bands:
        polygon(ring, "BANDE_CONSTRUCTIBLE")
    for constraint in plan.constraints:
        target = CONSTRAINT_LAYERS.get(constraint.effect)
        if target is None:
            continue
        for ring in constraint.rings:
            polygon(ring, target)
        for line in constraint.lines:
            if len(line) >= 2:
                msp.add_lwpolyline(shifted(line), dxfattribs=layer(target))
    for cut in plan.cuts:
        start, end = shifted([cut.start, cut.end])
        msp.add_line(start, end, dxfattribs=layer("COUPE"))
        for point, text in ((start, cut.key), (end, f"{cut.key}'")):
            msp.add_text(text, height=CUT_TEXT_HEIGHT_M, dxfattribs=layer("COUPE")).set_placement(point)
    for stage in plan.stages:
        color = STAGE_COLORS.get(stage.reading, 7)
        contour_layer = stage_layer(stage.reading, "COURBES", stage.roof)
        volume_layer = stage_layer(stage.reading, "VOLUME", stage.roof)
        for area in stage.areas:
            for ring in (area.exterior, *area.holes):
                layer(contour_layer, color)
                polygon(ring, contour_layer, elevation=stage.to_m)
            faces = solid(area, stage.from_m + dz, stage.to_m + dz, (dx, dy))
            if faces:
                mesh = msp.add_polyface(dxfattribs=layer(volume_layer, color))
                mesh.append_faces(faces)
                mesh.optimize(precision=DECIMALS)

    msp.add_point((dx, dy), dxfattribs=layer("ORIGINE"))
    min_x, min_y, _max_x, max_y = plan.bounds()
    for index, note in enumerate(notes):
        msp.add_text(note, height=TEXT_HEIGHT_M, dxfattribs=layer("TEXTE")).set_placement(
            (round(min_x + dx, DECIMALS), round(max_y + dy + (len(notes) - index) * 0.8, DECIMALS))
        )
    for index, entry in enumerate(cartouche or []):
        msp.add_text(entry, height=TEXT_HEIGHT_M, dxfattribs=layer("CARTOUCHE", 7)).set_placement(
            (round(min_x + dx, DECIMALS), round(min_y + dy - (index + 2) * 0.8, DECIMALS))
        )

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def _open(ring: Ring) -> Ring:
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def _clean(ring: Ring, shift: tuple[float, float]) -> list[tuple[float, float]]:
    """Offener Ring, gerundet wie die Datei, ohne doppelte und ohne Punkte auf einer Geraden. Die Zerlegung
    in Dreiecke ließe solche Punkte aus; die Seitenfläche daran hätte dann keinen Nachbarn im Deckel."""
    points: list[tuple[float, float]] = []
    for x, y in _open(ring):
        point = (round(x + shift[0], DECIMALS), round(y + shift[1], DECIMALS))
        if not points or point != points[-1]:
            points.append(point)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    changed = True
    while changed and len(points) >= 3:
        changed = False
        for index in range(len(points)):
            before, point, after = points[index - 1], points[index], points[(index + 1) % len(points)]
            if abs(_signed_area([before, point, after])) < COLLINEAR_M2:
                del points[index]
                changed = True
                break
    return points


def _signed_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True)
    )


def solid(
    area: Area, bottom: float, top: float, shift: tuple[float, float] = (0.0, 0.0)
) -> list[list[tuple[float, float, float]]]:
    """Geschlossener Körper von `bottom` bis `top` (3.4, 7.1 Nr. 12): Seitenflächen je Kante, Deckel und
    Boden als Dreiecke mit Löchern. Außenring gegen den Uhrzeigersinn, Löcher im Uhrzeigersinn; so zeigen
    alle Flächen nach außen. Ein zu kleiner Ring ergibt nichts."""
    from ezdxf.math.triangulation import mapbox_earcut_2d

    exterior = _clean(area.exterior, shift)
    if len(exterior) < 3 or top <= bottom:
        return []
    if _signed_area(exterior) < 0:
        exterior.reverse()
    holes: list[list[tuple[float, float]]] = []
    for raw in area.holes:
        hole = _clean(raw, shift)
        if len(hole) >= 3:
            if _signed_area(hole) > 0:
                hole.reverse()
            holes.append(hole)
    z0, z1 = round(bottom, DECIMALS), round(top, DECIMALS)
    faces: list[list[tuple[float, float, float]]] = []
    for ring in (exterior, *holes):
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
            faces.append([(x1, y1, z0), (x2, y2, z0), (x2, y2, z1), (x1, y1, z1)])
    for triangle in mapbox_earcut_2d(exterior, holes):
        corners = [(float(p.x), float(p.y)) for p in triangle]
        if abs(_signed_area(corners)) < 1e-9:
            continue
        if _signed_area(corners) < 0:
            corners.reverse()
        faces.append([(x, y, z1) for x, y in corners])
        faces.append([(x, y, z0) for x, y in reversed(corners)])
    return faces
