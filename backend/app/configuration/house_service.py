"""Konfiguration des Hausmodells (docs/PLAN_HAUSMODELL.md 3.1, 3.7–3.9; HM4): Anwendungsfälle des Kundenwegs.

Haustypen und Katalog kommen aus `house.service` mit festgehaltenen Versionen (E-HM-7), die maßgebliche
Rechnung aus `engine` (L5), die Prüfung auf dem Grundstück aus `configuration/domain` über die
Hausbeschreibung (E-HM-4). Gespeichert wird jede Auswahl und Lage, auch eine unzulässige (E-HM-6); nur ein
Haustyp ohne zulässige Lage lässt sich nicht wählen (D12). Lesen braucht `engine` nicht: Die Hausbeschreibung
steht im Snapshot, Grundstück und Regeln gelten im aktuellen Stand.
"""

import uuid

import httpx2
from shapely.geometry import Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.configuration import outputs
from app.configuration.domain import ENGINE_VERSION
from app.configuration.domain import presets as preset_rules
from app.configuration.domain.change import ChangeRejected, check_boundary_options
from app.configuration.domain.compliance import MaterialSubject
from app.configuration.domain.facts import FactsError, house_type
from app.configuration.domain.fit import eligible_parts, evaluate_type
from app.configuration.domain.geometry import polygons
from app.configuration.domain.house import HouseType
from app.configuration.domain.outcomes import combined_status, round_amount, site_outcome
from app.configuration.domain.placement import Placement
from app.configuration.domain.rotations import candidate_rotations, is_allowed_rotation, site_rotations
from app.configuration.domain.site_check import SiteCheck, evaluate_site, placement_surfaces
from app.configuration.domain.surface import BoundaryOptions
from app.configuration.house_schemas import (
    HouseConfigurationOut,
    HouseConfigurationPatch,
    HouseConfigurationStaffOut,
    HouseDocumentsOut,
    HouseFactsOut,
    HousePriceOut,
    HouseSiteResultOut,
    HouseTemplateFitOut,
    HouseTemplateRefOut,
    HouseTemplatesOut,
)
from app.configuration.models import HouseConfigurationRecord
from app.configuration.schemas import PlacementAreaOut, PresetsOut, RotationAreaOut
from app.configuration.service import Loaded, load_site
from app.envelope.domain import ENGINE_VERSION as ENVELOPE_ENGINE_VERSION
from app.house import engine
from app.house import service as house_service
from app.house.contract import HouseConfiguration, HouseEvaluation, HouseFacts, HousePrice
from app.house.engine import EngineRejected
from app.house.service import TemplatePair
from app.platform.db import utcnow
from app.platform.logging import get_logger
from app.platform.problems import Problem
from app.site.domain.local import rings as local_rings

FEATURE_FLAG = "house_model"
TOTAL_STEP_EUR = 1000.0
DELTA_STEP_EUR = 100.0
PRICE_TOLERANCE_EUR = 0.005
"""Browser und Server rechnen gleich, wenn die Nettobeträge auf den Cent übereinstimmen (Risiko 9, L5)."""
EMPTY = HouseConfiguration(selections={})
OUTCOME_ORDER = {"deviation": 0, "warning": 1, "info": 2}

log = get_logger("house_configuration")


# ---------------------------------------------------------------------------
# Eingaben
# ---------------------------------------------------------------------------


def _row(db: Session, project_id: uuid.UUID, *, lock: bool = False) -> HouseConfigurationRecord | None:
    query = select(HouseConfigurationRecord).where(HouseConfigurationRecord.project_id == project_id)
    if lock:
        query = query.with_for_update()
    return db.execute(query).scalar_one_or_none()


def _pinned(db: Session, row: HouseConfigurationRecord | None) -> TemplatePair | None:
    if row is None or row.template_version_id is None or row.catalog_version_id is None:
        return None
    return house_service.pinned_pair(db, row.template_version_id, row.catalog_version_id)


def _options(row: HouseConfigurationRecord | None) -> BoundaryOptions:
    if row is None:
        return {}
    return {int(k): True for k, v in row.boundary_options.items() if v}


def _placement(row: HouseConfigurationRecord | None, loaded: Loaded) -> Placement | None:
    if row is None or not row.placement:
        return None
    origin = loaded.ctx.origin
    return Placement(
        origin=(float(row.placement["origin_e"]) - origin[0], float(row.placement["origin_n"]) - origin[1]),
        rotation_deg=float(row.placement["rotation_deg"]),
    )


