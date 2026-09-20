"""Terrasse, Carport und Zufahrt automatisch setzen (Plan H3 3.3–3.5; Umsetzungsplan 3.8).

Die Terrasse liegt an der längsten Gartenkante des Hauses, der Carport so nah an der Hauptstraße, wie die
Nebengebäuderegeln erlauben. Beide sind Vorschläge, keine Planung: Der Kunde platziert sie nicht selbst.
"""

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from app.catalog.domain.offer import OptionOffer
from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import SiteContext
from app.configuration.domain.geometry import clean, keep_distance, place, segments, touching, turn, union
from app.configuration.domain.house import HouseType, edges_of, longest_role_edge, make_polygon
from app.configuration.domain.placement import Placement
from app.configuration.domain.presets import candidates
from app.configuration.domain.rotations import base_rotation_deg
from app.configuration.domain.surface import edge_requirement, part_surface

Point2 = tuple[float, float]


# ---------------------------------------------------------------------------
# Terrasse
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerraceSpec:
    slug: str
    depth_m: float
    height_above_terrain_m: float
    sealing_factor: float
    width_m: float | None
    """Länge der Gartenkante; `None`, wenn der Typ keine Kante mit der Rolle `garden` hat."""
    edge: tuple[Point2, Point2] | None

    @property
    def area_m2(self) -> float:
        """Fläche aus Typ und Rolle: hängt nicht von der Lage ab (Plan H3 3.8)."""
        return round(self.width_m * self.depth_m, tol.AREA_DECIMALS) if self.width_m else 0.0


def terrace_spec(option: OptionOffer, house: HouseType) -> TerraceSpec:
    params = option.params
    found = longest_role_edge(house, "garden")
    edge = (found[1], found[2]) if found else None
    return TerraceSpec(
        slug=option.slug,
        depth_m=float(params.get("depth_m", 3.0)),
        height_above_terrain_m=float(params.get("height_above_terrain_m", 0.3)),
        sealing_factor=float(params.get("sealing_factor", 1.0)),
        width_m=round(math.dist(*edge), 3) if edge else None,
        edge=edge,
    )


def terrace_polygon(spec: TerraceSpec, placement: Placement) -> Polygon | None:
    """Rechteck an der Gartenkante nach außen, rechts der Laufrichtung (Umrisse laufen gegen den Uhrzeiger)"""
    if spec.edge is None or not spec.width_m:
        return None
    (ax, ay), (bx, by) = spec.edge
    length = math.dist((ax, ay), (bx, by))
    nx, ny = (by - ay) / length, -(bx - ax) / length
    d = spec.depth_m
    model = make_polygon([(ax, ay), (bx, by), (bx + nx * d, by + ny * d), (ax + nx * d, ay + ny * d)])
    placed = place(model, placement.origin, placement.rotation_deg)
    return placed if isinstance(placed, Polygon) else None


# ---------------------------------------------------------------------------
# Carport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarportSpec:
    slug: str
    spaces: int
    width_m: float
    depth_m: float
    height_m: float

    @property
    def area_m2(self) -> float:
        return round(self.width_m * self.depth_m, tol.AREA_DECIMALS)


def carport_spec(option: OptionOffer) -> CarportSpec:
    params = option.params
    spaces = int(params.get("spaces", 1))
    return CarportSpec(
        slug=option.slug,
        spaces=spaces,
        width_m=float(params.get("width_m", 3.0 * spaces)),
        depth_m=float(params.get("depth_m", 5.0)),
        height_m=float(params.get("height_m", 2.7)),
    )


def carport_house(spec: CarportSpec) -> HouseType:
    """Der Carport als flacher Baukörper: die offene Seite (Kante 2, im Modell nach Norden) ist die
    „Straßenfassade“, damit dieselbe Drehung und Flächenrechnung wie beim Haus gilt."""
    w, d = spec.width_m, spec.depth_m
    footprint = make_polygon([(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)])
    return HouseType(
        slug=spec.slug,
        version=1,
        version_id=spec.slug,
        name=spec.slug,
        facade=footprint,
        projection=footprint,
        storeys="R",
        roof_form="flat",
        ridge_height_m=spec.height_m,
        eave_height_m=spec.height_m,
        living_area_m2=0.0,
        facade_roles={2: "street"},
    )


@dataclass(frozen=True)
class CarportPlacement:
    polygon: Polygon
    front: LineString
    """Die offene Seite zur Straße, von der die Zufahrt ausgeht."""
    origin: Point2
    rotation_deg: float
    setback: str
    """`known` (Regel für Nebenbauten), `assumed` (Abstände des Hauptbaus als Annahme) oder `relaxed`
    (auch damit kein Platz: ohne Abstände gesetzt)."""


def street_reference(ctx: SiteContext) -> LineString | None:
    """Hauptstraßenkante; ohne sie die längste Kante des Grundstücks (wie die Drehung, Plan H3 3.4)."""
    for edge in ctx.edges:
        if edge.seq == ctx.street_seq and isinstance(edge.geometry, LineString):
            return edge.geometry
    lines = segments(ctx.polygon)
    if not lines:
        return None
    a, b = max(lines, key=lambda s: math.dist(s[0], s[1]))
    return LineString([a, b])


