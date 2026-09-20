"""Hilfen für die Tests des Moduls H2: Haustypen des Mockups und Kontext des Testgrundstücks."""

from typing import Any

from shapely.geometry import Polygon

from app.catalog.domain.offer import BasePrice, EnergyFinding, OptionOffer, PackageOffer, TypeOffer
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


# ---------------------------------------------------------------------------
# H3: Angebot des Katalogs (Linien, Optionen, Preise) als Datenklassen
# ---------------------------------------------------------------------------


def package_offer(
    slug: str,
    surcharge_eur: int | None = 0,
    *,
    included: tuple[str, ...] = (),
    regulatory: dict[str, str] | None = None,
    status: str = "published",
) -> PackageOffer:
    return PackageOffer(
        slug=slug,
        version_id=f"{slug}-v1",
        version=1,
        status=status,
        label_de=slug.capitalize(),
        label_fr=slug.capitalize(),
        included=included,
        regulatory=regulatory or {},
        surcharge_cents=None if surcharge_eur is None else surcharge_eur * 100,
    )


def option_offer(
    slug: str,
    price_eur: int | None = 1000,
    *,
    kind: str = "plain",
    params: dict[str, Any] | None = None,
    excludes: tuple[str, ...] = (),
    regulatory: dict[str, str] | None = None,
    status: str = "published",
) -> OptionOffer:
    defaults: dict[str, Any] = {}
    if kind == "terrace":
        defaults = {"depth_m": 3.0, "height_above_terrain_m": 0.3, "sealing_factor": 1.0}
    if kind == "carport":
        defaults = {"spaces": 1, "width_m": 3.0, "depth_m": 5.0, "height_m": 2.7}
    return OptionOffer(
        slug=slug,
        version_id=f"{slug}-v1",
        version=1,
        status=status,
        kind=kind,
        label_de=slug,
        label_fr=slug,
        params={**defaults, **(params or {})},
        regulatory=regulatory or {},
        excludes=excludes,
        price_cents=None if price_eur is None else price_eur * 100,
    )


def type_offer(
    packages: tuple[PackageOffer, ...] = (),
    options: tuple[OptionOffer, ...] = (),
    *,
    energy: tuple[EnergyFinding, ...] = (),
    base_eur: tuple[int, int] | None = (328_000, 362_000),
    vat_rate: float = 0.0,
    catalog: bool = True,
) -> TypeOffer:
    """Angebot wie in der Parität des Mockups (Spez. 11.2): Ligne 328.000 – 362.000 €, ohne Mehrwertsteuer."""
    return TypeOffer(
        catalog_version_id="catalog-v1" if catalog else None,
        catalog_version=1 if catalog else None,
        vat_rate=vat_rate,
        base=BasePrice(base_eur[0] * 100, base_eur[1] * 100, "catalog") if base_eur else None,
        packages=packages,
        options=options,
        energy=energy,
    )


def mockup_offer(vat_rate: float = 0.0) -> TypeOffer:
    """Linien und Optionen des Mockups mit ihren Aufpreisen (`Hauskonfigurator.jsx`), RE2020 nur für Base."""
    return type_offer(
        packages=(
            package_offer("base", 0),
            package_offer("confort", 34_000, included=("ziegel_dach",)),
            package_offer(
                "signature",
                71_000,
                included=("holz_sued", "holz_voll", "ziegel_dach", "fenster_sued", "pv"),
            ),
        ),
        options=(
            option_offer("holz_sued", 12_400, excludes=("holz_voll",)),
            option_offer("holz_voll", 28_900, excludes=("holz_sued",)),
            option_offer("ziegel_eg", 19_700),
            option_offer("ziegel_dach", 4_200),
            option_offer("fenster_sued", 8_600),
            option_offer("pv", 11_200),
            option_offer("terrasse", 9_800),
            option_offer("keller", 47_000),
        ),
        energy=(
            EnergyFinding("base", "H2b", "Bbio knapp verfehlt", False, 950_000, "Dämmung und Lüftung"),
            EnergyFinding("confort", "H2b", "erfüllt", True),
        ),
        vat_rate=vat_rate,
    )
