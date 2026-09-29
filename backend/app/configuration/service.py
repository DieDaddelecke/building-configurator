"""Anwendungsfälle des Moduls H2 (Plan H2 4.3). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Grundstück, Regeln und Baurahmen kommen über `envelope.service.derived`, der Katalog über
`catalog.service`. Zulässigkeit und Prüfung der Lage entstehen bei jedem Abruf neu (Plan H2 3.8): Regeln,
Grundstück und Katalog ändern sich nach dem Speichern.
"""

import uuid
from dataclasses import dataclass, replace
from typing import Any

from shapely.geometry import Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import service as catalog_service
from app.catalog.domain.offer import OptionOffer, TypeOffer
from app.catalog.service import PublishedType
from app.configuration import outputs, review
from app.configuration.domain import ENGINE_VERSION
from app.configuration.domain import presets as preset_rules
from app.configuration.domain.checks import Check, type_checks
from app.configuration.domain.context import PartContext, SiteContext, build_context
from app.configuration.domain.design import Design, evaluate_design
from app.configuration.domain.energy import energy_status
from app.configuration.domain.fit import TypeFit, evaluate_type, with_suggestions
from app.configuration.domain.geometry import polygons
from app.configuration.domain.house import HouseType, make_polygon
from app.configuration.domain.options import Reason, Selection, resolve
from app.configuration.domain.outbuildings import carport_spec, terrace_spec
from app.configuration.domain.placement import Placement, PlacementResult, check_placement
from app.configuration.domain.rotations import allowed_rotations, is_allowed_rotation
from app.configuration.domain.surface import BoundaryOptions, requirements, surface_by_rotation
from app.configuration.models import Configuration
from app.configuration.outputs import check_out as _check_out
from app.configuration.schemas import (
    ConfigurationOut,
    ConfigurationPatch,
    EdgeMeasureOut,
    LocalPointModel,
    OptionChoiceOut,
    OptionsOut,
    OptionState,
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
from app.envelope.domain import ENGINE_VERSION as ENVELOPE_ENGINE_VERSION
from app.platform.db import utcnow
from app.platform.problems import Problem
from app.site.domain.local import rings as local_rings

FEATURE_FLAG = "configurator"


# ---------------------------------------------------------------------------
# Eingaben
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Loaded:
    ctx: SiteContext
    notices: list[str]
    site_revision: int
    input_parts: dict[str, str]
    """Prüfsumme von Grundstück und Regeln in zwei Teilen (Prüfstempel, V 3.3)."""


def _load(db: Session, project_id: uuid.UUID) -> Loaded:
    data, envelope = envelope_service.derived(db, project_id)
    ctx = build_context(data, envelope)
    return Loaded(
        ctx=ctx,
        notices=list(dict.fromkeys(data.notices)),
        site_revision=data.site.revision,
        input_parts=envelope_service.fingerprint_parts(data),
    )


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
        garage_door=_garage_door(version.garage_door),
    )


def _garage_door(raw: dict[str, Any] | None) -> tuple[int, float] | None:
    """`{edge, position}` aus der Katalogpflege (ANNAHMEN H10); alles andere gilt als „kein Garagentor“."""
    if not isinstance(raw, dict):
        return None
    edge, position = raw.get("edge"), raw.get("position")
    if isinstance(edge, int) and not isinstance(edge, bool) and isinstance(position, int | float):
        return edge, float(position)
    return None


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
# Auswahl und Auswertung (H3)
# ---------------------------------------------------------------------------


def _stored_ids(row: Configuration | None) -> tuple[uuid.UUID | None, list[uuid.UUID]]:
    """Gespeicherte Versionen von Linie und Optionen (L4)."""
    if row is None:
        return None, []
    return row.package_version_id, [uuid.UUID(str(m["module_version_id"])) for m in row.modules]


