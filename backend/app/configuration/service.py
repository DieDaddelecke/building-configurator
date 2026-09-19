"""Anwendungsfälle des Moduls H2 (Plan H2 4.3). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Grundstück, Regeln und Baurahmen kommen über `envelope.service.derived`, der Katalog über
`catalog.service`. Zulässigkeit und Prüfung der Lage entstehen bei jedem Abruf neu (Plan H2 3.8): Regeln,
Grundstück und Katalog ändern sich nach dem Speichern.
"""

import uuid
from dataclasses import dataclass

from shapely.geometry import Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import service as catalog_service
from app.catalog.service import PublishedType
from app.configuration.domain import ENGINE_VERSION
from app.configuration.domain import presets as preset_rules
from app.configuration.domain.checks import Check, type_checks
from app.configuration.domain.context import PartContext, SiteContext, build_context
from app.configuration.domain.fit import TypeFit, evaluate_type, with_suggestions
from app.configuration.domain.geometry import polygons
from app.configuration.domain.house import HouseType, make_polygon
from app.configuration.domain.placement import Placement, PlacementResult, check_placement
from app.configuration.domain.rotations import allowed_rotations, is_allowed_rotation
from app.configuration.domain.surface import BoundaryOptions, requirements, surface_by_rotation
from app.configuration.models import Configuration
from app.configuration.schemas import (
    CheckOut,
    ConfigurationOut,
    ConfigurationPatch,
    EdgeMeasureOut,
    LocalPointModel,
    PlacementAreaOut,
    PlacementEvaluationOut,
    PlacementOut,
    PresetsOut,
    RotationAreaOut,
    TypeFactsOut,
    TypeFitOut,
    TypeRefOut,
    TypesOut,
)
from app.envelope import service as envelope_service
from app.envelope.schemas import CitationOut
from app.platform.db import utcnow
from app.platform.problems import Problem

FEATURE_FLAG = "configurator"


# ---------------------------------------------------------------------------
# Eingaben
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Loaded:
    ctx: SiteContext
    notices: list[str]
    site_revision: int


def _load(db: Session, project_id: uuid.UUID) -> Loaded:
    data, envelope = envelope_service.derived(db, project_id)
    ctx = build_context(data, envelope)
    return Loaded(ctx=ctx, notices=list(dict.fromkeys(data.notices)), site_revision=data.site.revision)


def _house(published: PublishedType) -> HouseType:
    version = published.version
    return HouseType(
        slug=published.slug,
        version=version.version,
        version_id=str(version.id),
        name=version.name,
        facade=make_polygon(version.footprint_facade),
        projection=make_polygon(version.footprint_projection),
        storeys=version.storeys,
        roof_form=version.roof_form,
        ridge_height_m=version.ridge_height_m,
        eave_height_m=version.eave_height_m,
        living_area_m2=version.living_area_m2,
        pitch_deg=version.pitch_deg,
        ridge_direction=version.ridge_direction,
        facade_roles={int(k): role for k, role in version.facade_roles.items()},
        family=published.family,
        alternatives=tuple(published.alternatives),
    )


def _row(db: Session, project_id: uuid.UUID, *, lock: bool = False) -> Configuration | None:
    query = select(Configuration).where(Configuration.project_id == project_id)
    if lock:
        query = query.with_for_update()
    return db.execute(query).scalar_one_or_none()


def _options(row: Configuration | None) -> BoundaryOptions:
    if row is None:
        return {}
    return {int(k): bool(v) for k, v in row.boundary_options.items() if v}


def _placement(row: Configuration | None, ctx: SiteContext) -> Placement | None:
    if row is None or not row.placement:
        return None
    stored = row.placement
    return Placement(
        origin=(float(stored["origin_e"]) - ctx.origin[0], float(stored["origin_n"]) - ctx.origin[1]),
        rotation_deg=float(stored["rotation_deg"]),
    )


def _rotations(house: HouseType, ctx: SiteContext) -> list[float]:
    found: list[float] = []
    for part in ctx.parts:
        for rotation in allowed_rotations(house, part, ctx):
            if rotation not in found:
                found.append(rotation)
    return sorted(found)


