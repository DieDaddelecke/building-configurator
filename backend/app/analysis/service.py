"""Anwendungsfälle des Moduls AN3 (docs/PLAN_AN3_ANALYSE.md 3.9).

Die Analyse wird bei jedem Abruf aus Baurahmen (G3), Regeln (G2) und den Annahmen des Projekts gerechnet,
wie der Baurahmen selbst (Plan G3 11.1 Nr. 1). Die Prüfsumme benennt den Eingabestand für den Bericht (AN5).
Seit AN4 auch für einen anderen Stand der Regeln – ohne Korrekturen oder mit einer früheren Auswertung –,
um zwei Stände nebeneinanderzustellen (docs/PLAN_AN4_KORREKTUR.md 3.5).
"""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.analysis.domain import ENGINE_VERSION
from app.analysis.domain.analyse import Analysis, PartAnalysis, SupplementInput, SupplementResult, analyse
from app.analysis.domain.floor_area import NOT_COUNTED, StoreyArea
from app.analysis.domain.footprint import Footprint
from app.analysis.domain.gabarit import Gabarit
from app.analysis.domain.parameters import DEFAULTS, Parameters
from app.analysis.domain.section import Section
from app.analysis.models import AnalysisParameters
from app.analysis.schemas import (
    AnalysisAssumptionsOut,
    AnalysisComparisonOut,
    AnalysisFloorAreaOut,
    AnalysisFootprintOut,
    AnalysisOut,
    AnalysisParametersIn,
    AnalysisParametersOut,
    AnalysisPartOut,
    AnalysisStoreysOut,
    ComparisonBaseOut,
    ComparisonFigureOut,
    ComparisonRuleOut,
    ComparisonStateOut,
    FloorAreaTotalOut,
    FootprintCandidateOut,
    FootprintTotalOut,
    GabaritContourOut,
    GabaritHeightsOut,
    GabaritLevelOut,
    GabaritOut,
    RuleComparisonOut,
    SectionOut,
    SpanOut,
    StoreyAreaOut,
    SupplementAnalysisOut,
)
from app.envelope import service as envelope_service
from app.envelope.domain import local as local_coords
from app.envelope.domain.derive import ZONE_WITHOUT_RULES, Envelope
from app.envelope.domain.inputs import Citation, EnvelopeInput, RuleInput
from app.envelope.schemas import CitationOut, LimitOut
from app.platform import audit
from app.platform.db import utcnow
from app.platform.problems import Problem
from app.rules import service as rules_service
from app.rules.domain.kinds import params_equal
from app.rules.schemas import RuleOut, VersionOut

# ---------------------------------------------------------------------------
# Annahmen
# ---------------------------------------------------------------------------


def _stored(db: Session, project_id: uuid.UUID) -> AnalysisParameters | None:
    return db.get(AnalysisParameters, project_id)


def parameters(db: Session, project_id: uuid.UUID) -> Parameters:
    row = _stored(db, project_id)
    return Parameters.from_json(row.params) if row is not None else DEFAULTS


def save_parameters(db: Session, project_id: uuid.UUID, body: AnalysisParametersIn, actor: str) -> None:
    value = Parameters.from_json({name: [span.low, span.high] for name, span in body}).as_json()
    row = _stored(db, project_id)
    before = row.params if row is not None else None
    if row is None:
        db.add(AnalysisParameters(project_id=project_id, params=value, updated_by=actor))
    else:
        row.params, row.updated_at, row.updated_by = value, utcnow(), actor
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="analysis.parameters",
        entity_type="project",
        entity_id=str(project_id),
        before=before,
        after=value,
    )
    db.commit()