def _offer(db: Session, published: PublishedType, row: Configuration | None) -> TypeOffer:
    """Angebot des Katalogs für den Typ; gespeicherte Versionen behalten ihren Stand."""
    package_id, module_ids = _stored_ids(row)
    return catalog_service.offer_for_type(
        db, published, package_version_id=package_id, module_version_ids=module_ids
    )


def _selection(offer: TypeOffer, row: Configuration | None) -> Selection:
    package_id, module_ids = _stored_ids(row)
    package = next((p.slug for p in offer.packages if p.version_id == str(package_id)), None)
    by_version = {o.version_id: o.slug for o in offer.options}
    # In der gespeicherten Reihenfolge: Bei einem Ausschluss trägt die zuletzt gewählte Option den Grund
    return Selection(package, tuple(by_version[str(i)] for i in module_ids if str(i) in by_version))


def _selection_ids(offer: TypeOffer, selection: Selection) -> tuple[uuid.UUID | None, list[dict[str, str]]]:
    """Versions-IDs zum Speichern; eine noch gespeicherte, inzwischen nicht mehr angebotene Wahl bleibt."""
    package = offer.package(selection.package_slug)
    modules = [o for o in (offer.option(s) for s in selection.option_slugs) if o is not None]
    return (
        uuid.UUID(package.version_id) if package else None,
        [{"module_version_id": o.version_id} for o in modules],
    )


def _evaluate(
    house: HouseType,
    placement: Placement | None,
    boundary: BoundaryOptions,
    ctx: SiteContext,
    offer: TypeOffer,
    selection: Selection,
) -> tuple[PlacementResult | None, Design]:
    result = check_placement(house, placement, ctx, boundary) if placement else None
    return result, evaluate_design(house, placement, ctx, result, offer, selection)


def _key(check: Check) -> tuple[str, str | None, int | None, str | None]:
    subject = check.params.get("subject")
    return check.code, check.zone_code, check.edge_seq, str(subject) if subject is not None else None


def _new_blockers(
    design: Design, allowed: set[tuple[str, str | None, int | None, str | None]]
) -> list[Check]:
    return [c for c in design.blocking if _key(c) not in allowed]


def _design_fields(design: Design, offer: TypeOffer, house: HouseType, dropped: list[str]) -> dict[str, Any]:
    return {
        "selection": outputs.selection_out(design, offer, dropped),
        "outbuildings": outputs.outbuildings_out(design),
        "areas": outputs.areas_out(design.areas),
        "compliance": outputs.compliance_out(design.checks),
        "energy": outputs.energy_out(design.type_part.energy, offer.vat_rate),
        "costs": outputs.costs_out(design.type_part.costs, offer, house.name),
        "orientation": outputs.orientation_out(design.orientation),
    }


# ---------------------------------------------------------------------------
# Ausgaben
# ---------------------------------------------------------------------------


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


def get_configuration(
    db: Session, project_id: uuid.UUID, *, dropped: list[str] | None = None
) -> ConfigurationOut:
    return _configuration(db, project_id, dropped=dropped).out


@dataclass(frozen=True)
class DesignReview:
    """Neu gerechnete Konfiguration für die Übergabe (V 3.2) mit dem, was der Snapshot vom Katalog braucht."""

    out: ConfigurationOut
    catalog: dict[str, Any]
    """Kopien der benutzten Katalogstände (V 3.6); leer ohne Typ."""
    lines_offered: bool
    """Ob der Katalog für den Typ Linien anbietet (dann ist eine Linie Pflicht, V 3.2)."""


def design_review(db: Session, project_id: uuid.UUID) -> DesignReview:
    return _configuration(db, project_id)


