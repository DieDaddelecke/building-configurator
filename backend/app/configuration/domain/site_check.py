"""Prüfung eines Hauses aus der Hausbeschreibung auf dem Grundstück (docs/PLAN_HAUSMODELL.md 3.1, 3.7; HM4).

Wie `design.site_part` ohne Linie und Optionen aus H3: Lage je Kante, Flächen, Regeln der Teilfläche, Material
aus den Klassen von Fassade und Dach, Stellplätze, Himmelsrichtung. Terrasse und Carport kommen mit HM5 als
Slots `site` dazu (Ergänzung 7). Eine unzulässige Lage wird nicht abgelehnt, sondern bewertet (E-HM-6); dazu
gibt es den Vorschlag einer zulässigen Lage (Ergänzung 9).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from app.configuration.domain.areas import Areas, Buildings, compute_areas
from app.configuration.domain.checks import Check
from app.configuration.domain.compliance import MaterialSubject, SiteFacts, geometry_checks, rule_checks
from app.configuration.domain.context import SiteContext
from app.configuration.domain.fit import TypeFit, eligible_parts, evaluate_type
from app.configuration.domain.geometry import turn
from app.configuration.domain.house import HouseType
from app.configuration.domain.orientation import Orientation, orientation
from app.configuration.domain.placement import Placement, PlacementResult, check_placement
from app.configuration.domain.rotations import site_rotations
from app.configuration.domain.surface import BoundaryOptions, surface_by_rotation


@dataclass(frozen=True)
class SiteCheck:
    result: PlacementResult | None
    """Prüfung je Kante; `None` ohne Lage."""
    areas: Areas | None
    checks: list[Check]
    """Alle Prüfungen: Lage, Typ in der Teilfläche, Flächen, Material, Stellplätze; ohne Lage die des Typs."""
    orientation: Orientation | None
    fit: TypeFit
    """Zulässigkeit mit dieser Hausbeschreibung (Spez. 5.4.6); gesperrt heißt: keine zulässige Lage."""
    suggestion: Placement | None
    """Nächste zulässige Lage, wenn die Lage bindende Verstöße hat und es eine gibt."""


def placement_surfaces(
    house: HouseType, ctx: SiteContext, boundary: BoundaryOptions
) -> dict[float, BaseGeometry]:
    """Fläche zulässiger Ursprünge je erlaubter Drehung: mit den Abständen selbst, damit eine eingerastete
    Lage nicht 1 cm zu nah liegt; passt das Haus nur mit der Toleranz von 0,01 m, gilt diese Fläche (H2)."""
    parts = eligible_parts(house, ctx)
    rotations = site_rotations(house, ctx)
    exact = surface_by_rotation(house, parts, rotations, ctx, boundary, exact=True)
    tolerant = surface_by_rotation(house, parts, rotations, ctx, boundary)
    return {r: (exact[r] if not exact[r].is_empty else tolerant[r]) for r in rotations}


def _gap_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def _origin_keeping_centre(house: HouseType, placement: Placement, rotation: float) -> tuple[float, float]:
    """Ursprung, bei dem die Fassade nach der Drehung `rotation` dieselbe Mitte hat wie jetzt."""
    now = turn(house.facade, placement.rotation_deg).centroid
    then = turn(house.facade, rotation).centroid
    return (
        placement.origin[0] + float(now.x) - float(then.x),
        placement.origin[1] + float(now.y) - float(then.y),
    )


def suggest_placement(
    house: HouseType, ctx: SiteContext, boundary: BoundaryOptions, placement: Placement
) -> Placement | None:
    """Die zulässige Lage, die das Haus am wenigsten bewegt; die eigene Drehung zuerst. Geprüft wie jede Lage,
    damit der Vorschlag nie selbst einen Verstoß hat."""
    surfaces = placement_surfaces(house, ctx, boundary)
    ranked = sorted(surfaces, key=lambda r: (_gap_deg(r, placement.rotation_deg), r))
    best: tuple[float, Placement] | None = None
    for rotation in ranked:
        surface = surfaces[rotation]
        if surface.is_empty:
            continue
        target = _origin_keeping_centre(house, placement, rotation)
        spot = nearest_points(surface, Point(target))[0]
        candidate = Placement(
            origin=(round(float(spot.x), 3), round(float(spot.y), 3)), rotation_deg=rotation
        )
        if not check_placement(house, candidate, ctx, boundary).valid:
            continue
        moved = math.dist(candidate.origin, target)
        if best is None or moved < best[0] - 1e-9:
            best = (moved, candidate)
        if rotation == ranked[0]:
            break
    return best[1] if best else None


def evaluate_site(
    house: HouseType,
    placement: Placement | None,
    ctx: SiteContext,
    boundary: BoundaryOptions,
    materials: Sequence[MaterialSubject],
) -> SiteCheck:
    fit = evaluate_type(house, ctx, boundary)
    result = check_placement(house, placement, ctx, boundary) if placement else None
    facts = SiteFacts(has_garage_door=house.garage_door is not None, placed=result is not None)
    if placement is None or result is None:
        checks = [
            *fit.reasons,
            *fit.hints,
            *geometry_checks(ctx, facts),
            *rule_checks(ctx, None, None, facts, materials),
        ]
        return SiteCheck(None, None, checks, None, fit, None)
    areas = compute_areas(
        ctx, Buildings(house_facade=result.facade, house_projection=result.projection), result.part
    )
    checks = [
        *result.checks,
        *geometry_checks(ctx, facts),
        *rule_checks(ctx, result.part, areas, facts, materials),
    ]
    if not fit.allowed:
        # Mit dieser Auswahl gibt es keine zulässige Lage (Ergänzung 9); das steht neben den Verstößen
        checks.extend(c for c in fit.reasons if c.code == "no_valid_position")
    suggestion = None
    if result.blocking and fit.allowed:
        suggestion = suggest_placement(house, ctx, boundary, placement)
    centre = ctx.polygon.centroid
    where = orientation(
        house, placement.rotation_deg, (float(centre.x) + ctx.origin[0], float(centre.y) + ctx.origin[1])
    )
    return SiteCheck(result, areas, checks, where, fit, suggestion)