def _stored_placement(placement: Placement | None, loaded: Loaded) -> dict[str, float] | None:
    """Lage in Lambert-93 wie `configuration.placement` (Spez. 4.4)."""
    if placement is None:
        return None
    origin = loaded.ctx.origin
    return {
        "origin_e": round(placement.origin[0] + origin[0], 3),
        "origin_n": round(placement.origin[1] + origin[1], 3),
        "rotation_deg": placement.rotation_deg,
    }


def _house(pair: TemplatePair, facts: HouseFacts) -> HouseType:
    try:
        return house_type(
            facts,
            slug=pair.slug,
            version=pair.template_version,
            version_id=str(pair.template_version_id),
            name=pair.template.name.fr,
        )
    except FactsError:
        # Eine Antwort außerhalb des Vertrags ist ein Ausfall des Rechendienstes (E-HM-45)
        log.warning("engine_unavailable", reason="contract:HouseFacts")
        raise Problem(503, "engine_unavailable") from None


def _materials(pair: TemplatePair, facts: HouseFacts) -> list[MaterialSubject]:
    """Materialklassen aus Wandprofil und Dachtyp für die PLU-Prüfung (Ergänzung 8)."""
    return [
        MaterialSubject(
            "house",
            pair.slug,
            {"facade_material": facts.facade_material_class, "roof_material": facts.roof_material_class},
        )
    ]


def _evaluate(
    client: httpx2.Client, pair: TemplatePair, configuration: HouseConfiguration
) -> HouseEvaluation:
    try:
        return engine.evaluate(client, pair.template, pair.catalog, configuration)
    except EngineRejected as exc:
        # Der Kern rechnet diese Auswahl nicht (unbekannter Wert, gemischte Profile …); der Browser auch nicht
        raise Problem(422, "house_selection_invalid", reason=exc.code, params=exc.detail) from None


# ---------------------------------------------------------------------------
# Ausgaben
# ---------------------------------------------------------------------------


def _ring(polygon: Polygon) -> list[list[float]]:
    return [[round(float(x), 3), round(float(y), 3)] for x, y, *_ in polygon.exterior.coords]


def _facts_out(house: HouseType, facts: HouseFacts) -> HouseFactsOut:
    min_x, min_y, max_x, max_y = house.facade.bounds
    return HouseFactsOut(
        storeys=house.storeys,
        roof_form=house.roof_form,
        pitch_deg=house.pitch_deg,
        height_m=house.ridge_height_m,
        eave_height_m=house.eave_height_m,
        floor_area_m2=round(facts.floor_area, 2),
        footprint_m2=round(float(house.facade.area), 2),
        width_m=round(max_x - min_x, 2),
        depth_m=round(max_y - min_y, 2),
        facade_local=_ring(house.facade),
        projection_local=_ring(house.projection),
        facade_roles={str(edge): role for edge, role in house.facade_roles.items()},
        facade_material=facts.facade_material_class,
        roof_material=facts.roof_material_class,
    )


def price_out(price: HousePrice) -> HousePriceOut:
    """Nur gerundete Bruttobeträge (E-HM-2, L1); dieselbe Rundung wie im Browser."""
    factor = 1.0 + price.vat_rate
    return HousePriceOut(
        currency=price.currency,
        vat_rate=price.vat_rate,
        gross_rounded=round_amount(price.gross_amount, TOTAL_STEP_EUR),
        deltas_rounded={
            slot: round_amount(delta * factor, DELTA_STEP_EUR) for slot, delta in sorted(price.deltas.items())
        },
    )


def _site_results(site: SiteCheck) -> list[HouseSiteResultOut]:
    results = []
    for check in site.checks:
        outcome = site_outcome(check)
        if outcome is not None:
            results.append(HouseSiteResultOut(outcome=outcome, check=outputs.check_out(check)))
    return sorted(results, key=lambda r: OUTCOME_ORDER[r.outcome])


def _empty(
    project_id: uuid.UUID, row: HouseConfigurationRecord | None, loaded: Loaded
) -> HouseConfigurationOut:
    return HouseConfigurationOut(
        project_id=project_id,
        revision=row.revision if row else 0,
        mode=loaded.ctx.mode,
        free_reason=loaded.ctx.free_reason,
        notices=loaded.notices,
        template=None,
        update_available=False,
        configuration=EMPTY,
        placement=None,
        boundary_options={},
        rotations=[],
        facts=None,
        evaluation=None,
        areas=None,
        orientation=None,
        status=None,
        rule_results=[],
        notes=[],
        site_results=[],
        suggestion=None,
        price=None,
        domain_version=None,
        site_changed=False,
        updated_at=row.updated_at if row else None,
    )