def _eligible_parts(house: HouseType, ctx: SiteContext) -> list[PartContext]:
    """Teilflächen, in denen der Typ nicht schon aus anderem Grund als der Lage scheitert."""
    return [p for p in ctx.parts if not any(c.blocks for c in type_checks(house, p, ctx))]


# ---------------------------------------------------------------------------
# Ausgaben
# ---------------------------------------------------------------------------


def _check_out(check: Check) -> CheckOut:
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


def _ring(polygon: Polygon) -> list[list[float]]:
    return [[round(float(x), 3), round(float(y), 3)] for x, y, *_ in polygon.exterior.coords]


def _facts(published: PublishedType) -> TypeFactsOut:
    version = published.version
    min_x, min_y, max_x, max_y = make_polygon(version.footprint_facade).bounds
    return TypeFactsOut(
        storeys=version.storeys,
        roof_form=version.roof_form,
        pitch_deg=version.pitch_deg,
        ridge_direction=version.ridge_direction,
        ridge_height_m=version.ridge_height_m,
        eave_height_m=version.eave_height_m,
        footprint_m2=version.footprint_facade_area_m2,
        width_m=round(max_x - min_x, 2),
        depth_m=round(max_y - min_y, 2),
        living_area_m2=version.living_area_m2,
        rooms_text=version.rooms_text,
        base_price_min_cents=version.base_price_min_cents,
        base_price_max_cents=version.base_price_max_cents,
        facade_local=_ring(make_polygon(version.footprint_facade)),
        projection_local=_ring(make_polygon(version.footprint_projection)),
        facade_roles=dict(version.facade_roles),
        entrance=version.entrance,
    )


def _fit_out(fit: TypeFit, published: PublishedType) -> TypeFitOut:
    return TypeFitOut(
        slug=published.slug,
        version=published.version.version,
        name=published.version.name,
        family=published.family,
        allowed=fit.allowed,
        reasons=[_check_out(c) for c in fit.reasons],
        hints=[_check_out(c) for c in fit.hints],
        rotations=fit.rotations,
        suggestions=fit.suggestions,
        facts=_facts(published),
    )


def _evaluation_out(result: PlacementResult) -> PlacementEvaluationOut:
    def ring(geometry: object) -> list[list[float]]:
        parts = polygons(geometry)
        return _ring(parts[0]) if parts else []

    return PlacementEvaluationOut(
        valid=result.valid,
        checks=[_check_out(c) for c in result.checks],
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
        facade_local=ring(result.facade),
        projection_local=ring(result.projection),
        zone_code=result.part.zone_code if result.part else None,
    )


def _placement_out(placement: Placement) -> PlacementOut:
    return PlacementOut(
        origin=LocalPointModel(e=round(placement.origin[0], 3), n=round(placement.origin[1], 3)),
        rotation_deg=placement.rotation_deg,
    )


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def list_types(db: Session, project_id: uuid.UUID) -> TypesOut:
    """Veröffentlichte Typen mit Zulässigkeit, allen Gründen, Hinweisen und Vorschlägen (Spez. 5.4.6)."""
    loaded = _load(db, project_id)
    published = catalog_service.published_types(db)
    by_slug = {p.slug: p for p in published}
    fits = with_suggestions([evaluate_type(_house(p), loaded.ctx) for p in published])
    return TypesOut(
        mode=loaded.ctx.mode,
        free_reason=loaded.ctx.free_reason,
        notices=loaded.notices,
        site_revision=loaded.site_revision,
        types=[_fit_out(fit, by_slug[fit.house.slug]) for fit in fits],
    )