def reset_parameters(db: Session, project_id: uuid.UUID, actor: str) -> None:
    row = _stored(db, project_id)
    if row is None:
        return
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor,
        action="analysis.parameters_reset",
        entity_type="project",
        entity_id=str(project_id),
        before=row.params,
    )
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def _rule_input(rule: RuleOut) -> RuleInput:
    return RuleInput(
        kind=rule.kind,
        building_kind=rule.building_kind,
        status=rule.status,
        reason=rule.reason,
        params=dict(rule.params),
        citation=Citation(
            page=rule.page,
            quote=rule.quote,
            quote_verified=rule.quote_verified,
            source_url=rule.source_url,
            origin=rule.origin,
            confidence=rule.confidence,
            notes=rule.notes,
            document_id=str(rule.source_document_id) if rule.source_document_id else None,
        ),
    )


def _supplements(db: Session, project_id: uuid.UUID) -> tuple[list[SupplementInput], list[str]]:
    """Zusatzdokumente als Eingabe der Analyse und ihr Regelstand für die Prüfsumme."""
    items = rules_service.supplement_rules(db, project_id)
    inputs = [
        SupplementInput(
            document_id=str(item.document_id),
            title=item.title,
            du_type=item.du_type,
            lot=item.lot,
            status=item.status,
            reason=item.reason,
            rules=[_rule_input(rule) for rule in item.rules],
            hints=[_rule_input(rule) for rule in item.hints],
            updating=item.updating,
        )
        for item in items
    ]
    stamps = [f"{item.document_id}:{item.lot}:{item.status}:{item.version_id}" for item in items]
    return inputs, stamps


def project_analysis(db: Session, project_id: uuid.UUID) -> AnalysisOut:
    data, envelope = envelope_service.derived(db, project_id)
    params = parameters(db, project_id)
    supplements, stamps = _supplements(db, project_id)
    result = analyse(data, envelope, params, supplements)
    raw = json.dumps(
        [ENGINE_VERSION, envelope_service.fingerprint(data), params.as_json(), stamps], sort_keys=True
    )
    return _out(result, params, data, custom=_stored(db, project_id) is not None, input_hash=raw)


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------


def _citation(citation: Citation | None) -> CitationOut | None:
    if citation is None:
        return None
    origin: Literal["extraction", "office", "project"] = (
        "office"
        if citation.origin == "office"
        else "project"
        if citation.origin == "project"
        else "extraction"
    )
    return CitationOut(
        page=citation.page,
        quote=citation.quote,
        quote_verified=citation.quote_verified,
        source_url=citation.source_url,
        origin=origin,
        confidence=citation.confidence,
        notes=citation.notes,
    )


def _limit(rule: RuleInput) -> LimitOut:
    return LimitOut(
        key=rule.kind,
        kind=rule.kind,
        building_kind=rule.building_kind,
        status="text_only" if rule.status == "text_only" else rule.status,
        reason=rule.reason,
        params=dict(rule.params),
        citation=_citation(rule.citation),
    )


def _parameters_out(params: Parameters) -> AnalysisParametersOut:
    return AnalysisParametersOut(
        **{name: SpanOut(low=span["low"], high=span["high"]) for name, span in asdict(params).items()}
    )


def _footprint_out(footprint: Footprint) -> AnalysisFootprintOut:
    return AnalysisFootprintOut(
        value_m2=footprint.value_m2,
        binding=footprint.binding,
        complete=footprint.complete,
        reasons=footprint.reasons,
        candidates=[
            FootprintCandidateOut(
                source=c.source, value_m2=c.value_m2, status=c.status, citation=_citation(c.citation)
            )
            for c in footprint.candidates
        ],
    )


