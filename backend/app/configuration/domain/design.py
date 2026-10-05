"""`evaluate_design`: Auswertung von Linie, Optionen und Nebenbauten (Plan H3 3.11, 4.1; Spez. 5.5.3).

Zwei getrennte reine Funktionen: der **Typteil** (`type_part`: Auswahl, Energie, Kosten, Maße der Nebenbauten)
hängt nur von Typ, Linie und Optionen ab, der **Lageteil** (`site_part`: Geometrie, Flächen, Prüfungen,
Himmelsrichtung) von der Lage. Beide ohne Datenbank; der Katalog kommt als `TypeOffer`.
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from app.catalog.domain.offer import TypeOffer
from app.configuration.domain.areas import Areas, Buildings, compute_areas
from app.configuration.domain.checks import Check
from app.configuration.domain.compliance import SiteFacts, geometry_checks, material_subjects, rule_checks
from app.configuration.domain.context import SiteContext
from app.configuration.domain.costs import Costs, compute_costs
from app.configuration.domain.energy import EnergyStatus, energy_status
from app.configuration.domain.geometry import union
from app.configuration.domain.house import HouseType
from app.configuration.domain.options import Resolved, Selection, resolve
from app.configuration.domain.orientation import Orientation, orientation
from app.configuration.domain.outbuildings import (
    CarportPlacement,
    CarportSpec,
    Driveway,
    TerraceSpec,
    carport_driveway,
    carport_spec,
    garage_driveway,
    place_carport,
    street_reference,
    terrace_polygon,
    terrace_spec,
)
from app.configuration.domain.placement import Placement, PlacementResult


@dataclass(frozen=True)
class TypePart:
    resolved: Resolved
    energy: EnergyStatus
    costs: Costs
    terrace_spec: TerraceSpec | None
    carport_spec: CarportSpec | None


@dataclass(frozen=True)
class Design:
    type_part: TypePart
    terrace: BaseGeometry | None
    carport: CarportPlacement | None
    driveways: tuple[Driveway, ...]
    areas: Areas | None
    checks: list[Check]
    orientation: Orientation | None

    @property
    def resolved(self) -> Resolved:
        return self.type_part.resolved

    @property
    def blocking(self) -> list[Check]:
        return [c for c in self.checks if c.blocks]


def type_part(house: HouseType, offer: TypeOffer, selection: Selection) -> TypePart:
    """Auswahl prüfen, Energie und Kosten rechnen. Die Terrassenfläche hängt nur vom Typ ab (Plan H3 3.8)."""
    resolved = resolve(offer, selection)
    effective = resolved.effective
    terrace_option = next((o for o in effective if o.kind == "terrace"), None)
    carport_option = next((o for o in effective if o.kind == "carport"), None)
    terrace = terrace_spec(terrace_option, house) if terrace_option else None
    carport = carport_spec(carport_option) if carport_option else None
    energy = energy_status(offer.finding(resolved.package.slug if resolved.package else None))
    areas = {terrace.slug: terrace.area_m2} if terrace else {}
    return TypePart(resolved, energy, compute_costs(offer, resolved, energy, areas), terrace, carport)


def site_part(
    house: HouseType,
    placement: Placement | None,
    ctx: SiteContext,
    house_result: PlacementResult | None,
    part: TypePart,
) -> Design:
    """Geometrie der Nebenbauten, Flächen, Prüfungen und Himmelsrichtung für eine Lage."""
    has_door = house.garage_door is not None
    if placement is None or house_result is None:
        facts = SiteFacts(
            terrace_spec=part.terrace_spec,
            carport_spec=part.carport_spec,
            has_garage_door=has_door,
            placed=False,
        )
        materials = material_subjects(part.resolved)
        checks = [*geometry_checks(ctx, facts), *rule_checks(ctx, None, None, facts, materials)]
        return Design(part, None, None, (), None, checks, None)

    terrace = terrace_polygon(part.terrace_spec, placement) if part.terrace_spec else None
    # Haus und Terrasse sind Hindernisse: kein Überlapp mit dem Carport, seine Zufahrt kreuzt sie nicht
    obstacle = union([g for g in (house_result.projection, terrace) if g is not None])
    carport = place_carport(part.carport_spec, ctx, obstacle) if part.carport_spec else None
    street = street_reference(ctx)
    drives: list[Driveway] = []
    if street is not None:
        if carport is not None:
            drives.append(carport_driveway(carport, street))
        garage = garage_driveway(house, placement, street)
        if garage is not None:
            drives.append(garage)
    spec = part.terrace_spec
    buildings = Buildings(
        house_facade=house_result.facade,
        house_projection=house_result.projection,
        carport=carport.polygon if carport else None,
        terrace=terrace,
        terrace_height_m=spec.height_above_terrain_m if spec else 0.0,
        terrace_sealing_factor=spec.sealing_factor if spec else 1.0,
        driveways=tuple(d.polygon for d in drives),
    )
    areas = compute_areas(ctx, buildings, house_result.part)
    facts = SiteFacts(
        terrace_spec=part.terrace_spec,
        terrace=terrace,
        carport_spec=part.carport_spec,
        carport=carport,
        has_garage_door=has_door,
        placed=True,
    )
    checks = [
        *geometry_checks(ctx, facts),
        *rule_checks(ctx, house_result.part, areas, facts, material_subjects(part.resolved)),
    ]
    centre = ctx.polygon.centroid
    where = orientation(
        house, placement.rotation_deg, (float(centre.x) + ctx.origin[0], float(centre.y) + ctx.origin[1])
    )
    return Design(part, terrace, carport, tuple(drives), areas, checks, where)


def evaluate_design(
    house: HouseType,
    placement: Placement | None,
    ctx: SiteContext,
    house_result: PlacementResult | None,
    offer: TypeOffer,
    selection: Selection,
) -> Design:
    return site_part(house, placement, ctx, house_result, type_part(house, offer, selection))