def get_configuration(db: Session, project_id: uuid.UUID) -> ConfigurationOut:
    row = _row(db, project_id)
    loaded = _load(db, project_id)
    ctx = loaded.ctx
    empty = ConfigurationOut(
        project_id=project_id,
        revision=row.revision if row else 0,
        engine_version=ENGINE_VERSION,
        mode=ctx.mode,
        free_reason=ctx.free_reason,
        type=None,
        placement=None,
        boundary_options={},
        rotations=[],
        fit=None,
        evaluation=None,
        notices=loaded.notices,
        updated_at=row.updated_at if row else None,
    )
    if row is None or row.building_type_version_id is None:
        return empty
    published = catalog_service.type_by_version_id(db, row.building_type_version_id)
    if published is None:
        return empty
    house = _house(published)
    options = _options(row)
    fit = evaluate_type(house, ctx, options)
    placement = _placement(row, ctx)
    evaluation = _evaluation_out(check_placement(house, placement, ctx, options)) if placement else None
    return empty.model_copy(
        update={
            "type": TypeRefOut(
                slug=published.slug,
                version=published.version.version,
                name=published.version.name,
                retired=published.version.status == "retired",
            ),
            "placement": _placement_out(placement) if placement else None,
            "boundary_options": {str(k): True for k in options},
            "rotations": _rotations(house, ctx),
            "fit": _fit_out(fit, published),
            "evaluation": evaluation,
        }
    )


def _chosen_type(
    db: Session, project_id: uuid.UUID, slug: str | None
) -> tuple[PublishedType, Configuration | None]:
    row = _row(db, project_id)
    published: PublishedType | None = None
    if slug is not None:
        published = next((p for p in catalog_service.published_types(db) if p.slug == slug), None)
        if published is None:
            raise Problem(404, "type_not_found")
    elif row is not None and row.building_type_version_id is not None:
        published = catalog_service.type_by_version_id(db, row.building_type_version_id)
    if published is None:
        raise Problem(409, "no_type_selected")
    return published, row


def placement_area(db: Session, project_id: uuid.UUID, type_slug: str | None) -> PlacementAreaOut:
    """Fläche zulässiger Ursprünge je erlaubter Drehung, für den Typ der Konfiguration oder `type_slug`."""
    published, row = _chosen_type(db, project_id, type_slug)
    ctx = _load(db, project_id).ctx
    house = _house(published)
    options = _options(row) if type_slug is None or _same_type(row, published) else {}
    parts = _eligible_parts(house, ctx)
    rotations = _rotations(house, ctx)
    # Der Browser rastet an der Fläche ein: mit den Abständen selbst, damit die Lage nicht 1 cm zu nah
    # liegt; passt das Haus nur mit der Toleranz von 0,01 m, gilt diese Fläche
    exact = surface_by_rotation(house, parts, rotations, ctx, options, exact=True)
    tolerant = surface_by_rotation(house, parts, rotations, ctx, options)
    surfaces = {r: (exact[r] if not exact[r].is_empty else tolerant[r]) for r in rotations}
    return PlacementAreaOut(
        type_slug=published.slug,
        rotations=[
            RotationAreaOut(
                rotation_deg=rotation,
                rings_local=[ring for poly in polygons(surfaces[rotation]) for ring in _rings(poly)],
                area_m2=round(float(surfaces[rotation].area), 2),
            )
            for rotation in rotations
        ],
    )


def _rings(polygon: Polygon) -> list[list[list[float]]]:
    return [
        [[round(float(x), 3), round(float(y), 3)] for x, y, *_ in ring.coords]
        for ring in (polygon.exterior, *polygon.interiors)
    ]


def _same_type(row: Configuration | None, published: PublishedType) -> bool:
    return row is not None and row.building_type_version_id == published.version.id


def presets(db: Session, project_id: uuid.UUID, type_slug: str | None) -> PresetsOut:
    """Schnellstellungen `street_near`, `set_back`, `garden_max` (Spez. 5.3.5)."""
    published, row = _chosen_type(db, project_id, type_slug)
    ctx = _load(db, project_id).ctx
    house = _house(published)
    options = _options(row) if _same_type(row, published) else {}
    computed = preset_rules.all_presets(house, ctx, options, _eligible_parts(house, ctx))
    return PresetsOut(
        type_slug=published.slug,
        presets={name: _placement_out(place) if place else None for name, place in computed.items()},
    )


# ---------------------------------------------------------------------------
# Ändern
# ---------------------------------------------------------------------------


