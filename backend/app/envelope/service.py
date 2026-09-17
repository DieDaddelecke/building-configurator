"""Anwendungsfälle des Moduls G3 (Plan 3.5). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Der Baurahmen wird bei jedem Abruf aus Grundstück (G1) und Regeln (G2) neu abgeleitet. Er wird nicht
zwischengespeichert: Gelände, Projektkorrekturen und der Rückfall auf einen vorigen Planstand ändern weder
die Revision des Grundstücks noch die Regelwerksversion, ein Zwischenspeicher nach Nummern lieferte dann
einen veralteten Baurahmen (Plan G3 11.1 Nr. 1). Stattdessen trägt jede Antwort eine Prüfsumme über den
Inhalt der Eingaben; Steckbrief und später der Snapshot der Anfrage hängen daran.
"""

import hashlib
import json
import uuid
from typing import Any

import shapely
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.envelope.domain import ENGINE_VERSION
from app.envelope.domain import local as local_coords
from app.envelope.domain.bands import Band
from app.envelope.domain.derive import Contour, EdgeResult, Envelope, Limit, PartResult, derive_envelope
from app.envelope.domain.inputs import (
    Citation,
    ConstraintInput,
    EdgeInput,
    EnvelopeInput,
    RuleInput,
    SiteInput,
    TerrainInput,
    ZoneInput,
)
from app.envelope.models import EnvelopeSheet
from app.envelope.schemas import (
    BandOut,
    CitationOut,
    ConstraintOut,
    ContourOut,
    EnvelopeEdgeOut,
    EnvelopeOut,
    HeightsOut,
    LimitOut,
    PartOut,
    ProvenanceOut,
    SetbackOut,
    SheetOut,
)
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.problems import Problem
from app.rules import service as rules_service
from app.rules.schemas import RuleOut
from app.site import service as site_service
from app.site.schemas import LocalOrigin

FEATURE_FLAG = "envelope_simulation"
NOTICE = "notice.envelope_simulation"
SHEET_PREFIX = "envelope-sheets"


# ---------------------------------------------------------------------------
# Eingaben
# ---------------------------------------------------------------------------


def _citation(rule: RuleOut) -> Citation:
    return Citation(
        page=rule.page,
        quote=rule.quote,
        quote_verified=rule.quote_verified,
        source_url=rule.source_url,
        origin=rule.origin,
        confidence=rule.confidence,
        notes=rule.notes,
    )


def _rule_input(rule: RuleOut) -> RuleInput:
    return RuleInput(
        kind=rule.kind,
        building_kind=rule.building_kind,
        status=rule.status,
        reason=rule.reason,
        params=dict(rule.params),
        citation=_citation(rule),
    )