def _part_out(part: PartAnalysis) -> AnalysisPartOut:
    storeys, floor = part.storeys, part.floor_area
    return AnalysisPartOut(
        zone_code=part.zone_code,
        area_m2=part.area_m2,
        excluded=part.excluded,
        footprint={reading: _footprint_out(fp) for reading, fp in part.footprint.items()},
        storeys=AnalysisStoreysOut(
            full_min=storeys.full_min,
            full_max=storeys.full_max,
            top=storeys.top,
            top_certain=storeys.top_certain,
            source=storeys.source,
            status=storeys.status,
            citation=_citation(storeys.citation),
            notes=storeys.notes,
        ),
        floor_area=AnalysisFloorAreaOut(
            low_m2=floor.low_m2,
            high_m2=floor.high_m2,
            cap_m2=floor.cap_m2,
            capped=floor.capped,
            complete=floor.complete,
            reasons=floor.reasons,
            cap_citation=_citation(floor.cap_citation),
            storeys_low=[_storey_out(s) for s in floor.storeys_low],
            storeys_high=[_storey_out(s) for s in floor.storeys_high],
            notes=floor.notes,
        ),
    )


def _storey_out(storey: StoreyArea) -> StoreyAreaOut:
    return StoreyAreaOut(level_m=storey.level_m, area_m2=storey.area_m2, share=storey.share)


def _gabarit_out(hull: Gabarit, data: EnvelopeInput) -> GabaritOut:
    origin = data.site.local_origin
    status: Literal["ok", "partial", "unavailable"] = (
        "ok" if hull.status == "ok" else "partial" if hull.status == "partial" else "unavailable"
    )
    return GabaritOut(
        status=status,
        reason=hull.reason,
        top_m=hull.top_m,
        storey_height_m=hull.storey_height_m,
        reasons=hull.reasons,
        heights=[
            GabaritHeightsOut(
                zone_code=zone,
                eave_m=heights.eave_m,
                ridge_m=heights.ridge_m,
                parapet_m=heights.parapet_m,
                derived=bool(heights.assumptions),
            )
            for zone, heights in hull.heights.items()
        ],
        levels=[
            GabaritLevelOut.model_validate(
                {
                    "from_m": level.from_m,
                    "to_m": level.to_m,
                    "roof": level.roof,
                    "contours": {
                        reading: GabaritContourOut(
                            rings_local=local_coords.rings(contour.geometry, origin),
                            area_m2=contour.area_m2,
                            complete=contour.complete,
                            reasons=contour.reasons,
                        )
                        for reading, contour in level.contours.items()
                    },
                }
            )
            for level in hull.levels
        ],
        terrain_status=data.site.terrain.status,
        terrain_slope_percent=data.site.terrain.slope_percent,
    )


def _section_out(section: Section, origin: tuple[float, float]) -> SectionOut:
    """Die Fachlogik trägt Schlüssel, Arten und Auslegungen als Text; die Prüfung übernimmt Pydantic."""
    return SectionOut.model_validate(
        {
            "key": section.key,
            "start_local": local_coords.point(section.start, origin),
            "end_local": local_coords.point(section.end, origin),
            "length_m": section.length_m,
            "parcel": [list(interval) for interval in section.parcel],
            "crossings": [asdict(crossing) for crossing in section.crossings],
            "levels": [
                {
                    "from_m": level.from_m,
                    "to_m": level.to_m,
                    "roof": level.roof,
                    "intervals": {r: [list(i) for i in items] for r, items in level.intervals.items()},
                }
                for level in section.levels
            ],
            "height_lines": [asdict(line) for line in section.height_lines],
            "prospects": [
                {"edge_seq": p.edge_seq, "reading": p.reading, "points": [list(x) for x in p.points]}
                for p in section.prospects
            ],
        }
    )


def _supplement_out(result: SupplementResult) -> SupplementAnalysisOut:
    source = result.source
    return SupplementAnalysisOut(
        document_id=uuid.UUID(source.document_id),
        title=source.title,
        du_type=source.du_type,
        lot=source.lot,
        status=source.status,
        reason=source.reason,
        updating=source.updating,
        comparisons=[
            RuleComparisonOut(
                kind=c.kind,
                building_kind=c.building_kind,
                verdict=c.verdict,
                supplement=_limit(c.supplement),
                plu=_limit(c.plu) if c.plu is not None else None,
                details=c.details,
                proposal=c.proposal,
            )
            for c in result.comparisons
        ],
        hints=[_limit(hint) for hint in source.hints],
    )