def _catalog_copy(published: PublishedType, offer: TypeOffer, selection: Selection) -> dict[str, Any]:
    package = offer.package(selection.package_slug)
    included = set(package.included) if package else set()
    options = [o for o in offer.options if o.slug in selection.option_slugs or o.slug in included]
    return {
        "type": {
            "slug": published.slug,
            "version": published.version.version,
            "version_id": str(published.version.id),
            "status": published.version.status,
            "name": published.version.name,
            "family": published.family,
        },
        "package": (
            {
                "slug": package.slug,
                "version": package.version,
                "status": package.status,
                "label_de": package.label_de,
                "label_fr": package.label_fr,
                "scope": list(package.scope),
                "included": list(package.included),
                "regulatory": dict(package.regulatory),
            }
            if package
            else None
        ),
        "options": [
            {
                "slug": o.slug,
                "version": o.version,
                "status": o.status,
                "kind": o.kind,
                "label_de": o.label_de,
                "label_fr": o.label_fr,
                "params": dict(o.params),
                "regulatory": dict(o.regulatory),
                "included": o.slug in included,
            }
            for o in options
        ],
        "price_catalog": {"version": offer.catalog_version, "vat_rate": offer.vat_rate},
    }


def _configuration(db: Session, project_id: uuid.UUID, *, dropped: list[str] | None = None) -> DesignReview:
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
        selection=None,
        outbuildings=None,
        areas=None,
        compliance=None,
        energy=None,
        costs=None,
        orientation=None,
        review_stamp=None,
    )
    if row is None or row.building_type_version_id is None:
        return DesignReview(empty, {}, lines_offered=False)
    published = catalog_service.type_by_version_id(db, row.building_type_version_id)
    if published is None:
        return DesignReview(empty, {}, lines_offered=False)
    house = _house(published)
    options = _options(row)
    fit = evaluate_type(house, ctx, options)
    placement = _placement(row, ctx)
    offer = _offer(db, published, row)
    selection = _selection(offer, row)
    result, design = _evaluate(house, placement, options, ctx, offer, selection)
    evaluation = _evaluation_out(result) if result else None
    out = empty.model_copy(
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
            **_design_fields(design, offer, house, dropped or []),
        }
    )
    stamp = {
        **loaded.input_parts,
        "catalog": review.catalog_part(str(published.version.id), published.version.status, offer, selection),
        "configuration": str(row.revision),
        "result": review.result_part(out),
        "engine": review.digest([ENGINE_VERSION, ENVELOPE_ENGINE_VERSION]),
    }
    return DesignReview(
        out.model_copy(update={"review_stamp": review.make_stamp(stamp)}),
        _catalog_copy(published, offer, selection),
        lines_offered=any(p.offered for p in offer.packages),
    )


def options_catalog(db: Session, project_id: uuid.UUID) -> OptionsOut:
    """Linien und Optionen des gewählten Typs mit Preis, Zustand und Gründen (Plan H3 3.9, 4.3).

    Jede Option, die der Kunde noch nicht gewählt hat, wird zur aktuellen Auswahl hinzugenommen und gerechnet:
    neue bindende Verstöße oder ein Ausschluss machen sie `blocked`, mit Gründen. So sieht der Kunde,
    was nicht
    geht, ohne den Fehler auszulösen."""
    row = _row(db, project_id)
    published = (
        catalog_service.type_by_version_id(db, row.building_type_version_id)
        if row is not None and row.building_type_version_id is not None
        else None
    )
    if row is None or published is None:
        raise Problem(409, "no_type_selected")
    ctx = _load(db, project_id).ctx
    house = _house(published)
    offer = _offer(db, published, row)
    boundary, placement = _options(row), _placement(row, ctx)
    selection = _selection(offer, row)
    resolved = resolve(offer, selection)
    known = set(resolved.invalid)
    allowed = _allowed_blockers(house, placement, boundary, ctx, offer, (placement, boundary, selection))

    packages = [
        outputs.package_choice(
            p,
            offer.vat_rate,
            energy_status(offer.finding(p.slug)),
            selected=resolved.package is not None and resolved.package.slug == p.slug,
        )
        for p in offer.packages
        if p.offered
    ]
    choices: list[OptionChoiceOut] = []
    for option in offer.options:
        included = option.slug in resolved.included_slugs
        if not (option.offered or included):
            continue
        area = _option_area(option, house)
        state: OptionState
        reasons: list[Reason]
        blockers: list[Check]
        if included:
            state, reasons, blockers = "included", [], []
        elif option.slug in selection.option_slugs:
            state, reasons, blockers = "selected", [], []
        else:
            trial = replace(selection, option_slugs=(*selection.option_slugs, option.slug))
            reasons = [r for r in resolve(offer, trial).invalid if r not in known]
            blockers = []
            if not reasons:
                _, design = _evaluate(house, placement, boundary, ctx, offer, trial)
                blockers = _new_blockers(design, allowed)
            state = "blocked" if reasons or blockers else "available"
        choices.append(
            outputs.option_choice(
                option,
                state,
                offer.vat_rate,
                area_m2=area,
                reasons=reasons,
                checks=blockers,
            )
        )
    return OptionsOut(
        type_slug=published.slug,
        catalog_available=offer.catalog_available,
        vat_rate=offer.vat_rate,
        packages=packages,
        options=choices,
    )