def place_carport(
    spec: CarportSpec, ctx: SiteContext, obstacle: BaseGeometry | None
) -> CarportPlacement | None:
    """Carport nah an der Straße, ohne Haus und Terrasse (`obstacle`) zu berühren und mit einer Zufahrt, die
    sie nicht kreuzt; `None`, wenn es keine Stelle gibt."""
    house = carport_house(spec)
    rotation = base_rotation_deg(house, ctx)
    turned = turn(house.projection, rotation)
    blocked = None
    if obstacle is not None and not obstacle.is_empty:
        blocked = union(
            [
                touching(obstacle, turned),
                keep_distance(obstacle, turned, tol.OUTBUILDING_CLEARANCE_M),
            ]
        )
    assumption_needed = any(
        edge_requirement(edge, part, house, {}, "annex").assumed for part in ctx.parts for edge in ctx.edges
    )
    street = street_reference(ctx)
    for allow_assumed, label in ((True, "assumed" if assumption_needed else "known"), (False, "relaxed")):
        if not allow_assumed and not assumption_needed:
            break
        surface = _surface(house, rotation, ctx, allow_assumed)
        if blocked is not None and not surface.is_empty:
            surface = clean(surface.difference(blocked))
        if surface.is_empty:
            continue
        origin = _street_near(spec, rotation, surface, street, obstacle)
        if origin is None:
            continue
        polygon = place(house.facade, origin, rotation)
        front = _front(spec, origin, rotation)
        if isinstance(polygon, Polygon) and front is not None:
            return CarportPlacement(polygon, front, origin, rotation, label)
    return None


def _surface(house: HouseType, rotation: float, ctx: SiteContext, allow_assumed: bool) -> BaseGeometry:
    for exact in (True, False):
        surface = union(
            part_surface(
                house,
                part,
                rotation,
                ctx,
                {},
                exact=exact,
                building_kind="annex",
                use_bands=False,
                allow_assumed=allow_assumed,
            )
            for part in ctx.parts
        )
        if not surface.is_empty:
            return surface
    return Polygon()


def _access_path(front: LineString, street: BaseGeometry) -> LineString:
    """Kürzeste Verbindung von der Mitte der offenen Seite zur Straßenkante."""
    middle = front.interpolate(0.5, normalized=True)
    end = nearest_points(middle, street)[1]
    return LineString([(float(middle.x), float(middle.y)), (float(end.x), float(end.y))])


def _reachable(front: LineString, street: BaseGeometry | None, obstacle: BaseGeometry | None) -> bool:
    """Erreichbar heißt: Die Zufahrt (3 m breit) schneidet das Haus nicht (Plan H3 3.4)."""
    if street is None or obstacle is None or obstacle.is_empty:
        return True
    path = _access_path(front, street)
    if path.length < 1e-6:
        return True
    strip = path.buffer(tol.DRIVEWAY_WIDTH_M / 2.0, cap_style="flat")
    return float(strip.intersection(obstacle).area) < 1e-6


def _street_near(
    spec: CarportSpec,
    rotation: float,
    surface: BaseGeometry,
    street: LineString | None,
    obstacle: BaseGeometry | None,
) -> Point2 | None:
    """Erreichbarer Ursprung mit dem kleinsten Abstand zur Straße, dann möglichst mittig entlang der Kante."""
    body = carport_house(spec).facade
    scored: list[tuple[tuple[float, float], Point2]] = []
    for origin in candidates(surface):
        placed = place(body, origin, rotation)
        if street is None:
            score = (0.0, 0.0)
        else:
            lateral = abs(float(street.project(placed.centroid)) - float(street.length) / 2.0)
            score = (round(float(placed.distance(street)), 2), round(lateral, 2))
        scored.append((score, (round(origin[0], 3), round(origin[1], 3))))
    for _, origin in sorted(scored, key=lambda s: s[0]):
        front = _front(spec, origin, rotation)
        if front is not None and _reachable(front, street, obstacle):
            return origin
    return None


def _front(spec: CarportSpec, origin: Point2, rotation: float) -> LineString | None:
    line = place(LineString([(spec.width_m, spec.depth_m), (0.0, spec.depth_m)]), origin, rotation)
    return line if isinstance(line, LineString) else None


# ---------------------------------------------------------------------------
# Zufahrt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Driveway:
    source: str
    """`carport` oder `garage`."""
    polygon: BaseGeometry
    length_m: float

    @property
    def area_m2(self) -> float:
        return round(float(self.polygon.area), tol.AREA_DECIMALS)


def driveway(source: str, start: Point2, street: BaseGeometry) -> Driveway:
    """Kürzeste Verbindung von `start` zur Straßenkante, 3,00 m breit (Spez. 5.9.3)."""
    end = nearest_points(Point(start), street)[1]
    line = LineString([start, (float(end.x), float(end.y))])
    length = float(line.length)
    polygon: BaseGeometry = (
        line.buffer(tol.DRIVEWAY_WIDTH_M / 2.0, cap_style="flat") if length > 1e-6 else Polygon()
    )
    return Driveway(source, polygon, round(length, 3))


def carport_driveway(placement: CarportPlacement, street: BaseGeometry) -> Driveway:
    middle = placement.front.interpolate(0.5, normalized=True)
    return driveway("carport", (float(middle.x), float(middle.y)), street)


def garage_driveway(house: HouseType, placement: Placement, street: BaseGeometry) -> Driveway | None:
    """Zufahrt zum Garagentor des Typs; `None`, wenn der Typ keines hat."""
    if house.garage_door is None:
        return None
    edge_index, position = house.garage_door
    edges = [e for e in edges_of(house.facade) if e[0] == edge_index]
    if not edges:
        return None
    _, a, b = edges[0]
    point = Point(a[0] + (b[0] - a[0]) * position, a[1] + (b[1] - a[1]) * position)
    placed = place(point, placement.origin, placement.rotation_deg)
    if not isinstance(placed, Point):
        return None
    return driveway("garage", (float(placed.x), float(placed.y)), street)
