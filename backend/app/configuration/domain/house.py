"""Ein Haustyp als Eingabe der Fachlogik (Plan H2 4.1): Umrisse, Höhen, Dach und Fassadenrollen aus H1.

Koordinaten sind lokale Modellmeter, die Y-Achse ist Modellnord (Spez. 5.4.4). Beide Umrisse sind gegen
den Uhrzeigersinn orientiert; die Kante `i` läuft von Punkt `i` zum Punkt `i + 1` (der letzte schließt).
Außen liegt dann rechts der Laufrichtung.
"""

import math
from dataclasses import dataclass, field

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

Point = tuple[float, float]


@dataclass(frozen=True)
class HouseType:
    slug: str
    version: int
    version_id: str
    name: str
    facade: Polygon
    projection: Polygon
    storeys: str
    roof_form: str
    """Begriff der PLU-Regeln (`gable`, `hip`, `mono_pitch`, `flat`, `mansard`, `other`), bei Typen aus H1
    auch `complex`; bei einer Form, die der PLU nicht eindeutig benennt, die Form des Kerns (`half_hip`)."""
    ridge_height_m: float
    """Bei Flachdach die Oberkante der Attika (Plan H1 3.1)."""
    eave_height_m: float
    living_area_m2: float
    pitch_deg: float | None = None
    """Neigung, wenn alle Dachflächen gleich geneigt sind."""
    roof_form_readings: tuple[str, ...] = ()
    """Begriffe der PLU-Regeln, die eine nicht eindeutig benannte Form sein kann (E-HM-61); sonst leer."""
    roof_pitches_deg: tuple[float, ...] = ()
    """Verschiedene Neigungen der Dachflächen (Mansarde, Krüppelwalm), wenn `pitch_deg` fehlt (E-HM-61)."""
    ridge_direction: str | None = None
    """`laengs` oder `quer`: First parallel zur langen oder zur kurzen Rechteckseite."""
    facade_roles: dict[int, str] = field(default_factory=dict)
    """Kantenindex → `street`, `garden`, `side_left`, `side_right`; leer, solange nicht zugewiesen."""
    family: str | None = None
    alternatives: tuple[str, ...] = ()
    garage_door: tuple[int, float] | None = None
    """`(Kantenindex, Anteil 0–1 vom Kantenanfang)` auf der Fassade (Plan H1 3.1, ANNAHMEN H10)."""

    @property
    def is_flat(self) -> bool:
        return self.roof_form == "flat"

    @property
    def highest_m(self) -> float:
        return max(self.ridge_height_m, self.eave_height_m)


def make_polygon(points: list[list[float]] | list[Point]) -> Polygon:
    """Umriss aus offenem Punktring, gegen den Uhrzeigersinn."""
    return orient(Polygon([(float(x), float(y)) for x, y, *_ in points]), sign=1.0)


def azimuth_deg(dx: float, dy: float) -> float:
    """Azimut eines Vektors: 0° = Norden (+Y), im Uhrzeigersinn."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def edges_of(polygon: Polygon) -> list[tuple[int, Point, Point]]:
    coords = [(float(x), float(y)) for x, y, *_ in polygon.exterior.coords][:-1]
    return [(i, coords[i], coords[(i + 1) % len(coords)]) for i in range(len(coords))]


def role_edges(house: HouseType, role: str) -> list[tuple[int, Point, Point]]:
    return [edge for edge in edges_of(house.facade) if house.facade_roles.get(edge[0]) == role]


def role_normal_model_deg(house: HouseType, role: str) -> float | None:
    """Azimut der Außennormalen der längsten Kante mit dieser Rolle im Modell."""
    edges = role_edges(house, role)
    if not edges:
        return None
    _, a, b = max(edges, key=lambda e: math.dist(e[1], e[2]))
    return (azimuth_deg(b[0] - a[0], b[1] - a[1]) + 90.0) % 360.0


def street_normal_model_deg(house: HouseType) -> float | None:
    """Azimut der Außennormalen der Straßenfassade im Modell (längste Kante mit Rolle `street`)."""
    return role_normal_model_deg(house, "street")


def longest_role_edge(house: HouseType, role: str) -> tuple[int, Point, Point] | None:
    """Längste Fassadenkante mit dieser Rolle: Kantenindex und Endpunkte im Modell."""
    edges = role_edges(house, role)
    return max(edges, key=lambda e: math.dist(e[1], e[2])) if edges else None


def ridge_axis_model_deg(house: HouseType) -> float | None:
    """Richtung des Firsts im Modell (Azimut modulo 180°) oder `None` ohne First (Flachdach, keine Angabe)."""
    if house.is_flat or house.ridge_direction is None:
        return None
    rect = house.facade.minimum_rotated_rectangle
    coords = [(float(x), float(y)) for x, y, *_ in rect.exterior.coords][:-1]
    if len(coords) < 4:
        return None
    first = (coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    second = (coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
    long_side, short_side = (first, second) if math.hypot(*first) >= math.hypot(*second) else (second, first)
    side = long_side if house.ridge_direction == "laengs" else short_side
    return azimuth_deg(*side) % 180.0