def _option_area(option: OptionOffer, house: HouseType) -> float | None:
    if option.kind == "terrace":
        return terrace_spec(option, house).area_m2
    if option.kind == "carport":
        return carport_spec(option).area_m2
    return None


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
                # Die Fläche liegt schon in lokalen Metern
                rings_local=[
                    ring for poly in polygons(surfaces[rotation]) for ring in local_rings(poly, (0.0, 0.0))
                ],
                area_m2=round(float(surfaces[rotation].area), 2),
            )
            for rotation in rotations
        ],
    )


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


def _drop_unoffered(offer: TypeOffer, selection: Selection) -> tuple[Selection, list[str]]:
    """Beim Typwechsel entfällt, was der neue Typ nicht anbietet (Plan H3 3.1)."""
    unoffered = {"not_offered", "unknown_option", "unknown_package", "catalog_unavailable"}
    bad = {r.slug for r in resolve(offer, selection).invalid if r.code in unoffered and r.slug}
    kept = Selection(
        None if selection.package_slug in bad else selection.package_slug,
        tuple(s for s in selection.option_slugs if s not in bad),
    )
    return kept, sorted(s for s in bad if s)


def _allowed_blockers(
    house: HouseType,
    placement: Placement | None,
    boundary: BoundaryOptions,
    ctx: SiteContext,
    offer: TypeOffer,
    stored: tuple[Placement | None, BoundaryOptions, Selection] | None,
) -> set[tuple[str, str | None, int | None, str | None]]:
    """Verstöße, die schon ohne die neue Wahl bestanden: der Stand ohne Optionen (was H2 angenommen hat) und
    der gespeicherte Stand. Nur **neue** bindende Verstöße lehnt H3 ab (Plan H3 3.9), damit niemand in einem
    Zustand festhängt, den erst ein Katalog- oder Regelwechsel ungültig gemacht hat."""
    _, base = _evaluate(house, placement, boundary, ctx, offer, Selection())
    allowed = {_key(c) for c in base.blocking}
    if stored is not None:
        old_placement, old_boundary, old_selection = stored
        _, old = _evaluate(house, old_placement, old_boundary, ctx, offer, old_selection)
        allowed |= {_key(c) for c in old.blocking}
    return allowed


