"""Hilfen für die Tests des Moduls H2: Haustypen des Mockups und Kontext des Testgrundstücks."""

from typing import Any

from shapely.geometry import Polygon

from app.configuration.domain.context import SiteContext, build_context
from app.configuration.domain.house import HouseType
from app.envelope.domain.derive import derive_envelope
from app.envelope.domain.inputs import EnvelopeInput
from tests.envelope_support import envelope_input, rule, site, ub_rules, zone


def box(width: float, depth: float, overhang: float = 0.0) -> Polygon:
    return Polygon(
        [
            (-overhang, -overhang),
            (width + overhang, -overhang),
            (width + overhang, depth + overhang),
            (-overhang, depth + overhang),
        ]
    )


def house(
    slug: str = "ligne",
    *,
    width: float = 12.0,
    depth: float = 8.0,
    overhang: float = 0.0,
    roof_form: str = "gable",
    pitch_deg: float | None = 40.0,
    ridge_direction: str | None = "laengs",
    ridge_height_m: float = 8.4,
    eave_height_m: float = 5.6,
    storeys: str = "R+1",
    living_area_m2: float = 158.0,
    roles: bool = True,
    family: str | None = None,
    alternatives: tuple[str, ...] = (),
) -> HouseType:
    """Rechteckhaus mit Straßenfassade im Norden des Modells (Kante 2: von rechts oben nach links oben)."""
    from app.configuration.domain.house import make_polygon

    facade = make_polygon(list(box(width, depth).exterior.coords)[:-1])
    projection = make_polygon(list(box(width, depth, overhang).exterior.coords)[:-1])
    return HouseType(
        slug=slug,
        version=1,
        version_id=f"{slug}-v1",
        name=slug.capitalize(),
        facade=facade,
        projection=projection,
        storeys=storeys,
        roof_form=roof_form,
        ridge_height_m=ridge_height_m,
        eave_height_m=eave_height_m,
        living_area_m2=living_area_m2,
        pitch_deg=pitch_deg,
        ridge_direction=ridge_direction,
        facade_roles={0: "garden", 1: "side_right", 2: "street", 3: "side_left"} if roles else {},
        family=family,
        alternatives=alternatives,
    )


def ligne() -> HouseType:
    return house("ligne")


def plateau() -> HouseType:
    return house(
        "plateau",
        width=16.5,
        roof_form="flat",
        pitch_deg=None,
        ridge_direction=None,
        ridge_height_m=6.8,
        eave_height_m=6.8,
        storeys="R+1",
        living_area_m2=141.0,
        family="plateau",
        alternatives=("plateau_adapte",),
    )


def plateau_adapte() -> HouseType:
    return house(
        "plateau_adapte",
        width=13.5,
        pitch_deg=38.0,
        ridge_height_m=8.1,
        eave_height_m=5.5,
        living_area_m2=132.0,
        family="plateau",
    )


def context(rules: list[Any] | None = None, **envelope_kwargs: Any) -> SiteContext:
    data, envelope = _derive(rules, **envelope_kwargs)
    return build_context(data, envelope)


def _derive(rules: list[Any] | None = None, **envelope_kwargs: Any) -> tuple[EnvelopeInput, Any]:
    site_input = envelope_kwargs.pop("site_input", site())
    zones = envelope_kwargs.pop("zones", [zone(rules=rules if rules is not None else ub_rules())])
    data = envelope_input(site_input=site_input, zones=zones, **envelope_kwargs)
    return data, derive_envelope(data)


def ub_with(**overrides: dict[str, Any]) -> list[Any]:
    """Regeln der Zone UB, einzelne Arten durch andere Parameter ersetzt."""
    result = []
    for base in ub_rules():
        if base.kind in overrides:
            result.append(rule(base.kind, overrides[base.kind]))
        else:
            result.append(base)
    return result