def _out(
    db: Session,
    row: HouseConfigurationRecord,
    pair: TemplatePair,
    evaluation: HouseEvaluation,
    house: HouseType,
    site: SiteCheck,
    loaded: Loaded,
    *,
    price_match: bool | None = None,
) -> HouseConfigurationOut:
    results = _site_results(site)
    offered = house_service.offered_version_ids(db, pair.slug)
    stored_site = (row.snapshot or {}).get("site") or {}
    return _empty(row.project_id, row, loaded).model_copy(
        update={
            "template": HouseTemplateRefOut(
                slug=pair.slug,
                version=pair.template_version,
                catalog_version=pair.catalog_version,
                name=pair.template.name,
                retired=pair.template_status == "retired",
            ),
            "update_available": offered is not None
            and offered != (pair.template_version_id, pair.catalog_version_id),
            "configuration": HouseConfiguration.model_validate(row.configuration),
            "placement": outputs.placement_out(site.result.placement) if site.result else None,
            "boundary_options": {str(k): True for k in _options(row)},
            "rotations": site_rotations(house, loaded.ctx),
            "facts": _facts_out(house, evaluation.facts),
            "evaluation": outputs.evaluation_out(site.result) if site.result else None,
            "areas": outputs.areas_out(site.areas),
            "orientation": outputs.orientation_out(site.orientation),
            "status": combined_status(evaluation.status, (r.outcome for r in results)),
            "rule_results": evaluation.rule_results,
            "notes": evaluation.notes,
            "site_results": results,
            "suggestion": outputs.placement_out(site.suggestion) if site.suggestion else None,
            "price": price_out(evaluation.price),
            "price_match": price_match,
            "domain_version": evaluation.domain_version,
            "site_changed": bool(stored_site) and stored_site.get("input_parts") != loaded.input_parts,
        }
    )


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def list_templates(db: Session, client: httpx2.Client, project_id: uuid.UUID) -> HouseTemplatesOut:
    """Angebotene Haustypen mit Zulässigkeit, geprüft mit den Standards des Templates (Ergänzung 9, D12),
    Richtpreis „ab“ und Kennwerten. Ein Paar, das der Kern nicht rechnet, wird nicht angeboten."""
    loaded = load_site(db, project_id)
    templates = []
    for pair in house_service.offered_templates(db):
        try:
            evaluation = engine.evaluate(client, pair.template, pair.catalog, EMPTY)
        except EngineRejected as exc:
            log.warning("house_template_not_computable", slug=pair.slug, code=exc.code)
            continue
        house = _house(pair, evaluation.facts)
        fit = evaluate_type(house, loaded.ctx)
        templates.append(
            HouseTemplateFitOut(
                slug=pair.slug,
                version=pair.template_version,
                catalog_version=pair.catalog_version,
                name=pair.template.name,
                allowed=fit.allowed,
                reasons=[outputs.check_out(c) for c in fit.reasons],
                hints=[outputs.check_out(c) for c in fit.hints],
                rotations=fit.rotations,
                status=evaluation.status,
                price=price_out(evaluation.price),
                facts=_facts_out(house, evaluation.facts),
            )
        )
    return HouseTemplatesOut(
        mode=loaded.ctx.mode,
        free_reason=loaded.ctx.free_reason,
        notices=loaded.notices,
        site_revision=loaded.site_revision,
        templates=templates,
    )


def _snapshot_evaluation(row: HouseConfigurationRecord) -> HouseEvaluation | None:
    if not row.snapshot:
        return None
    return HouseEvaluation.model_validate(row.snapshot["evaluation"])


def _configuration(
    db: Session, project_id: uuid.UUID
) -> tuple[HouseConfigurationOut, HouseConfigurationRecord | None]:
    row = _row(db, project_id)
    loaded = load_site(db, project_id)
    pair = _pinned(db, row)
    evaluation = _snapshot_evaluation(row) if row is not None else None
    if row is None or pair is None or evaluation is None:
        return _empty(project_id, row, loaded), row
    house = _house(pair, evaluation.facts)
    site = evaluate_site(
        house, _placement(row, loaded), loaded.ctx, _options(row), _materials(pair, evaluation.facts)
    )
    return _out(db, row, pair, evaluation, house, site, loaded), row


def get_configuration(db: Session, project_id: uuid.UUID) -> HouseConfigurationOut:
    """Gespeicherte Auswahl mit dem Ergebnis des Snapshots; die PLU-Prüfung neu im aktuellen Stand von
    Grundstück und Regeln (E-HM-7)."""
    return _configuration(db, project_id)[0]