def patch_configuration(
    db: Session,
    project_id: uuid.UUID,
    body: ConfigurationPatch,
    *,
    if_match: int | None,
    actor: str,
) -> ConfigurationOut:
    """Typ, Lage, Grenzschalter, Linie und Optionen ändern. Gespeichert wird nie ein Typ, der gesperrt ist,
    nie eine Lage mit bindendem Verstoß und keine Auswahl mit neuem bindendem Verstoß (D12); die Serverprüfung
    ist maßgeblich (L5)."""
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
    boundary = _options(row)
    stored_placement = _placement(row, ctx)
    placement = stored_placement
    stored_offer = _offer(db, published, row) if published else None
    stored_selection = _selection(stored_offer, row) if stored_offer else Selection()
    selection = stored_selection
    dropped: list[str] = []

    new_type = False
    if "type_slug" in fields:
        if body.type_slug is None:
            published, placement, boundary, selection = None, None, {}, Selection()
        else:
            chosen = next((p for p in catalog_service.published_types(db) if p.slug == body.type_slug), None)
            if chosen is None:
                raise Problem(404, "type_not_found")
            if published is None or published.version.id != chosen.version.id:
                new_type, placement, boundary = True, None, {}
            published = chosen
    if "boundary_options" in fields:
        boundary = {seq: True for seq, on in (body.boundary_options or {}).items() if on}
    if published is None and ("package_slug" in fields or "option_slugs" in fields):
        raise Problem(409, "no_type_selected")
    if "package_slug" in fields:
        selection = replace(selection, package_slug=body.package_slug or None)
    if "option_slugs" in fields:
        selection = replace(selection, option_slugs=tuple(dict.fromkeys(body.option_slugs or [])))

    offer: TypeOffer | None = None
    if published is None:
        if body.placement is not None:
            raise Problem(409, "no_type_selected")
        boundary, selection = {}, Selection()
    else:
        house = _house(published)
        offer = _offer(db, published, row)
        _check_boundary_options(house, ctx, boundary)
        fit = evaluate_type(house, ctx, boundary)
        if not fit.allowed and (new_type or "boundary_options" in fields or "type_slug" in fields):
            raise Problem(422, "type_blocked", reasons=_dump(fit.reasons))
        if new_type:
            selection, dropped = _drop_unoffered(offer, selection)
        elif "package_slug" in fields or "option_slugs" in fields:
            known = set(resolve(offer, stored_selection).invalid)
            fresh = [r for r in resolve(offer, selection).invalid if r not in known]
            if fresh:
                raise Problem(
                    422,
                    "invalid_selection",
                    reasons=[outputs.reason_out(r).model_dump(mode="json") for r in fresh],
                )
        if "placement" in fields:
            placement = _requested_placement(house, ctx, body)
        elif placement is None:
            placement = preset_rules.compute(house, ctx, "street_near", boundary, _eligible_parts(house, ctx))
        result, design = _evaluate(house, placement, boundary, ctx, offer, selection)
        if result is not None and result.blocking:
            raise Problem(
                422,
                "placement_violation",
                checks=_dump(result.checks),
                edges=[e.model_dump(mode="json") for e in _evaluation_out(result).edges],
            )
        if design.blocking:
            stored = None if new_type else (stored_placement, _options(row), stored_selection)
            allowed = _allowed_blockers(house, placement, boundary, ctx, offer, stored)
            fresh_blockers = _new_blockers(design, allowed)
            if fresh_blockers and new_type:
                # Optionen, die auf dem neuen Typ nicht aufgehen (Terrasse ohne Garten), fallen weg
                subjects = {str(c.params["subject"]) for c in fresh_blockers if "subject" in c.params}
                gone = subjects & set(selection.option_slugs)
                if gone:
                    dropped = sorted({*dropped, *gone})
                    selection = replace(
                        selection, option_slugs=tuple(s for s in selection.option_slugs if s not in gone)
                    )
                    _, design = _evaluate(house, placement, boundary, ctx, offer, selection)
                    fresh_blockers = _new_blockers(design, allowed)
            if fresh_blockers:
                raise Problem(422, "selection_blocked", checks=_dump(fresh_blockers))

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
    row.boundary_options = {str(seq): True for seq in boundary}
    row.package_version_id, row.modules = _selection_ids(offer, selection) if offer else (None, [])
    row.updated_at = utcnow()
    row.updated_by = actor
    db.commit()
    return get_configuration(db, project_id, dropped=dropped)


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
