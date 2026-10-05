"""Hausbeschreibung des Rechenkerns als Haustyp der Prüfung (docs/PLAN_HAUSMODELL.md 3.1, E-HM-4; HM4).

Lage, Fläche zulässiger Ursprünge, Schnellstellungen, Zulässigkeit und PLU-Prüfung arbeiten weiter mit
`HouseType`; diese Abbildung ersetzt den Typ aus dem H1-Katalog. Höhen gelten über dem Gelände: Höhe über
±0,00 plus Erdgeschoss über Gelände (E-HM-11). Die Umrisse kommen gegen den Uhrzeigersinn (Vertrag), sonst
stimmten die Kantennummern der Fassadenrollen nicht.
"""

from collections.abc import Sequence
from dataclasses import replace

from shapely.geometry import Polygon

from app.configuration.domain import tolerances as tol
from app.configuration.domain.geometry import angle_between_axes
from app.configuration.domain.house import HouseType, ridge_axis_model_deg
from app.house.contract import HouseFacts, HousePoint

RIDGE_AXIS_DEG = {"x": 90.0, "y": 0.0}
"""Firstrichtung der Hausbeschreibung als Azimut der Achse im Modell (Y = Modellnord)."""


class FactsError(ValueError):
    """Die Hausbeschreibung verletzt den Vertrag (Umriss ungültig oder im Uhrzeigersinn)."""


def _polygon(points: Sequence[HousePoint]) -> Polygon:
    polygon = Polygon([(p.x, p.y) for p in points])
    if not polygon.is_valid or polygon.area <= 0 or not polygon.exterior.is_ccw:
        raise FactsError("outline_invalid")
    return polygon


def storeys_text(storeys: int) -> str:
    """Geschosszahl in der Schreibweise der PLU-Regeln: 1 → `R`, 2 → `R+1`."""
    return "R" if storeys <= 1 else f"R+{storeys - 1}"


def _pitch(slopes: Sequence[float]) -> float | None:
    """Eine Neigung für die Prüfung, wenn alle Dachflächen gleich geneigt sind. Bei verschiedenen Neigungen
    (Mansarde, Mischformen) bleibt sie offen: Welche gilt, legt die Auslegung fest (Ergänzung 11)."""
    if not slopes or max(slopes) - min(slopes) > tol.PITCH_TOLERANCE_DEG:
        return None
    return round(sum(slopes) / len(slopes), 2)


def _ridge_direction(house: HouseType, axis: str) -> str:
    """`laengs` oder `quer` so, dass `ridge_axis_model_deg` die Firstachse der Hausbeschreibung ergibt; bei
    quadratischem Umriss entscheidet so die Achse, nicht die Benennung."""
    along = ridge_axis_model_deg(replace(house, ridge_direction="laengs"))
    if along is not None and angle_between_axes(along, RIDGE_AXIS_DEG[axis]) <= 45.0:
        return "laengs"
    return "quer"


def house_type(facts: HouseFacts, *, slug: str, version: int, version_id: str, name: str) -> HouseType:
    """`HouseType` aus der Hausbeschreibung; `FactsError`, wenn die Umrisse nicht dem Vertrag entsprechen."""
    offset = facts.ground_floor_offset
    house = HouseType(
        slug=slug,
        version=version,
        version_id=version_id,
        name=name,
        facade=_polygon(facts.facade_outline),
        projection=_polygon(facts.projection_outline),
        storeys=storeys_text(facts.storeys),
        roof_form=facts.roof_form,
        ridge_height_m=round(facts.top_height + offset, 3),
        eave_height_m=round(facts.eave_height + offset, 3),
        living_area_m2=round(facts.floor_area, 2),
        pitch_deg=_pitch(facts.roof_slopes_deg),
        facade_roles={role.edge: role.role for role in facts.facade_roles},
        garage_door=(facts.garage_door.edge, facts.garage_door.position) if facts.garage_door else None,
    )
    if facts.roof_form == "flat" or facts.ridge_direction is None:
        return house
    return replace(house, ridge_direction=_ridge_direction(house, facts.ridge_direction))