def envelope_input(
    db: Session, project_id: uuid.UUID, site: site_service.EnvelopeSite | None = None
) -> tuple[EnvelopeInput, rules_service.RulesResult]:
    """Eingaben aus G1 und G2 einsammeln. Nur für Grundstücke aus Kataster (`site.origin == 'parcel'`);
    für Weg E (freies Zeichnen) siehe `_manual_sketch_input` – G2 wird dafür nicht aufgerufen (D13)."""
    if site is None:
        site = site_service.envelope_site(db, project_id)
    rules = rules_service.envelope_rules(db, project_id)
    geometries = {zone.code: shapely.from_wkb(zone.wkb) for zone in rules.zones}
    zones = [
        ZoneInput(
            code=zone.code,
            label=zone.label,
            status=zone.status,
            reason=zone.reason,
            area_m2=zone.area_m2,
            share=zone.share,
            polygon=geometries[zone.code],
            rules=[_rule_input(rule) for rule in zone.rules],
            hints=[_rule_input(hint) for hint in zone.hints],
            version_id=str(zone.version.id) if zone.version else None,
        )
        for zone in rules.out.zones
        if zone.code in geometries
    ]
    data = EnvelopeInput(
        site=SiteInput(
            polygon=site.polygon,
            area_m2=site.area_m2,
            local_origin=site.local_origin,
            edges=[
                EdgeInput(
                    seq=edge.seq,
                    ring=edge.ring,
                    kind=edge.kind,
                    classification_source=edge.classification_source,
                    confidence=edge.confidence,
                    length_m=edge.length_m,
                    normal_azimuth_deg=edge.normal_azimuth_deg,
                    street_name=edge.street_name,
                    geometry=edge.geometry,
                )
                for edge in site.edges
            ],
            main_street_seq=site.main_street_seq,
            warnings=list(site.warnings),
            customer_edges_unconfirmed=site.customer_edges_unconfirmed,
            terrain=TerrainInput(
                status=site.terrain_status,
                slope_percent=site.terrain_slope_percent,
                reference_altitude_ngf=site.terrain_reference_altitude_ngf,
                method=site.terrain_method,
            ),
            parcels=list(site.parcel_idus),
            revision=site.revision,
            engine_version=site.engine_version,
        ),
        zones=zones,
        constraints=[
            ConstraintInput(
                category=item.category,
                type_code=item.type_code,
                label=item.label,
                endpoint=item.endpoint,
                geometry=shapely.from_wkb(item.wkb),
            )
            for item in rules.constraints
        ],
        rules_status=rules.out.status,
        rules_reason=rules.out.reason,
        uncovered_share=rules.out.uncovered_share,
        warnings=list(rules.out.warnings),
        notices=[NOTICE, *rules.out.notices, "notice.cadastre_accuracy"],
        rules_engine_version=rules.engine_version,
    )
    return data, rules


