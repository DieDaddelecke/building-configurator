"""Fläche zulässiger Ursprünge und Abstandsanforderung je Kante (Plan H2 3.3, 3.4).

`edge_requirement` legt für ein Haus in einer Teilfläche fest, welcher Abstand von welcher Kante mit
welcher Bezugskontur einzuhalten ist. `part_surface` macht daraus die Fläche aller Ursprünge, bei denen das
Haus in der Teilfläche liegt, alle Abstände hält, kein Bauverbot berührt und im Bauband steht.
"""

from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.geometry import (
    clean,
    erode,
    keep_distance,
    polygons,
    sweep,
    touching,
    turn,
    union,
)
from app.configuration.domain.house import HouseType, role_edges
from app.configuration.domain.rotations import ridge_allows, ridge_orientation_rule
from app.envelope.domain.heights import Heights
from app.envelope.domain.inputs import Citation, EdgeInput
from app.envelope.domain.setbacks import Setback, setbacks_for_edge

BoundaryOptions = dict[int, bool]


@dataclass(frozen=True)
class EdgeRequirement:
    edge_seq: int
    kind: str
    distance_m: float | None
    """Einzuhaltender Abstand; `None`, wenn die Regel unbekannt ist (dann nur Hinweis)."""
    contour: str
    """`facade` oder `projection`: woran der Abstand gemessen wird."""
    on_boundary: bool
    status: str
    """`effective`, `not_regulated` oder `unknown`."""
    reason: str | None = None
    markers: list[str] = field(default_factory=list)
    on_boundary_allowed: bool = False
    on_boundary_max_height_m: float | None = None
    setback_kind: str | None = None
    citation: Citation | None = None


def house_heights(house: HouseType) -> Heights:
    return Heights(eave_m=house.eave_height_m, ridge_m=house.ridge_height_m)


def edge_requirement(
    edge: EdgeInput, part: PartContext, house: HouseType, boundary_options: BoundaryOptions
) -> EdgeRequirement:
    """Abstand einer Kante für dieses Haus in dieser Teilfläche (Spez. 5.3.2, 5.3.4).

    Die Regel wird mit den Höhen des Typs gerechnet, nicht mit der Höchsthöhe der Zone. Bei einer Kante
    `other` kommen zwei Regeln in Betracht: es gilt die mildere, damit keine gültige Lage verloren geht
    (Plan G3 ANNAHMEN BR03); die Kante ist als unklar markiert.
    """
    setbacks = setbacks_for_edge(edge, part.rules, house_heights(house), part.zone_code)
    chosen = bool(boundary_options.get(edge.seq))
    values: list[tuple[float, Setback, bool]] = []
    unknown: Setback | None = None
    for setback in setbacks:
        value = _binding(setback, chosen)
        if value is None:
            unknown = setback
        else:
            values.append((value, setback, chosen and bool(setback.params.get("allow_on_boundary"))))
    if not values:
        return EdgeRequirement(
            edge_seq=edge.seq,
            kind=edge.kind,
            distance_m=None,
            contour="facade",
            on_boundary=False,
            status="unknown",
            reason=(unknown.reason if unknown else None) or "missing",
            markers=sorted({m for s in setbacks for m in s.markers}),
            setback_kind=unknown.kind if unknown else None,
        )
    pick = min(values, key=lambda v: v[0]) if edge.kind == "other" else max(values, key=lambda v: v[0])
    distance, setback, on_boundary = pick
    allow = any(bool(s.params.get("allow_on_boundary")) for s in setbacks)
    height = setback.params.get("on_boundary_max_height_m")
    return EdgeRequirement(
        edge_seq=edge.seq,
        kind=edge.kind,
        distance_m=distance,
        contour="projection"
        if setback.params.get("measured_from") in ("roof_edge", "any_projection")
        else "facade",
        on_boundary=on_boundary,
        status=setback.status,
        reason=setback.reason,
        markers=sorted({m for s in setbacks for m in s.markers}),
        on_boundary_allowed=allow,
        on_boundary_max_height_m=float(height) if isinstance(height, int | float) else None,
        setback_kind=setback.kind,
        citation=setback.citation,
    )


