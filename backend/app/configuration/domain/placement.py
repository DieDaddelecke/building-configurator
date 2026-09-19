"""Prüfung einer Lage je Kante mit allen Verstößen (Plan H2 3.1, 3.4; Spez. 5.3.4).

Maßgeblich ist diese Prüfung, nicht die Fläche zulässiger Ursprünge: verschiedene Regeln haben verschiedene
Bezugskonturen (Straße ab Fassade, Nachbar ab Dachüberstand). Die Fläche muss zu ihr passen; das sichern
die Eigenschaftstests.
"""

from dataclasses import dataclass, field

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from app.configuration.domain import tolerances as tol
from app.configuration.domain.checks import FAIL, HINT, PASS, UNKNOWN, Check, type_checks
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.geometry import clean, distance, place, polygons, segments, union
from app.configuration.domain.house import HouseType, role_edges
from app.configuration.domain.rotations import (
    ridge_deviation_deg,
    ridge_orientation_rule,
)
from app.configuration.domain.surface import BoundaryOptions, EdgeRequirement, requirements
from app.envelope.domain.bands import Band

Point = tuple[float, float]


@dataclass(frozen=True)
class Placement:
    origin: Point
    """Lokale Meter (Ost, Nord) des Modellursprungs."""
    rotation_deg: float


@dataclass(frozen=True)
class EdgeMeasure:
    seq: int
    kind: str
    measured_m: float
    required_m: float | None
    contour: str
    status: str
    on_boundary: bool
    on_boundary_allowed: bool
    markers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlacementResult:
    placement: Placement
    facade: BaseGeometry
    projection: BaseGeometry
    part: PartContext | None
    checks: list[Check]
    edges: list[EdgeMeasure]

    @property
    def blocking(self) -> list[Check]:
        return [c for c in self.checks if c.blocks]

    @property
    def valid(self) -> bool:
        return not self.blocking


def check_placement(
    house: HouseType, placement: Placement, ctx: SiteContext, boundary_options: BoundaryOptions
) -> PlacementResult:
    facade = place(house.facade, placement.origin, placement.rotation_deg)
    projection = place(house.projection, placement.origin, placement.rotation_deg)
    checks: list[Check] = []
    part = _containing_part(ctx, projection)
    containment = _containment(ctx, projection, part)
    if containment is not None:
        checks.append(containment)
    if part is None:
        part = _best_part(ctx, projection)
    if part is None:
        return PlacementResult(placement, facade, projection, None, checks, [])

    reqs = requirements(house, part, ctx, boundary_options)
    edge_measures: list[EdgeMeasure] = []
    for edge in ctx.edges:
        req = reqs[edge.seq]
        moving = projection if req.contour == "projection" else facade
        measured = distance(moving, edge.geometry)
        status, check = _edge_check(house, edge.seq, req, measured, part)
        edge_measures.append(
            EdgeMeasure(
                seq=edge.seq,
                kind=edge.kind,
                measured_m=round(measured, tol.STORAGE_DECIMALS),
                required_m=req.distance_m,
                contour=req.contour,
                status=status,
                on_boundary=req.on_boundary,
                on_boundary_allowed=req.on_boundary_allowed,
                markers=req.markers,
            )
        )
        checks.extend(check)
    checks.extend(_band_checks(house, part, placement, facade, projection, ctx))
    checks.extend(_overlay_checks(ctx, projection))
    checks.extend(_ridge_check(house, placement, part, ctx))
    checks.extend(type_checks(house, part, ctx))
    checks.extend(_roles_hint(house, ctx))
    return PlacementResult(placement, facade, projection, part, checks, edge_measures)


def _containing_part(ctx: SiteContext, projection: BaseGeometry) -> PartContext | None:
    for part in ctx.parts:
        if part.polygon.buffer(tol.DISTANCE_TOLERANCE_M).covers(projection):
            return part
    return None


def _best_part(ctx: SiteContext, projection: BaseGeometry) -> PartContext | None:
    if not ctx.parts:
        return None
    return max(ctx.parts, key=lambda p: float(p.polygon.intersection(projection).area))


def _containment(ctx: SiteContext, projection: BaseGeometry, part: PartContext | None) -> Check | None:
    if part is not None:
        return None
    if ctx.is_free:
        return Check(code="outside_outline", kind="site", status=FAIL)
    inside_site = ctx.polygon.buffer(tol.DISTANCE_TOLERANCE_M).covers(projection)
    return Check(code="crosses_zones" if inside_site else "outside_site", kind="site", status=FAIL)


