"""Abbildung der Auswertung (Fachlogik) auf die Ausgaben der API (Plan H3 4.3). Ohne Datenbank.

Preise gehen brutto hinaus (Anzeigebasis, D10); intern wird netto gerechnet. Es gibt kein Feld, das als
Gesamtpreis lesbar ist (L1): nur Spannen und Einzelposten.
"""

from collections.abc import Sequence

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from app.catalog.domain.offer import OptionOffer, PackageOffer, TypeOffer
from app.configuration.domain.areas import Areas
from app.configuration.domain.checks import Check
from app.configuration.domain.costs import Costs, Range, gross_cents
from app.configuration.domain.design import Design
from app.configuration.domain.energy import EnergyStatus
from app.configuration.domain.geometry import polygons
from app.configuration.domain.options import Reason
from app.configuration.domain.orientation import Orientation
from app.configuration.domain.outbuildings import CarportPlacement, CarportSpec, Driveway, TerraceSpec
from app.configuration.domain.placement import Placement, PlacementResult
from app.configuration.schemas import (
    AreasOut,
    CheckOut,
    ComplianceOut,
    CostItemOut,
    CostsOut,
    DrivewayOut,
    EdgeMeasureOut,
    EnergyStatusOut,
    LocalPointModel,
    OptionChoiceOut,
    OptionState,
    OrientationOut,
    OutbuildingOut,
    OutbuildingsOut,
    PackageChoiceOut,
    PartAreasOut,
    PlacementEvaluationOut,
    PlacementOut,
    PriceOut,
    RangeOut,
    SelectionOut,
    SelectionReasonOut,
)
from app.envelope.schemas import CitationOut


def check_out(check: Check) -> CheckOut:
    citation = check.citation
    return CheckOut(
        code=check.code,
        kind=check.kind,
        status=check.status,
        binding=check.binding,
        measured=check.measured,
        limit=check.limit,
        unit=check.unit,
        edge_seq=check.edge_seq,
        zone_code=check.zone_code,
        reason=check.reason,
        params=check.params,
        citation=CitationOut(
            page=citation.page,
            quote=citation.quote,
            quote_verified=citation.quote_verified,
            source_url=citation.source_url,
            origin=citation.origin,
            confidence=citation.confidence,
            notes=citation.notes,
        )
        if citation
        else None,
    )


def reason_out(reason: Reason) -> SelectionReasonOut:
    return SelectionReasonOut(code=reason.code, slug=reason.slug, other=reason.other)


def _ring(geometry: BaseGeometry | None) -> list[list[float]] | None:
    parts = polygons(geometry)
    if not parts:
        return None
    polygon: Polygon = parts[0]
    return [[round(float(x), 3), round(float(y), 3)] for x, y, *_ in polygon.exterior.coords]


def placement_out(placement: Placement) -> PlacementOut:
    return PlacementOut(
        origin=LocalPointModel(e=round(placement.origin[0], 3), n=round(placement.origin[1], 3)),
        rotation_deg=placement.rotation_deg,
    )


def evaluation_out(result: PlacementResult) -> PlacementEvaluationOut:
    """Prüfung einer Lage je Kante mit den gelegten Umrissen (H2 und Hausmodell)."""
    return PlacementEvaluationOut(
        valid=result.valid,
        checks=[check_out(c) for c in result.checks],
        edges=[
            EdgeMeasureOut(
                seq=e.seq,
                kind=e.kind,
                measured_m=e.measured_m,
                required_m=e.required_m,
                contour=e.contour,
                status=e.status,
                on_boundary=e.on_boundary,
                on_boundary_allowed=e.on_boundary_allowed,
                markers=e.markers,
            )
            for e in result.edges
        ],
        facade_local=_ring(result.facade) or [],
        projection_local=_ring(result.projection) or [],
        zone_code=result.part.zone_code if result.part else None,
    )


def selection_out(design: Design, offer: TypeOffer, dropped: list[str]) -> SelectionOut:
    resolved = design.resolved
    return SelectionOut(
        package_slug=resolved.package.slug if resolved.package else None,
        package_version=resolved.package.version if resolved.package else None,
        option_slugs=[o.slug for o in resolved.explicit],
        included_slugs=sorted(resolved.included_slugs),
        invalid=[reason_out(r) for r in resolved.invalid],
        dropped=dropped,
    )


def outbuildings_out(design: Design) -> OutbuildingsOut:
    part = design.type_part
    return placed_outbuildings_out(
        part.terrace_spec, design.terrace, part.carport_spec, design.carport, design.driveways
    )


def placed_outbuildings_out(
    terrace_spec: TerraceSpec | None,
    terrace: BaseGeometry | None,
    carport_spec: CarportSpec | None,
    carport: CarportPlacement | None,
    driveways: Sequence[Driveway],
) -> OutbuildingsOut:
    """Terrasse, Carport und Zufahrten, wie `outbuildings.py` sie gesetzt hat (H3 und Hausmodell)."""
    terrace_out = None
    if terrace_spec is not None:
        terrace_out = OutbuildingOut(
            slug=terrace_spec.slug,
            kind="terrace",
            placed=terrace is not None,
            polygon_local=_ring(terrace),
            area_m2=terrace_spec.area_m2,
            width_m=terrace_spec.width_m,
            depth_m=terrace_spec.depth_m,
        )
    carport_out = None
    if carport_spec is not None:
        carport_out = OutbuildingOut(
            slug=carport_spec.slug,
            kind="carport",
            placed=carport is not None,
            polygon_local=_ring(carport.polygon) if carport else None,
            area_m2=carport_spec.area_m2,
            width_m=carport_spec.width_m,
            depth_m=carport_spec.depth_m,
            spaces=carport_spec.spaces,
            setback=carport.setback if carport else None,
        )
    return OutbuildingsOut(
        terrace=terrace_out,
        carport=carport_out,
        driveways=[
            DrivewayOut(
                source=d.source,
                polygon_local=_ring(d.polygon),
                length_m=d.length_m,
                area_m2=d.area_m2,
            )
            for d in driveways
        ],
    )


