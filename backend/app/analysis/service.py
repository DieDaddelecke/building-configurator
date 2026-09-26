"""Anwendungsfälle des Moduls AN3 (docs/PLAN_AN3_ANALYSE.md 3.9).

Die Analyse wird bei jedem Abruf aus Baurahmen (G3), Regeln (G2) und den Annahmen des Projekts gerechnet,
wie der Baurahmen selbst (Plan G3 11.1 Nr. 1). Die Prüfsumme benennt den Eingabestand für den Bericht (AN5).
"""

import hashlib
import json
import uuid
from dataclasses import asdict
from typing import Literal

from sqlalchemy.orm import Session

from app.analysis.domain import ENGINE_VERSION
from app.analysis.domain.analyse import Analysis, PartAnalysis, SupplementInput, SupplementResult, analyse
from app.analysis.domain.floor_area import NOT_COUNTED
from app.analysis.domain.footprint import Footprint
from app.analysis.domain.parameters import DEFAULTS, Parameters
from app.analysis.models import AnalysisParameters
from app.analysis.schemas import (
    AnalysisAssumptionsOut,
    AnalysisFloorAreaOut,
    AnalysisFootprintOut,
    AnalysisOut,
    AnalysisParametersIn,
    AnalysisParametersOut,
    AnalysisPartOut,
    AnalysisStoreysOut,
    FloorAreaTotalOut,
    FootprintCandidateOut,
    FootprintTotalOut,
    RuleComparisonOut,
    SpanOut,
    SupplementAnalysisOut,
)
from app.envelope import service as envelope_service
from app.envelope.domain.inputs import Citation, RuleInput
from app.envelope.schemas import CitationOut, LimitOut
from app.platform import audit
from app.platform.db import utcnow
from app.rules import service as rules_service
from app.rules.schemas import RuleOut

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
    return _out(result, params, custom=_stored(db, project_id) is not None, input_hash=raw)


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
        ),
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
            )
            for c in result.comparisons
        ],
        hints=[_limit(hint) for hint in source.hints],
    )


def _out(result: Analysis, params: Parameters, *, custom: bool, input_hash: str) -> AnalysisOut:
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
    )