def patch_configuration(
    db: Session,
    project_id: uuid.UUID,
    body: ConfigurationPatch,
    *,
    if_match: int | None,
    actor: str,
) -> ConfigurationOut:
    """Typ, Lage und Grenzschalter ändern. Gespeichert wird nie ein Typ, der gesperrt ist, und nie eine Lage
    mit bindendem Verstoß (D12); die Serverprüfung ist maßgeblich (L5)."""
    fields = body.model_fields_set
    row = _row(db, project_id, lock=True)
    current = row.revision if row else 0
    if if_match is not None and if_match != current:
        raise Problem(409, "revision_conflict", current_revision=current)
    if not fields:
        return get_configuration(db, project_id)

    ctx = _load(db, project_id).ctx
    published: PublishedType | None = None
    if row is not None and row.building_type_version_id is not None:
        published = catalog_service.type_by_version_id(db, row.building_type_version_id)
    options = _options(row)
    placement = _placement(row, ctx)

    new_type = False
    if "type_slug" in fields:
        if body.type_slug is None:
            published, placement, options = None, None, {}
        else:
            chosen = next((p for p in catalog_service.published_types(db) if p.slug == body.type_slug), None)
            if chosen is None:
                raise Problem(404, "type_not_found")
            if published is None or published.version.id != chosen.version.id:
                new_type, placement, options = True, None, {}
            published = chosen
    if "boundary_options" in fields:
        options = {seq: True for seq, on in (body.boundary_options or {}).items() if on}

    if published is None:
        if body.placement is not None:
            raise Problem(409, "no_type_selected")
        options = {}
    else:
        house = _house(published)
        _check_boundary_options(house, ctx, options)
        fit = evaluate_type(house, ctx, options)
        if not fit.allowed and (new_type or "boundary_options" in fields or "type_slug" in fields):
            raise Problem(422, "type_blocked", reasons=_dump(fit.reasons))
        if "placement" in fields:
            placement = _requested_placement(house, ctx, body)
        elif placement is None:
            placement = preset_rules.compute(house, ctx, "street_near", options, _eligible_parts(house, ctx))
        if placement is not None:
            result = check_placement(house, placement, ctx, options)
            if result.blocking:
                raise Problem(
                    422,
                    "placement_violation",
                    checks=_dump(result.checks),
                    edges=[e.model_dump(mode="json") for e in _evaluation_out(result).edges],
                )

    if row is None:
        row = Configuration(project_id=project_id, revision=1, created_by=actor)
        db.add(row)
    else:
        row.revision = row.revision + 1
    row.building_type_version_id = published.version.id if published else None
    row.placement = (
        {
            "origin_e": round(placement.origin[0] + ctx.origin[0], 3),
            "origin_n": round(placement.origin[1] + ctx.origin[1], 3),
            "rotation_deg": placement.rotation_deg,
        }
        if placement
        else None
    )
    row.boundary_options = {str(seq): True for seq in options}
    row.updated_at = utcnow()
    row.updated_by = actor
    db.commit()
    return get_configuration(db, project_id)


def _requested_placement(house: HouseType, ctx: SiteContext, body: ConfigurationPatch) -> Placement | None:
    if body.placement is None:
        return None
    allowed = _rotations(house, ctx)
    matched = is_allowed_rotation(body.placement.rotation_deg, allowed)
    if matched is None:
        raise Problem(422, "rotation_not_allowed", allowed=allowed)
    return Placement(origin=(body.placement.origin.e, body.placement.origin.n), rotation_deg=matched)


def _check_boundary_options(house: HouseType, ctx: SiteContext, options: BoundaryOptions) -> None:
    """Der Schalter gilt nur an Kanten, deren Regel Bauen auf der Grenze erlaubt (Plan H2 3.4)."""
    if not options:
        return
    permitted: set[int] = set()
    for part in ctx.parts:
        for seq, req in requirements(house, part, ctx, {}).items():
            if req.on_boundary_allowed:
                permitted.add(seq)
    invalid = sorted(seq for seq in options if seq not in permitted)
    if invalid:
        raise Problem(422, "boundary_not_allowed", edges=invalid)


def _dump(checks: list[Check]) -> list[dict[str, object]]:
    return [_check_out(c).model_dump(mode="json") for c in checks]