def _out(
    result: Analysis, params: Parameters, data: EnvelopeInput, *, custom: bool, input_hash: str
) -> AnalysisOut:
    floor = result.floor_area
    return AnalysisOut(
        status=result.status,
        reason=result.reason,
        engine_version=ENGINE_VERSION,
        input_hash="sha256:" + hashlib.sha256(input_hash.encode()).hexdigest(),
        assumptions=AnalysisAssumptionsOut(
            values=_parameters_out(params), defaults=_parameters_out(DEFAULTS), custom=custom
        ),
        footprint={
            reading: FootprintTotalOut(value_m2=total.value_m2, complete=total.complete)
            for reading, total in result.footprint.items()
        },
        floor_area=(
            FloorAreaTotalOut(
                low_m2=floor.low_m2,
                high_m2=floor.high_m2,
                complete=floor.complete,
                capped=floor.capped,
                reasons=floor.reasons,
            )
            if floor is not None
            else None
        ),
        parts=[_part_out(part) for part in result.parts],
        not_counted=list(NOT_COUNTED),
        supplements=[_supplement_out(item) for item in result.supplements],
        supplement_stricter=result.supplement_stricter,
        warnings=result.warnings,
        gabarit=_gabarit_out(result.gabarit, data) if result.gabarit is not None else None,
        sections=[_section_out(section, data.site.local_origin) for section in result.sections],
    )


# ---------------------------------------------------------------------------
# Zwei Stände vergleichen (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5)
# ---------------------------------------------------------------------------

AUTOMATIC = "automatic"


@dataclass(frozen=True)
class _Offer:
    """Angebotene Vergleiche und je Versions-ID die Zone; dazu die aktuelle Version je Zone."""

    bases: list[ComparisonBaseOut]
    zone_of: dict[str, str]
    current: dict[str, VersionOut]


def _offer(db: Session, project_id: uuid.UUID) -> _Offer:
    """Ohne Korrekturen, wenn eine wirkt; je frühere Version eines Regelwerks einer Zone des Projekts."""
    states = rules_service.rule_states(db, project_id)
    bases = [ComparisonBaseOut(base=AUTOMATIC, kind="corrections")] if states.corrected else []
    bases += [
        ComparisonBaseOut(base=str(version.id), kind="versions", zone_code=zone, version=version)
        for zone, version in states.earlier
    ]
    return _Offer(bases, {str(v.id): zone for zone, v in states.earlier}, states.current)


def _state(
    db: Session, project_id: uuid.UUID, options: rules_service.RulesOptions, params: Parameters
) -> tuple[EnvelopeInput, Envelope | None, Analysis]:
    data, envelope = envelope_service.derived(db, project_id, options)
    return data, envelope, analyse(data, envelope, params, [])


FIGURE_UNITS: dict[str, Literal["m2", "m", "count"]] = {
    "storeys_min": "count",
    "storeys_max": "count",
    "height_top": "m",
}


def _figures(envelope: Envelope | None, result: Analysis) -> dict[str, float | None]:
    """Kennzahlen eines Stands; Geschosse der größten Teilfläche mit Regeln (die Teilflächen kommen nach
    Fläche sortiert)."""
    usable = envelope is not None and envelope.status not in ZONE_WITHOUT_RULES
    contours = envelope.contours if envelope is not None and usable else {}
    part = next((p for p in result.parts if p.excluded is None), None)
    floor = result.floor_area
    footprint = result.footprint
    return {
        "footprint_lenient": footprint["lenient"].value_m2 if footprint else None,
        "footprint_strict": footprint["strict"].value_m2 if footprint else None,
        "contour_lenient": contours["lenient"].area_m2 if contours else None,
        "contour_strict": contours["strict"].area_m2 if contours else None,
        "storeys_min": part.storeys.full_min if part else None,
        "storeys_max": part.storeys.full_max if part else None,
        "floor_area_low": floor.low_m2 if floor else None,
        "floor_area_high": floor.high_m2 if floor else None,
        "height_top": result.gabarit.top_m if result.gabarit else None,
    }