def areas_out(areas: Areas | None) -> AreasOut | None:
    if areas is None:
        return None
    return AreasOut(
        site_m2=areas.site_m2,
        house_m2=areas.house_m2,
        carport_m2=areas.carport_m2,
        terrace_m2=areas.terrace_m2,
        driveway_m2=areas.driveway_m2,
        paths_m2=areas.paths_m2,
        emprise_m2=areas.emprise_m2,
        sealed_m2=areas.sealed_m2,
        unsealed_m2=areas.unsealed_m2,
        parts=[
            PartAreasOut(
                zone_code=p.zone_code,
                area_m2=p.area_m2,
                emprise_m2=p.emprise_m2,
                sealed_m2=p.sealed_m2,
                unsealed_m2=p.unsealed_m2,
            )
            for p in areas.parts
        ],
    )


def compliance_out(checks: list[Check]) -> ComplianceOut:
    out = [check_out(c) for c in checks]
    return ComplianceOut(
        checks=out,
        fail=sum(1 for c in checks if c.status == "fail"),
        hint=sum(1 for c in checks if c.status == "hint"),
        unknown=sum(1 for c in checks if c.status == "unknown"),
        passed=sum(1 for c in checks if c.status == "pass"),
    )


def energy_out(energy: EnergyStatus, vat_rate: float) -> EnergyStatusOut:
    return EnergyStatusOut(
        status=energy.status,
        climate_zone=energy.climate_zone,
        verdict=energy.verdict,
        measures=energy.measures,
        surcharge_cents=gross_cents(energy.surcharge_cents, vat_rate) if energy.surcharge_cents else None,
    )


def costs_out(costs: Costs, offer: TypeOffer, type_name: str) -> CostsOut:
    def labels(slug: str | None, kind: str) -> tuple[str | None, str | None]:
        if kind == "base":
            return type_name, type_name
        if slug is None:
            return None, None
        found: PackageOffer | OptionOffer | None = (
            offer.package(slug) if kind == "package" else offer.option(slug)
        )
        return (found.label_de, found.label_fr) if found else (None, None)

    def rng(value: Range | None) -> RangeOut | None:
        return RangeOut(min_cents=value.min_cents, max_cents=value.max_cents) if value is not None else None

    items = []
    for item in costs.items:
        de, fr = labels(item.slug, item.kind)
        items.append(
            CostItemOut(
                code=item.code,
                kind=item.kind,
                slug=item.slug,
                label_de=de,
                label_fr=fr,
                min_cents=gross_cents(item.min_cents, costs.vat_rate),
                max_cents=gross_cents(item.max_cents, costs.vat_rate),
                included=item.included,
                quantity=item.quantity,
                unit=item.unit,
                unit_price_cents=gross_cents(item.unit_price_cents, costs.vat_rate)
                if item.unit_price_cents
                else None,
                source=item.source,
            )
        )
    return CostsOut(
        available=costs.available,
        reason=costs.reason,
        net=rng(costs.net),
        gross=rng(costs.gross),
        vat_rate=costs.vat_rate,
        display=rng(costs.display),
        catalog_version=costs.catalog_version,
        items=items,
    )


def orientation_out(orientation: Orientation | None) -> OrientationOut | None:
    if orientation is None:
        return None
    return OrientationOut(
        convergence_deg=orientation.convergence_deg,
        facades={role: round(azimuth, 1) for role, azimuth in orientation.facades.items()},
    )


def package_price(package: PackageOffer, vat_rate: float) -> PriceOut:
    cents = gross_cents(package.surcharge_cents or 0, vat_rate)
    return PriceOut(basis="fixed", min_cents=cents, max_cents=cents)


def option_price(option: OptionOffer, vat_rate: float, area_m2: float | None) -> PriceOut | None:
    if option.price_cents is None:
        return None
    unit = gross_cents(option.price_cents, vat_rate)
    if option.per_m2:
        total = round(unit * (area_m2 or 0.0))
        return PriceOut(
            basis="per_m2", min_cents=total, max_cents=total, unit_price_cents=unit, quantity=area_m2
        )
    return PriceOut(basis="fixed", min_cents=unit, max_cents=unit)


def option_choice(
    option: OptionOffer,
    state: OptionState,
    vat_rate: float,
    *,
    area_m2: float | None,
    reasons: list[Reason],
    checks: list[Check],
) -> OptionChoiceOut:
    return OptionChoiceOut(
        slug=option.slug,
        version=option.version,
        kind=option.kind,
        label_de=option.label_de,
        label_fr=option.label_fr,
        excludes=list(option.excludes),
        state=state,
        price=option_price(option, vat_rate, area_m2),
        reasons=[reason_out(r) for r in reasons],
        checks=[check_out(c) for c in checks],
        area_m2=area_m2,
    )


def package_choice(
    package: PackageOffer, vat_rate: float, energy: EnergyStatus, *, selected: bool
) -> PackageChoiceOut:
    return PackageChoiceOut(
        slug=package.slug,
        version=package.version,
        label_de=package.label_de,
        label_fr=package.label_fr,
        scope=list(package.scope),
        included_option_slugs=list(package.included),
        price=package_price(package, vat_rate),
        selected=selected,
        retired=package.status == "retired",
        energy=energy_out(energy, vat_rate),
    )
