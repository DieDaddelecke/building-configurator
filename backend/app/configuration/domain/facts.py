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
from app.configuration.domain.house import HouseType, longest_role_edge, ridge_axis_model_deg
from app.configuration.domain.outbuildings import CarportSpec, TerraceSpec
from app.house.contract import HouseFacts, HousePoint

PLU_ROOF_FORMS: dict[str, tuple[str, ...]] = {
    "flat": ("flat",),
    "mono_pitch": ("mono_pitch",),
    "gable": ("gable",),
    "hip": ("hip",),
    "mansard": ("mansard",),
    "mansard_gable": ("mansard",),
    "half_hip": ("gable", "hip", "other"),
}
"""Dachform des Kerns → Begriffe der PLU-Regeln (Ergänzung 11, E-HM-61). Mehrere Begriffe: Der PLU benennt die
Form nicht eindeutig; die Prüfung entscheidet dann nur, wenn alle Lesarten gleich ausgehen."""


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


def _ridge_direction(house: HouseType, azimuth_deg: float) -> str:
    """`laengs` oder `quer` so, dass `ridge_axis_model_deg` die Firstachse der Hausbeschreibung ergibt; bei
    quadratischem Umriss entscheidet so die Achse, nicht die Benennung."""
    along = ridge_axis_model_deg(replace(house, ridge_direction="laengs"))
    if along is not None and angle_between_axes(along, azimuth_deg) <= 45.0:
        return "laengs"
    return "quer"


def house_type(facts: HouseFacts, *, slug: str, version: int, version_id: str, name: str) -> HouseType:
    """`HouseType` aus der Hausbeschreibung; `FactsError`, wenn die Umrisse nicht dem Vertrag entsprechen."""
    offset = facts.ground_floor_offset
    forms = PLU_ROOF_FORMS[facts.roof_shape]
    pitch = _pitch(facts.roof_slopes_deg)
    house = HouseType(
        slug=slug,
        version=version,
        version_id=version_id,
        name=name,
        facade=_polygon(facts.facade_outline),
        projection=_polygon(facts.projection_outline),
        storeys=storeys_text(facts.storeys),
        roof_form=forms[0] if len(forms) == 1 else facts.roof_shape,
        ridge_height_m=round(facts.top_height + offset, 3),
        eave_height_m=round(facts.eave_height + offset, 3),
        living_area_m2=round(facts.floor_area, 2),
        pitch_deg=pitch,
        roof_form_readings=forms if len(forms) > 1 else (),
        roof_pitches_deg=()
        if pitch is not None
        else tuple(sorted({round(s, 2) for s in facts.roof_slopes_deg})),
        facade_roles={role.edge: role.role for role in facts.facade_roles},
        garage_door=(facts.garage_door.edge, facts.garage_door.position) if facts.garage_door else None,
    )
    if facts.roof_shape == "flat" or facts.ridge_azimuth_deg is None:
        return house
    return replace(house, ridge_direction=_ridge_direction(house, facts.ridge_azimuth_deg))


def outbuilding_specs(facts: HouseFacts, house: HouseType) -> tuple[TerraceSpec | None, CarportSpec | None]:
    """Terrasse und Carport aus den Slots `site` (Ergänzung 7): Maße rechnet der Kern, Lage, Zufahrt und
    Prüfungen bleiben in Python (`outbuildings.py`). Die Terrasse liegt an der längsten Gartenkante."""
    terrace = None
    if facts.terrace is not None:
        found = longest_role_edge(house, "garden") if facts.terrace.width else None
        terrace = TerraceSpec(
            slug=facts.terrace.type_id,
            depth_m=facts.terrace.depth,
            height_above_terrain_m=facts.terrace.height_above_terrain,
            sealing_factor=facts.terrace.sealing_factor,
            width_m=round(facts.terrace.width, 3) if found and facts.terrace.width else None,
            edge=(found[1], found[2]) if found else None,
        )
    carport = None
    if facts.carport is not None:
        carport = CarportSpec(
            slug=facts.carport.type_id,
            spaces=facts.carport.spaces,
            width_m=facts.carport.width,
            depth_m=facts.carport.depth,
            height_m=facts.carport.height,
        )
    return terrace, carport