def _binding(setback: Setback, on_boundary_chosen: bool) -> float | None:
    """Einzuhaltender Abstand einer Regel oder `None`, wenn sie nicht bindend ist (D12)."""
    if setback.status == "not_regulated":
        return 0.0
    if setback.status != "effective":
        return None
    if setback.kind == "setback_street":
        if setback.params.get("mode") == "alignment":
            return None
        minimum = setback.params.get("min_m")
        return float(minimum) if isinstance(minimum, int | float) else 0.0
    if on_boundary_chosen and setback.params.get("allow_on_boundary"):
        return 0.0
    return setback.strict_m


def requirements(
    house: HouseType, part: PartContext, ctx: SiteContext, boundary_options: BoundaryOptions
) -> dict[int, EdgeRequirement]:
    return {e.seq: edge_requirement(e, part, house, boundary_options) for e in ctx.edges}


def part_surface(
    house: HouseType,
    part: PartContext,
    rotation_deg: float,
    ctx: SiteContext,
    boundary_options: BoundaryOptions,
    *,
    exact: bool = False,
) -> BaseGeometry:
    """Alle Ursprünge, bei denen das Haus in `part` zulässig steht (lokale Meter).

    `exact = False` lässt 0,01 m Toleranz zu (Aussage „passt“, Ziehen), `exact = True` rechnet mit den
    Abständen selbst (Schnellstellungen).
    """
    projection = turn(house.projection, rotation_deg)
    facade = turn(house.facade, rotation_deg)
    if not isinstance(projection, Polygon) or not isinstance(facade, Polygon):
        return Polygon()
    area = erode(part.polygon, projection)
    for edge in ctx.edges:
        req = edge_requirement(edge, part, house, boundary_options)
        if req.distance_m is None or req.distance_m <= 0:
            continue
        moving = projection if req.contour == "projection" else facade
        distance = req.distance_m if exact else max(req.distance_m - tol.DISTANCE_TOLERANCE_M, 0.0)
        area = area.difference(keep_distance(edge.geometry, moving, distance))
        if area.is_empty:
            return Polygon()
    area = _apply_bands(area, house, part, rotation_deg, projection)
    if ctx.no_build is not None and not area.is_empty:
        area = area.difference(touching(ctx.no_build, projection))
    return clean(area)


def _apply_bands(
    area: BaseGeometry, house: HouseType, part: PartContext, rotation_deg: float, projection: Polygon
) -> BaseGeometry:
    building = [b.polygon for b in part.bands if b.band == "building"]
    if building and not area.is_empty:
        area = area.intersection(erode(union(building), projection))
    facade_bands = [b.polygon for b in part.bands if b.band == "facade"]
    if facade_bands and not area.is_empty:
        street = role_edges(house, "street")
        if street:
            strips = polygons(union(facade_bands))
            reachable = []
            for _, a, b in street:
                a_turned = _turn_point(a, rotation_deg)
                b_turned = _turn_point(b, rotation_deg)
                for strip in strips:
                    reachable.append(sweep(strip, (-a_turned[0], -a_turned[1]), (-b_turned[0], -b_turned[1])))
            area = area.intersection(union(reachable))
    return area


def _turn_point(point: tuple[float, float], rotation_deg: float) -> tuple[float, float]:
    turned = affinity.rotate(ShapelyPoint(point), -rotation_deg, origin=(0.0, 0.0))
    return float(turned.x), float(turned.y)


def surface_by_rotation(
    house: HouseType,
    parts: list[PartContext],
    rotations: list[float],
    ctx: SiteContext,
    boundary_options: BoundaryOptions,
    *,
    exact: bool = False,
) -> dict[float, BaseGeometry]:
    """Fläche je Drehung als Vereinigung über die Teilflächen. Eine Drehung, die die Firstrichtung der
    Teilfläche verletzt, trägt zu ihr nichts bei."""
    return {
        rotation: union(
            part_surface(house, part, rotation, ctx, boundary_options, exact=exact)
            for part in parts
            if ridge_allows(house, rotation, ctx, ridge_orientation_rule(part))
        )
        for rotation in rotations
    }