def fingerprint(data: EnvelopeInput) -> str:
    """Prüfsumme über den Inhalt aller Eingaben (Plan G3 4.2).

    Nicht über Revisions- und Versionsnummern: Gelände trifft ohne neue Revision ein, Projektkorrekturen
    und der Wechsel auf den Rückfall-Planstand erzeugen keine neue Regelwerksversion.
    """
    payload = {
        "engine": ENGINE_VERSION,
        "site": {
            "outline": _geometry_key(data.site.polygon),
            "edges": [
                [
                    e.seq,
                    e.ring,
                    e.kind,
                    e.classification_source,
                    round(e.confidence, 3),
                    _geometry_key(e.geometry),
                ]
                for e in data.site.edges
            ],
            "terrain": [
                data.site.terrain.status,
                data.site.terrain.slope_percent,
                data.site.terrain.reference_altitude_ngf,
            ],
            "warnings": sorted(data.site.warnings),
            "customer_edges_unconfirmed": data.site.customer_edges_unconfirmed,
        },
        "zones": [
            {
                "code": z.code,
                "status": z.status,
                "reason": z.reason,
                "polygon": _geometry_key(z.polygon),
                "rules": sorted(
                    [r.kind, r.building_kind, r.status, str(r.reason), json.dumps(r.params, sort_keys=True)]
                    for r in [*z.rules, *z.hints]
                ),
            }
            for z in data.zones
        ],
        "constraints": sorted(
            [c.category, c.type_code or "", c.label, _geometry_key(c.geometry)] for c in data.constraints
        ),
        "rules_status": [data.rules_status, data.rules_reason, round(data.uncovered_share, 4)],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _geometry_key(geometry: BaseGeometry) -> str:
    """Geometrie auf Millimeter gerundet als Hex-WKB: gleiche Fläche, gleiche Prüfsumme."""
    if geometry.is_empty:
        return ""
    return str(shapely.to_wkb(shapely.set_precision(geometry, 0.001), hex=True))


# ---------------------------------------------------------------------------
# Weg E: freies Zeichnen ohne Kataster (Plan 3.3, D13)
# ---------------------------------------------------------------------------

MANUAL_SKETCH_REASON = "manual_sketch"
MANUAL_SKETCH_NOTICE = "notice.manual_sketch"


def _manual_sketch_input(site: site_service.EnvelopeSite) -> EnvelopeInput:
    """G2 wird nicht aufgerufen: keine Zonen, keine Vorgaben, keine Kosten für eine Auswertung (D13)."""
    return EnvelopeInput(
        site=SiteInput(
            polygon=site.polygon,
            area_m2=site.area_m2,
            local_origin=site.local_origin,
            edges=[],
            parcels=[],
            revision=site.revision,
            engine_version=site.engine_version,
            terrain=TerrainInput(status=site.terrain_status),
        ),
        rules_status="unavailable",
        rules_reason=MANUAL_SKETCH_REASON,
        notices=[MANUAL_SKETCH_NOTICE],
        rules_engine_version="n/a",
    )


def _manual_sketch_envelope(site: site_service.EnvelopeSite) -> EnvelopeOut:
    """Kein Baurahmen für Weg E: die Fläche ist nicht mit dem Bebauungsplan abgeglichen (Plan 3.3)."""
    origin = site.local_origin
    fingerprint_raw = f"manual_sketch:{site.site_id}:{site.revision}".encode()
    return EnvelopeOut(
        status="unavailable",
        reason=MANUAL_SKETCH_REASON,
        engine_version=ENGINE_VERSION,
        input_hash="sha256:" + hashlib.sha256(fingerprint_raw).hexdigest(),
        updated_at=utcnow(),
        local_origin=LocalOrigin(e=origin[0], n=origin[1]),
        area_m2=round(site.area_m2, 2),
        parcels=[],
        outline_local=local_coords.rings(site.polygon, origin),
        contours={},
        parts=[],
        edges=[],
        bands=[],
        constraints=[],
        warnings=[],
        notices=[MANUAL_SKETCH_NOTICE],
        provenance=ProvenanceOut(
            site_revision=site.revision,
            site_engine_version=site.engine_version,
            rules_engine_version="n/a",
            rule_set_version_ids=[],
            project_overrides=0,
            terrain_status=site.terrain_status,
            assumptions=[],
        ),
    )


# ---------------------------------------------------------------------------
# Baurahmen
# ---------------------------------------------------------------------------


def build_envelope(db: Session, project_id: uuid.UUID) -> tuple[EnvelopeOut, EnvelopeInput]:
    """Baurahmen ableiten und ausgeben; die Eingaben kommen mit, damit der Steckbrief ihre Prüfsumme
    gegen den angeforderten Stand halten kann. Für Weg E (Plan 3.3) wird G2 nicht aufgerufen (D13)."""
    site = site_service.envelope_site(db, project_id)
    if site.origin == "manual_sketch":
        return _manual_sketch_envelope(site), _manual_sketch_input(site)
    data, rules = envelope_input(db, project_id, site=site)
    envelope = derive_envelope(data)
    return _out(db, data, rules, envelope), data


def project_envelope(db: Session, project_id: uuid.UUID) -> EnvelopeOut:
    """Baurahmen des Grundstücks als Simulation (Plan 3.5, D11)."""
    return build_envelope(db, project_id)[0]


def _out(
    db: Session,
    data: EnvelopeInput,
    rules: rules_service.RulesResult,
    envelope: Envelope,
) -> EnvelopeOut:
    origin = data.site.local_origin
    site = data.site
    return EnvelopeOut(
        status=envelope.status,
        reason=envelope.reason,
        engine_version=ENGINE_VERSION,
        input_hash=fingerprint(data),
        updated_at=utcnow(),
        local_origin=LocalOrigin(e=origin[0], n=origin[1]),
        area_m2=round(site.area_m2, 2),
        parcels=list(site.parcels),
        outline_local=local_coords.rings(site.polygon, origin),
        contours={
            reading: _contour_out(db, contour, origin) for reading, contour in envelope.contours.items()
        },
        parts=[_part_out(part, origin) for part in envelope.parts],
        edges=[_edge_out(edge, origin) for edge in envelope.edges],
        bands=[_band_out(band, origin) for band in envelope.bands],
        constraints=[_constraint_out(item, origin) for item in envelope.constraints],
        warnings=envelope.warnings,
        notices=list(dict.fromkeys(data.notices)),
        provenance=ProvenanceOut(
            site_revision=site.revision,
            site_engine_version=site.engine_version,
            rules_engine_version=data.rules_engine_version,
            plan_id=rules.out.plan.id if rules.out.plan else None,
            plan_title=rules.out.plan.title if rules.out.plan else None,
            rule_set_version_ids=rules.rule_set_version_ids,
            project_overrides=rules.override_count,
            terrain_status=site.terrain.status,
            terrain_slope_percent=site.terrain.slope_percent,
            terrain_reference_altitude_ngf=site.terrain.reference_altitude_ngf,
            assumptions=envelope.assumptions,
        ),
    )


def _contour_out(db: Session, contour: Contour, origin: tuple[float, float]) -> ContourOut:
    return ContourOut(
        rings_local=local_coords.rings(contour.geometry, origin),
        geojson=_geojson(db, contour.geometry),
        area_m2=contour.area_m2,
        complete=contour.complete,
        incomplete_reasons=contour.incomplete_reasons,
    )


def _geojson(db: Session, geometry: BaseGeometry) -> dict[str, Any] | None:
    if geometry.is_empty:
        return None
    raw = db.execute(
        text("SELECT ST_AsGeoJSON(ST_Transform(ST_GeomFromWKB(:wkb, 2154), 4326), 7)"),
        {"wkb": shapely.to_wkb(geometry)},
    ).scalar_one()
    return dict(json.loads(raw))


def _citation_out(citation: Citation | None) -> CitationOut | None:
    if citation is None:
        return None
    return CitationOut(
        page=citation.page,
        quote=citation.quote,
        quote_verified=citation.quote_verified,
        source_url=citation.source_url,
        origin=citation.origin,
        confidence=citation.confidence,
        notes=citation.notes,
    )


def _limit_out(limit: Limit) -> LimitOut:
    return LimitOut(
        key=limit.key,
        kind=limit.kind,
        building_kind=limit.building_kind,
        status=limit.status,
        reason=limit.reason,
        value=limit.value,
        params=limit.params,
        citation=_citation_out(limit.citation),
        derived_from=limit.derived_from,
    )


def _part_out(part: PartResult, origin: tuple[float, float]) -> PartOut:
    heights = part.heights
    return PartOut(
        zone_code=part.zone_code,
        zone_status=part.zone_status,
        reason=part.reason,
        area_m2=part.area_m2,
        share=part.share,
        rings_local=local_coords.rings(part.geometry, origin),
        excluded=part.excluded,
        limits=[_limit_out(limit) for limit in part.limits],
        hints=[
            LimitOut(
                key=hint.kind,
                kind=hint.kind,
                building_kind=hint.building_kind,
                status=hint.status,
                params=dict(hint.params),
                citation=_citation_out(hint.citation),
            )
            for hint in part.hints
        ],
        heights=HeightsOut(
            eave_m=heights.eave_m,
            ridge_m=heights.ridge_m,
            parapet_m=heights.parapet_m,
            storeys=heights.storeys,
            reference=heights.reference,
            measured_at=heights.measured_at,
            assumptions=heights.assumptions,
        ),
    )


def _edge_out(edge: EdgeResult, origin: tuple[float, float]) -> EnvelopeEdgeOut:
    coords = local_coords.lines(edge.geometry, origin)
    return EnvelopeEdgeOut(
        seq=edge.seq,
        ring=edge.ring,
        kind=edge.kind,
        classification_source=edge.classification_source,
        confidence=edge.confidence,
        length_m=edge.length_m,
        normal_azimuth_deg=edge.normal_azimuth_deg,
        street_name=edge.street_name,
        coords_local=coords[0] if coords else [],
        lenient_m=edge.lenient_m,
        strict_m=edge.strict_m,
        setbacks=[
            SetbackOut(
                zone_code=s.zone_code,
                kind=s.kind,
                building_kind=s.building_kind,
                status=s.status,
                reason=s.reason,
                lenient_m=s.lenient_m,
                strict_m=s.strict_m,
                params=s.params,
                citation=_citation_out(s.citation),
                markers=s.markers,
            )
            for s in edge.setbacks
        ],
        markers=edge.markers,
    )


def _band_out(band: Band, origin: tuple[float, float]) -> BandOut:
    from app.envelope.domain.bands import restriction

    return BandOut(
        edge_seq=band.edge_seq,
        zone_code=band.zone_code,
        min_m=band.min_m,
        max_m=band.max_m,
        band=band.band,
        limits_area={reading: restriction([band], reading) is not None for reading in ("lenient", "strict")},
        rings_local=local_coords.rings(band.polygon, origin),
    )


def _constraint_out(item: Any, origin: tuple[float, float]) -> ConstraintOut:
    return ConstraintOut(
        effect=item.effect,
        category=item.category,
        type_code=item.type_code,
        label=item.label,
        endpoint=item.endpoint,
        area_m2=item.area_m2,
        rings_local=local_coords.rings(item.geometry, origin),
        lines_local=local_coords.lines(item.geometry, origin),
    )


# ---------------------------------------------------------------------------
# Steckbrief
# ---------------------------------------------------------------------------


def sheet_key(project_id: uuid.UUID, input_hash: str) -> str:
    return f"{SHEET_PREFIX}/{project_id}/{input_hash.removeprefix('sha256:')}.pdf"


def stored_sheet(db: Session, project_id: uuid.UUID, input_hash: str) -> EnvelopeSheet | None:
    return db.execute(
        select(EnvelopeSheet).where(
            EnvelopeSheet.project_id == project_id, EnvelopeSheet.input_hash == input_hash
        )
    ).scalar_one_or_none()


def request_sheet(db: Session, project_id: uuid.UUID, actor: str | None = None) -> SheetOut:
    """Steckbrief liefern oder erzeugen lassen. Für denselben Eingabestand entsteht er nur einmal.

    Für Weg E (freies Zeichnen, Plan 3.3) gibt es keinen Steckbrief: ohne Baurahmen keine Simulation,
    die er zusammenfassen könnte (D13)."""
    site = site_service.envelope_site(db, project_id)
    if site.origin == "manual_sketch":
        raise Problem(409, "sheet_unavailable_manual_sketch")
    data, _rules = envelope_input(db, project_id, site=site)
    input_hash = fingerprint(data)
    existing = stored_sheet(db, project_id, input_hash)
    if existing is not None:
        return SheetOut(status="ready", input_hash=input_hash, created_at=existing.generated_at)
    job_id = enqueue(
        db,
        "envelope_sheet",
        {"project_id": str(project_id), "input_hash": input_hash},
        idempotency_key=f"envelope_sheet:{project_id}:{input_hash}",
        created_by=actor,
    )
    db.commit()
    return SheetOut(status="pending", input_hash=input_hash, job_id=job_id)


def sheet_bytes(db: Session, project_id: uuid.UUID) -> tuple[bytes, str]:
    """Fertiger Steckbrief zum aktuellen Eingabestand; sonst 409 mit Hinweis auf den Auftrag."""
    from app.platform import storage

    site = site_service.envelope_site(db, project_id)
    if site.origin == "manual_sketch":
        raise Problem(409, "sheet_unavailable_manual_sketch")
    data, _rules = envelope_input(db, project_id, site=site)
    input_hash = fingerprint(data)
    sheet = stored_sheet(db, project_id, input_hash)
    if sheet is None:
        raise Problem(409, "sheet_not_ready", input_hash=input_hash)
    return storage.get_bytes(sheet.storage_key), input_hash