def get_configuration_staff(db: Session, project_id: uuid.UUID) -> HouseConfigurationStaffOut:
    """Für das Büro zusätzlich festgehaltene Versionen und der Snapshot mit exakten Beträgen (3.8)."""
    out, row = _configuration(db, project_id)
    return HouseConfigurationStaffOut(
        **dict(out),
        template_version_id=row.template_version_id if row else None,
        catalog_version_id=row.catalog_version_id if row else None,
        snapshot=row.snapshot if row else None,
    )


def documents(db: Session, project_id: uuid.UUID) -> HouseDocumentsOut:
    """Festgehaltenes Template und Katalogversion für den Kern im Browser (Vorschau ohne Server, 3.1)."""
    pair = _pinned(db, _row(db, project_id))
    if pair is None:
        raise Problem(409, "no_house_template_selected")
    return HouseDocumentsOut(
        template_version_id=pair.template_version_id,
        catalog_version_id=pair.catalog_version_id,
        template=pair.template,
        catalog=pair.catalog,
    )


def _current_house(
    db: Session, project_id: uuid.UUID
) -> tuple[TemplatePair, HouseType, BoundaryOptions, Loaded]:
    row = _row(db, project_id)
    pair = _pinned(db, row)
    evaluation = _snapshot_evaluation(row) if row is not None else None
    if row is None or pair is None or evaluation is None:
        raise Problem(409, "no_house_template_selected")
    return pair, _house(pair, evaluation.facts), _options(row), load_site(db, project_id)


def placement_area(db: Session, project_id: uuid.UUID) -> PlacementAreaOut:
    """Fläche zulässiger Ursprünge je erlaubter Drehung für das Haus mit der gespeicherten Auswahl."""
    pair, house, boundary, loaded = _current_house(db, project_id)
    surfaces = placement_surfaces(house, loaded.ctx, boundary)
    return PlacementAreaOut(
        type_slug=pair.slug,
        rotations=[
            RotationAreaOut(
                rotation_deg=rotation,
                rings_local=[ring for poly in polygons(surface) for ring in local_rings(poly, (0.0, 0.0))],
                area_m2=round(float(surface.area), 2),
            )
            for rotation, surface in surfaces.items()
        ],
    )


def presets(db: Session, project_id: uuid.UUID) -> PresetsOut:
    """Schnellstellungen `street_near`, `set_back`, `garden_max` (Spez. 5.3.5) zur gespeicherten Auswahl."""
    pair, house, boundary, loaded = _current_house(db, project_id)
    computed = preset_rules.all_presets(house, loaded.ctx, boundary, eligible_parts(house, loaded.ctx))
    return PresetsOut(
        type_slug=pair.slug,
        presets={name: outputs.placement_out(place) if place else None for name, place in computed.items()},
    )


# ---------------------------------------------------------------------------
# Ändern
# ---------------------------------------------------------------------------


def _requested(body: HouseConfigurationPatch, house: HouseType, loaded: Loaded) -> Placement | None:
    """Verlangte Lage mit einer der vier Ausrichtungen zur Straße; eine Lage mit Verstößen bleibt erlaubt."""
    if body.placement is None:
        return None
    allowed = candidate_rotations(house, loaded.ctx)
    matched = is_allowed_rotation(body.placement.rotation_deg, allowed)
    if matched is None:
        raise Problem(422, "rotation_not_allowed", allowed=sorted(allowed))
    return Placement(origin=(body.placement.origin.e, body.placement.origin.n), rotation_deg=matched)


def _choose(
    db: Session, client: httpx2.Client, slug: str, loaded: Loaded
) -> tuple[TemplatePair, HouseEvaluation]:
    """Neuer Haustyp: die angebotenen Versionen, zulässig mit den Standards (D12, Ergänzung 9)."""
    offered = house_service.offered_templates(db, slug)
    if not offered:
        raise Problem(404, "house_template_not_found")
    pair = offered[0]
    evaluation = _evaluate(client, pair, EMPTY)
    fit = evaluate_type(_house(pair, evaluation.facts), loaded.ctx)
    if not fit.allowed:
        raise Problem(
            422, "type_blocked", reasons=[outputs.check_out(c).model_dump(mode="json") for c in fit.reasons]
        )
    return pair, evaluation


