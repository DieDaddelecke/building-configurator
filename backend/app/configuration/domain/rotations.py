"""Erlaubte Drehungen (Plan H2 3.2): vier Ausrichtungen zur Straße, gefiltert nach der Firstrichtung.

Bezug ist der Azimut, in den die Straßenfassade zeigen soll (`SiteContext.reference_normal_deg`). Hat der Typ
keine Fassade mit der Rolle `street`, gilt Modellnorden als Straßenseite und die Ausrichtung heißt nur „zur
Kante“; die Prüfung meldet das als Hinweis.
"""

from app.configuration.domain import tolerances as tol
from app.configuration.domain.context import PartContext, SiteContext
from app.configuration.domain.geometry import angle_between_axes, normalize_deg
from app.configuration.domain.house import HouseType, ridge_axis_model_deg, street_normal_model_deg
from app.envelope.domain.setbacks import rule_for


def base_rotation_deg(house: HouseType, ctx: SiteContext) -> float:
    """Drehung, bei der die Straßenfassade des Typs zur Straße zeigt."""
    model = street_normal_model_deg(house)
    return normalize_deg(ctx.reference_normal_deg - (model if model is not None else 0.0))


def candidate_rotations(house: HouseType, ctx: SiteContext) -> list[float]:
    """Vier Drehungen, die straßenzugewandte zuerst."""
    base = base_rotation_deg(house, ctx)
    return [normalize_deg(base + 90.0 * k) for k in range(4)]


def ridge_orientation_rule(part: PartContext) -> str:
    """Vorgabe der Zone: `any`, `parallel_to_street` oder `perpendicular_to_street`; nur, wenn wirksam."""
    rule = rule_for(part.rules, "roof")
    if rule is None or rule.status != "effective":
        return "any"
    return str(rule.params.get("ridge_orientation", "any"))


def ridge_deviation_deg(
    house: HouseType, rotation_deg: float, ctx: SiteContext, orientation: str
) -> float | None:
    """Abweichung des Firsts von der Vorgabe in Grad, oder `None`, wenn es nichts zu prüfen gibt."""
    axis = ridge_axis_model_deg(house)
    if axis is None or orientation == "any" or not ctx.has_street:
        return None
    ridge_world = (axis + rotation_deg) % 180.0
    angle = angle_between_axes(ridge_world, ctx.street_tangent_deg)
    return angle if orientation == "parallel_to_street" else abs(90.0 - angle)


def ridge_allows(house: HouseType, rotation_deg: float, ctx: SiteContext, orientation: str) -> bool:
    deviation = ridge_deviation_deg(house, rotation_deg, ctx, orientation)
    return deviation is None or deviation <= tol.RIDGE_TOLERANCE_DEG


def allowed_rotations(house: HouseType, part: PartContext, ctx: SiteContext) -> list[float]:
    orientation = ridge_orientation_rule(part)
    return [r for r in candidate_rotations(house, ctx) if ridge_allows(house, r, ctx, orientation)]


def is_allowed_rotation(rotation_deg: float, rotations: list[float]) -> float | None:
    """Die erlaubte Drehung, die der übermittelten entspricht (Toleranz 0,05°), sonst `None`."""
    for candidate in rotations:
        diff = abs(rotation_deg - candidate) % 360.0
        if min(diff, 360.0 - diff) <= tol.ROTATION_TOLERANCE_DEG:
            return candidate
    return None


def site_rotations(house: HouseType, ctx: SiteContext) -> list[float]:
    """Erlaubte Drehungen über alle Teilflächen des Grundstücks, aufsteigend."""
    found: list[float] = []
    for part in ctx.parts:
        for rotation in allowed_rotations(house, part, ctx):
            if rotation not in found:
                found.append(rotation)
    return sorted(found)