def _reason(rule: RuleInput) -> str | None:
    """Grund einer nicht ermittelten Regel; ohne Grund wie `missing`, so zeigt ihn die Oberfläche. Eine
    Büro-Version kennt keine Gründe; sonst stünde „nicht ermittelt“ links und rechts als Änderung (7.4)."""
    return (rule.reason or "missing") if rule.status == "unknown" else None


def _rule_rows(left: EnvelopeInput, right: EnvelopeInput) -> list[ComparisonRuleOut]:
    """Regeln beider Stände je Zone, Art und Baukörper; ohne Hinweise."""

    def index(data: EnvelopeInput) -> dict[tuple[str, str, str], RuleInput]:
        return {(z.code, r.kind, r.building_kind): r for z in data.zones for r in z.rules}

    before, after = index(left), index(right)
    rows: list[ComparisonRuleOut] = []
    for key in sorted(set(before) | set(after)):
        a, b = before.get(key), after.get(key)
        changed = (
            a is None
            or b is None
            or (a.status, _reason(a)) != (b.status, _reason(b))
            or not params_equal(a.params, b.params)
        )
        rows.append(
            ComparisonRuleOut(
                zone_code=key[0],
                kind=key[1],
                building_kind=key[2],
                left=_limit(a) if a is not None else None,
                right=_limit(b) if b is not None else None,
                changed=changed,
            )
        )
    return rows


def _state_out(
    envelope: Envelope | None, data: EnvelopeInput, *, corrections: bool, version: VersionOut | None
) -> ComparisonStateOut:
    status = envelope.status if envelope is not None else "unavailable"
    return ComparisonStateOut(
        corrections=corrections,
        version=version,
        status=status if status in ("ok", "partial", "in_progress") else "unavailable",
        reason=envelope.reason if envelope is not None else data.rules_reason,
    )


def comparison(db: Session, project_id: uuid.UUID, base: str) -> AnalysisComparisonOut:
    """Zwei Stände nebeneinander (3.5): `automatic` – ohne ↔ mit den Korrekturen des Projekts; eine
    Versions-ID – diese frühere Auswertung ↔ die aktuelle, beide ohne Korrekturen (7.1 Nr. 5)."""
    offer = _offer(db, project_id)
    kind: Literal["corrections", "versions"]
    left_version: VersionOut | None = None
    right_version: VersionOut | None = None
    if base == AUTOMATIC:
        kind = "corrections"
        left_options, right_options = rules_service.RulesOptions(overrides=False), rules_service.CURRENT
    elif base in offer.zone_of:
        kind = "versions"
        zone = offer.zone_of[base]
        left_options = rules_service.RulesOptions(overrides=False, versions={zone: uuid.UUID(base)})
        right_options = rules_service.RulesOptions(overrides=False)
        left_version = next(b.version for b in offer.bases if b.base == base)
        right_version = offer.current.get(zone)
    else:
        raise Problem(404, "version_not_found")
    params = parameters(db, project_id)
    left_data, left_envelope, left = _state(db, project_id, left_options, params)
    right_data, right_envelope, right = _state(db, project_id, right_options, params)
    before, after = _figures(left_envelope, left), _figures(right_envelope, right)
    return AnalysisComparisonOut(
        kind=kind,
        base=base,
        left=_state_out(left_envelope, left_data, corrections=False, version=left_version),
        right=_state_out(
            right_envelope, right_data, corrections=kind == "corrections", version=right_version
        ),
        bases=offer.bases,
        figures=[
            ComparisonFigureOut(
                key=key,
                unit=FIGURE_UNITS.get(key, "m2"),
                left=before[key],
                right=after[key],
                changed=before[key] != after[key],
            )
            for key in before
        ],
        rules=_rule_rows(left_data, right_data),
    )