def patch_configuration(
    db: Session,
    client: httpx2.Client,
    project_id: uuid.UUID,
    body: HouseConfigurationPatch,
    *,
    if_match: int | None,
    actor: str,
) -> HouseConfigurationOut:
    """Haustyp, Auswahl, Lage oder Grenzschalter ändern; `engine` rechnet maßgeblich, der Snapshot hält das
    Ergebnis fest. Ein neuer Haustyp beginnt mit seinen Standards und der straßennahen Stellung."""
    fields = body.model_fields_set - {"client_price"}
    row = _row(db, project_id, lock=True)
    current = row.revision if row else 0
    if if_match is not None and if_match != current:
        raise Problem(409, "revision_conflict", current_revision=current)
    if not fields:
        return get_configuration(db, project_id)

    loaded = load_site(db, project_id)
    pair = _pinned(db, row)
    configuration = HouseConfiguration.model_validate(row.configuration) if row else EMPTY
    placement, boundary = _placement(row, loaded), _options(row)
    evaluation: HouseEvaluation | None = None
    if "template_slug" in fields:
        if body.template_slug is None:
            pair = None
        elif pair is None or pair.slug != body.template_slug:
            pair, evaluation = _choose(db, client, body.template_slug, loaded)
            configuration, placement, boundary = EMPTY, None, {}
    if pair is None:
        if fields - {"template_slug"}:
            raise Problem(409, "no_house_template_selected")
        return _save_empty(db, row, project_id, loaded, actor)

    if "configuration" in fields:
        configuration = body.configuration or EMPTY
    if "boundary_options" in fields:
        boundary = {seq: True for seq, on in (body.boundary_options or {}).items() if on}
    if evaluation is None or configuration != EMPTY:
        evaluation = _evaluate(client, pair, configuration)
    house = _house(pair, evaluation.facts)
    try:
        check_boundary_options(house, loaded.ctx, boundary)
    except ChangeRejected as rejected:
        raise Problem(422, "boundary_not_allowed", edges=rejected.edges) from None
    if "placement" in fields:
        placement = _requested(body, house, loaded)
    elif placement is None:
        placement = preset_rules.compute(
            house, loaded.ctx, "street_near", boundary, eligible_parts(house, loaded.ctx)
        )
    site = evaluate_site(house, placement, loaded.ctx, boundary, _materials(pair, evaluation.facts))

    price_match = None
    if body.client_price is not None:
        price_match = abs(body.client_price.net_amount - evaluation.price.net_amount) < PRICE_TOLERANCE_EUR
        if not price_match:
            log.warning(
                "house_price_mismatch",
                client=body.client_price.net_amount,
                server=evaluation.price.net_amount,
                client_domain=body.client_price.domain_version,
                server_domain=evaluation.domain_version,
            )

    if row is None:
        row = HouseConfigurationRecord(project_id=project_id, revision=1, created_by=actor)
        db.add(row)
    else:
        row.revision = row.revision + 1
    results = _site_results(site)
    now = utcnow()
    row.template_version_id = pair.template_version_id
    row.catalog_version_id = pair.catalog_version_id
    row.configuration = configuration.model_dump(mode="json")
    row.placement = _stored_placement(placement, loaded)
    row.boundary_options = {str(seq): True for seq in boundary}
    row.engine_version = evaluation.domain_version
    row.snapshot = {
        "computed_at": now.isoformat(),
        "domain_version": evaluation.domain_version,
        "evaluation": evaluation.model_dump(mode="json"),
        "site": {
            "engine_version": f"{ENGINE_VERSION}+{ENVELOPE_ENGINE_VERSION}",
            "input_parts": loaded.input_parts,
            "status": combined_status(evaluation.status, (r.outcome for r in results)),
            "results": [r.model_dump(mode="json") for r in results],
        },
        "price_check": (
            {"client_net": body.client_price.net_amount, "match": price_match}
            if body.client_price is not None
            else None
        ),
    }
    row.updated_at = now
    row.updated_by = actor
    db.commit()
    return _out(db, row, pair, evaluation, house, site, loaded, price_match=price_match)


def _save_empty(
    db: Session, row: HouseConfigurationRecord | None, project_id: uuid.UUID, loaded: Loaded, actor: str
) -> HouseConfigurationOut:
    """Haustyp abgewählt: Auswahl, Lage und Snapshot entfallen."""
    if row is None:
        row = HouseConfigurationRecord(project_id=project_id, revision=1, created_by=actor)
        db.add(row)
    else:
        row.revision = row.revision + 1
    row.template_version_id = row.catalog_version_id = None
    row.configuration = EMPTY.model_dump(mode="json")
    row.placement = row.snapshot = row.engine_version = None
    row.boundary_options = {}
    row.updated_at, row.updated_by = utcnow(), actor
    db.commit()
    return _empty(project_id, row, loaded)