def _edge_check(
    house: HouseType, seq: int, req: EdgeRequirement, measured: float, part: PartContext
) -> tuple[str, list[Check]]:
    kind = req.setback_kind or _fallback_kind(req.kind)
    if req.distance_m is None:
        return UNKNOWN, [
            Check(
                code=f"{kind}_unknown",
                kind=kind,
                status=UNKNOWN,
                binding=False,
                edge_seq=seq,
                zone_code=part.zone_code,
                reason=req.reason,
                measured=round(measured, 2),
                params={"markers": req.markers},
            )
        ]
    ok = measured >= req.distance_m - tol.DISTANCE_TOLERANCE_M
    checks = [
        Check(
            code=kind,
            kind=kind,
            status=PASS if ok else FAIL,
            measured=round(measured, 2),
            limit=round(req.distance_m, 2),
            unit="m",
            edge_seq=seq,
            zone_code=part.zone_code,
            citation=req.citation,
            params={"on_boundary": req.on_boundary, "markers": req.markers},
        )
    ]
    if req.on_boundary and req.on_boundary_max_height_m is not None:
        high = house.highest_m
        checks.append(
            Check(
                code="on_boundary_height",
                kind=kind,
                status=PASS if high <= req.on_boundary_max_height_m + tol.HEIGHT_TOLERANCE_M else FAIL,
                measured=high,
                limit=req.on_boundary_max_height_m,
                unit="m",
                edge_seq=seq,
                zone_code=part.zone_code,
                citation=req.citation,
            )
        )
    if "alignment" in req.markers:
        checks.append(Check(code="setback_alignment", kind=kind, status=HINT, binding=False, edge_seq=seq))
    return (PASS if ok else FAIL), checks


def _fallback_kind(edge_kind: str) -> str:
    return {"street": "setback_street", "rear": "setback_rear"}.get(edge_kind, "setback_side")


def _band_checks(
    house: HouseType,
    part: PartContext,
    placement: Placement,
    facade: BaseGeometry,
    projection: BaseGeometry,
    ctx: SiteContext,
) -> list[Check]:
    checks: list[Check] = []
    for band in part.bands:

        def make(
            code: str,
            status: str,
            *,
            binding: bool = True,
            measured: float | None = None,
            limit: float | None = None,
            unit: str | None = None,
            _band: Band = band,
        ) -> Check:
            return Check(
                code=code,
                kind="setback_street",
                status=status,
                binding=binding,
                measured=measured,
                limit=limit,
                unit=unit,
                edge_seq=_band.edge_seq,
                zone_code=part.zone_code,
                citation=_band.citation,
            )

        if band.band == "building":
            inside = band.polygon.buffer(tol.DISTANCE_TOLERANCE_M).covers(projection)
            checks.append(make("band_building", PASS if inside else FAIL, limit=band.max_m, unit="m"))
        elif band.band == "facade":
            street = _street_facade(house, placement)
            edge = next((e for e in ctx.edges if e.seq == band.edge_seq), None)
            if street is None or edge is None:
                checks.append(make("band_facade_unchecked", UNKNOWN, binding=False))
                continue
            measured = distance(street, edge.geometry)
            ok = measured <= band.max_m + tol.DISTANCE_TOLERANCE_M
            checks.append(
                make(
                    "band_facade",
                    PASS if ok else FAIL,
                    measured=round(measured, 2),
                    limit=band.max_m,
                    unit="m",
                )
            )
        else:
            checks.append(make("band_unclear", HINT, binding=False))
    return checks


def _street_facade(house: HouseType, placement: Placement) -> BaseGeometry | None:
    lines = role_edges(house, "street")
    if not lines:
        return None
    from shapely.geometry import LineString

    return union(place(LineString([a, b]), placement.origin, placement.rotation_deg) for _, a, b in lines)


def _overlay_checks(ctx: SiteContext, projection: BaseGeometry) -> list[Check]:
    checks: list[Check] = []
    if ctx.no_build is not None and float(projection.intersection(ctx.no_build).area) > 1e-6:
        checks.append(Check(code="no_build_area", kind="site", status=FAIL))
    if ctx.restricted is not None and float(projection.intersection(ctx.restricted).area) > 1e-6:
        checks.append(Check(code="restricted_area", kind="site", status=HINT, binding=False))
    return checks


def _ridge_check(house: HouseType, placement: Placement, part: PartContext, ctx: SiteContext) -> list[Check]:
    orientation = ridge_orientation_rule(part)
    if orientation == "any" or ctx.is_free:
        return []
    deviation = ridge_deviation_deg(house, placement.rotation_deg, ctx, orientation)
    if deviation is None:
        applicable = house.is_flat or house.ridge_direction is None
        return [
            Check(
                code="ridge_orientation",
                kind="roof",
                status="not_applicable" if applicable else UNKNOWN,
                binding=False,
                zone_code=part.zone_code,
                reason="no_ridge" if applicable else "no_street",
            )
        ]
    return [
        Check(
            code="ridge_orientation",
            kind="roof",
            status=PASS if deviation <= tol.RIDGE_TOLERANCE_DEG else FAIL,
            measured=round(deviation, 1),
            limit=tol.RIDGE_TOLERANCE_DEG,
            unit="deg",
            zone_code=part.zone_code,
            params={"orientation": orientation},
        )
    ]


def _roles_hint(house: HouseType, ctx: SiteContext) -> list[Check]:
    if ctx.is_free or house.facade_roles:
        return []
    return [Check(code="facade_roles_missing", kind="site", status=HINT, binding=False)]


def footprint_polygons(result: PlacementResult) -> tuple[list[Polygon], list[Polygon]]:
    """Fassade und Projektion der Lage als Flächenlisten."""
    return polygons(clean(result.facade)), polygons(clean(result.projection))


def all_segments(geometry: BaseGeometry) -> list[tuple[Point, Point]]:
    return segments(geometry)
