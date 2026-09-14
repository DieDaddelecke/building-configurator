"""Anwendungsfälle des Moduls G2 (Plan 3.4). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Kunden sehen die aktuelle Version jedes Regelwerks sofort als Simulation (D11). Korrekturen des Büros sind
freiwillig: für die Zone (neue Version `office_reviewed`) oder nur für ein Projekt (`project_rule_override`).
"""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.problems import Problem
from app.rules.domain import ENGINE_VERSION
from app.rules.domain.assess import coverage as count_coverage
from app.rules.domain.kinds import ParamProblem, validate_params
from app.rules.extract import month_cost
from app.rules.models import (
    LandUsePlan,
    ProjectRuleOverride,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
)
from app.rules.schemas import (
    ChapterCoverageOut,
    CommuneCoverageOut,
    CoverageOut,
    IgnoredZoneOut,
    OverlayOut,
    PlanOut,
    ProjectOverrideIn,
    ProjectOverrideOut,
    ProjectRulesOut,
    RuleDetailOut,
    RuleOut,
    RuleSetOut,
    RuleSetVersionIn,
    VersionOut,
    ZoneRulesOut,
)
from app.site import service as site_service

FEATURE_FLAG = "rules_simulation"
SLIVER_MIN_M2 = 1.0
SLIVER_MIN_SHARE = 0.01
"""Teilflächen unter 1 m² oder 1 % der Grundstücksfläche werden ignoriert (Spez. 5.2.2)."""
LINE_OVERLAY_DISTANCE_M = 1.0
"""Linienhafte Vorgaben (z. B. Baulinie) liegen oft genau auf der Grenze; bis 1 m gelten sie als betroffen."""
NOTICES = ["notice.rules_simulation", "notice.rules_lotissement"]


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def _plan_out(db: Session, plan: LandUsePlan) -> PlanOut:
    source = db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars().first()
    return PlanOut(
        id=plan.id,
        title=plan.title,
        du_type=plan.du_type,
        gpu_doc_id=plan.gpu_doc_id,
        gpu_update_date=plan.gpu_update_date,
        regulation_url=source.url if source else None,
    )


def _version_out(version: RuleSetVersion) -> VersionOut:
    return VersionOut(
        id=version.id,
        version=version.version,
        status=version.status,
        origin=version.origin,
        model=version.model,
        created_at=version.created_at,
        created_by=version.created_by,
        note=version.note,
        coverage=version.coverage or {},
    )


def _source_url(urls: dict[uuid.UUID, str], file_id: uuid.UUID | None, page: int | None) -> str | None:
    if file_id is None or file_id not in urls:
        return None
    return f"{urls[file_id]}#page={page}" if page else urls[file_id]


def _rule_out(rule: Rule, urls: dict[uuid.UUID, str]) -> RuleOut:
    return RuleOut(
        kind=rule.kind,
        building_kind=rule.building_kind,
        status=rule.status,
        reason=rule.reason,
        params=rule.params or {},
        page=rule.page,
        quote=rule.quote,
        quote_verified=rule.quote_verified,
        source_url=_source_url(urls, rule.source_file_id, rule.page),
        confidence=rule.confidence,
        notes=rule.notes,
        origin=rule.origin,
    )


def _override_out(override: ProjectRuleOverride) -> RuleOut:
    return RuleOut(
        kind=override.kind,
        building_kind=override.building_kind,
        status=override.status,
        reason=None,
        params=override.params or {},
        page=None,
        quote=None,
        quote_verified=False,
        source_url=None,
        confidence=1.0,
        notes=override.note,
        origin="project",
    )


def _validated(kind: str, status: str, params: dict[str, Any]) -> dict[str, Any]:
    if status == "effective" or kind == "text_only":
        try:
            return validate_params(kind, params)
        except ParamProblem as problem:
            raise Problem(422, "rule_params_invalid", detail=problem.detail) from None
    return {}


# ---------------------------------------------------------------------------
# Kunde
# ---------------------------------------------------------------------------


def project_rules(db: Session, project_id: uuid.UUID) -> ProjectRulesOut:
    footprint = site_service.site_footprint(db, project_id)
    if footprint is None:
        raise Problem(404, "site_not_found")
    commune = footprint.commune_insees[0] if footprint.commune_insees else None
    warnings: list[str] = []
    if len(footprint.commune_insees) > 1:
        warnings.append("multiple_communes")
    state = db.get(RulesCommune, commune) if commune else None
    plan = db.get(LandUsePlan, state.land_use_plan_id) if state and state.land_use_plan_id else None
    if state is None or state.status != "ok" or plan is None or plan.status != "active":
        unavailable = state.status if state is not None and state.status != "ok" else "not_imported"
        return ProjectRulesOut(
            status="unavailable",
            reason=unavailable,
            commune_insee=commune,
            plan=None,
            zones=[],
            ignored_zones=[],
            overlays=[],
            warnings=warnings,
            notices=NOTICES,
        )

    rows = db.execute(
        text(
            """
            WITH s AS (SELECT ST_GeomFromWKB(:wkb, 2154) AS g)
            SELECT z.code, max(z.label) AS label, max(z.chapter_code) AS chapter_code,
                   ST_Area(ST_Union(ST_Intersection(z.geometry, s.g))) AS area
            FROM zone z, s
            WHERE z.land_use_plan_id = :plan AND z.geometry && s.g AND ST_Intersects(z.geometry, s.g)
            GROUP BY z.code
            ORDER BY area DESC
            """
        ),
        {"wkb": footprint.wkb, "plan": plan.id},
    ).all()
    site_area = footprint.area_m2 or 1.0
    relevant = [r for r in rows if r.area >= SLIVER_MIN_M2 and r.area >= SLIVER_MIN_SHARE * site_area]
    ignored = [
        IgnoredZoneOut(code=r.code, area_m2=round(float(r.area), 2)) for r in rows if r not in relevant
    ]
    if len(relevant) > 1:
        warnings.append("multiple_zones")

    codes = [r.code for r in relevant]
    rule_sets = {
        rs.zone_code: rs
        for rs in db.execute(
            select(RuleSet).where(RuleSet.land_use_plan_id == plan.id, RuleSet.zone_code.in_(codes))
        ).scalars()
    }
    versions = {
        v.id: v
        for v in db.execute(
            select(RuleSetVersion).where(
                RuleSetVersion.id.in_(
                    [rs.current_version_id for rs in rule_sets.values() if rs.current_version_id]
                )
            )
        ).scalars()
    }
    rules_by_version: dict[uuid.UUID, list[Rule]] = defaultdict(list)
    for rule in db.execute(
        select(Rule)
        .where(Rule.rule_set_version_id.in_(list(versions)))
        .order_by(Rule.kind, Rule.building_kind)
    ).scalars():
        rules_by_version[rule.rule_set_version_id].append(rule)
    chapters = {
        c.code: c
        for c in db.execute(
            select(RegulationChapter).where(RegulationChapter.land_use_plan_id == plan.id)
        ).scalars()
    }
    overrides: dict[str, list[ProjectRuleOverride]] = defaultdict(list)
    for override in db.execute(
        select(ProjectRuleOverride).where(ProjectRuleOverride.project_id == project_id)
    ).scalars():
        overrides[override.zone_code].append(override)
    urls = {
        f.id: f.url
        for f in db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars()
    }

    zones: list[ZoneRulesOut] = []
    for row in relevant:
        rule_set = rule_sets.get(row.code)
        version = (
            versions.get(rule_set.current_version_id) if rule_set and rule_set.current_version_id else None
        )
        chapter = chapters.get(row.chapter_code) if row.chapter_code else None
        status: str
        reason: str | None = None
        if version is not None:
            status = version.status
            if chapter is not None and chapter.status in ("pending", "extracting"):
                warnings.append("rules_updating")
        elif chapter is None:
            status, reason = "unavailable", "chapter_not_found"
        elif chapter.status in ("pending", "extracting"):
            status = "in_progress"
        else:
            status, reason = "unavailable", chapter.error or chapter.status
        rules = [_rule_out(r, urls) for r in rules_by_version.get(version.id, [])] if version else []
        for override in overrides.get(row.code, []):
            rules = [
                r
                for r in rules
                if not (r.kind == override.kind and r.building_kind == override.building_kind)
            ]
            rules.append(_override_out(override))
        zones.append(
            ZoneRulesOut(
                code=row.code,
                label=row.label,
                chapter_code=row.chapter_code,
                area_m2=round(float(row.area), 2),
                share=round(float(row.area) / site_area, 4),
                status=status,
                reason=reason,
                rule_set_id=rule_set.id if rule_set else None,
                version=_version_out(version) if version else None,
                rules=[r for r in rules if r.status != "text_only"],
                hints=[r for r in rules if r.status == "text_only"],
            )
        )

    overlay_rows = db.execute(
        text(
            """
            WITH s AS (SELECT ST_GeomFromWKB(:wkb, 2154) AS g)
            SELECT DISTINCT o.category, o.type_code, o.label, o.endpoint
            FROM overlay_constraint o, s
            WHERE o.land_use_plan_id = :plan AND o.commune_insee = :commune
              AND ST_DWithin(o.geometry, s.g, :distance)
              AND (GeometryType(o.geometry) NOT LIKE '%POLYGON%' OR ST_Intersects(o.geometry, s.g))
            ORDER BY o.category, o.label
            """
        ),
        {"wkb": footprint.wkb, "plan": plan.id, "commune": commune, "distance": LINE_OVERLAY_DISTANCE_M},
    ).all()
    statuses = {z.status for z in zones}
    if not zones:
        overall, overall_reason = "unavailable", "no_zone"
    elif statuses <= {"simulated", "office_reviewed"}:
        overall, overall_reason = "ok", None
    elif "in_progress" in statuses and not statuses & {"simulated", "office_reviewed"}:
        overall, overall_reason = "in_progress", None
    elif statuses & {"simulated", "office_reviewed"}:
        overall, overall_reason = "partial", None
    else:
        overall, overall_reason = "unavailable", zones[0].reason
    return ProjectRulesOut(
        status=overall,
        reason=overall_reason,
        commune_insee=commune,
        plan=_plan_out(db, plan),
        zones=zones,
        ignored_zones=ignored,
        overlays=[
            OverlayOut(category=r.category, type_code=r.type_code, label=r.label, endpoint=r.endpoint)
            for r in overlay_rows
        ],
        warnings=sorted(set(warnings)),
        notices=NOTICES,
    )


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


def coverage(db: Session, settings: Settings) -> CoverageOut:
    communes: list[CommuneCoverageOut] = []
    states = {s.commune_insee: s for s in db.execute(select(RulesCommune)).scalars()}
    for insee in sorted(set(settings.cadastre_communes) | set(states)):
        state = states.get(insee)
        plan = db.get(LandUsePlan, state.land_use_plan_id) if state and state.land_use_plan_id else None
        chapters_out: list[ChapterCoverageOut] = []
        if plan is not None:
            chapters = list(
                db.execute(
                    select(RegulationChapter)
                    .where(RegulationChapter.land_use_plan_id == plan.id)
                    .order_by(RegulationChapter.first_page)
                ).scalars()
            )
            run_stats = {
                row.chapter_id: row
                for row in db.execute(
                    select(
                        RuleExtractionRun.chapter_id,
                        func.count().label("runs"),
                        func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0).label("cost"),
                        func.max(RuleExtractionRun.model).label("model"),
                    )
                    .where(RuleExtractionRun.chapter_id.in_([c.id for c in chapters]))
                    .group_by(RuleExtractionRun.chapter_id)
                ).all()
            }
            sets = list(db.execute(select(RuleSet).where(RuleSet.land_use_plan_id == plan.id)).scalars())
            current = {
                v.id: v
                for v in db.execute(
                    select(RuleSetVersion).where(
                        RuleSetVersion.id.in_([s.current_version_id for s in sets if s.current_version_id])
                    )
                ).scalars()
            }
            by_zone = {s.zone_code: s for s in sets}
            for chapter in chapters:
                stats = run_stats.get(chapter.id)
                chapters_out.append(
                    ChapterCoverageOut(
                        id=chapter.id,
                        code=chapter.code,
                        title=chapter.title,
                        first_page=chapter.first_page,
                        last_page=chapter.last_page,
                        sectors=chapter.sectors,
                        status=chapter.status,
                        error=chapter.error,
                        updated_at=chapter.updated_at,
                        runs=int(stats.runs) if stats else 0,
                        cost_usd=round(float(stats.cost), 4) if stats else 0.0,
                        last_model=stats.model if stats else None,
                        rule_sets={
                            sector: (
                                _version_out(current[version_id])
                                if sector in by_zone
                                and (version_id := by_zone[sector].current_version_id) is not None
                                and version_id in current
                                else None
                            )
                            for sector in chapter.sectors
                        },
                        rule_set_ids={s: by_zone[s].id for s in chapter.sectors if s in by_zone},
                    )
                )
        communes.append(
            CommuneCoverageOut(
                commune_insee=insee,
                status=state.status if state else "not_imported",
                error=state.error if state else None,
                checked_at=state.checked_at if state else None,
                plan=_plan_out(db, plan) if plan else None,
                chapters=chapters_out,
            )
        )
    return CoverageOut(
        configured=settings.anthropic_api_key is not None,
        model=settings.rules_model,
        month_cost_usd=round(month_cost(db), 2),
        budget_month_usd=settings.rules_budget_month_usd,
        communes=communes,
    )


def rule_set_detail(db: Session, rule_set_id: uuid.UUID) -> RuleSetOut:
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise Problem(404, "not_found")
    plan = db.get(LandUsePlan, rule_set.land_use_plan_id)
    assert plan is not None
    versions = list(
        db.execute(
            select(RuleSetVersion)
            .where(RuleSetVersion.rule_set_id == rule_set.id)
            .order_by(RuleSetVersion.version.desc())
        ).scalars()
    )
    current = next((v for v in versions if v.id == rule_set.current_version_id), None)
    urls = {
        f.id: f.url
        for f in db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars()
    }
    rules = (
        list(
            db.execute(
                select(Rule).where(Rule.rule_set_version_id == current.id).order_by(Rule.kind)
            ).scalars()
        )
        if current
        else []
    )
    return RuleSetOut(
        id=rule_set.id,
        zone_code=rule_set.zone_code,
        plan=_plan_out(db, plan),
        current=_version_out(current) if current else None,
        versions=[_version_out(v) for v in versions],
        rules=[
            RuleDetailOut(
                **_rule_out(r, urls).model_dump(),
                detail=r.detail,
                alternatives=r.alternatives or [],
                similarity=r.similarity,
            )
            for r in rules
        ],
    )


def create_office_version(
    db: Session, rule_set_id: uuid.UUID, body: RuleSetVersionIn, actor_id: str
) -> RuleSetOut:
    """Korrektur des Büros für die Zone: neue, vollständige Version; gilt für spätere Simulationen."""
    rule_set = db.execute(
        select(RuleSet).where(RuleSet.id == rule_set_id).with_for_update()
    ).scalar_one_or_none()
    if rule_set is None:
        raise Problem(404, "not_found")
    keys = [(r.kind, r.building_kind) for r in body.rules if r.status != "text_only"]
    if len(keys) != len(set(keys)):
        raise Problem(422, "rule_duplicate")
    current = db.get(RuleSetVersion, rule_set.current_version_id) if rule_set.current_version_id else None
    source = (
        db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == rule_set.land_use_plan_id))
        .scalars()
        .first()
    )
    number = (
        db.execute(
            select(func.coalesce(func.max(RuleSetVersion.version), 0)).where(
                RuleSetVersion.rule_set_id == rule_set.id
            )
        ).scalar_one()
        + 1
    )
    prepared = [(item, _validated(item.kind, item.status, item.params)) for item in body.rules]
    version = RuleSetVersion(
        rule_set_id=rule_set.id,
        version=number,
        status="office_reviewed",
        origin="office",
        based_on_id=current.id if current else None,
        engine_version=ENGINE_VERSION,
        note=body.note,
        created_by=actor_id,
    )
    db.add(version)
    db.flush()
    stored: list[Rule] = []
    for item, params in prepared:
        rule = Rule(
            rule_set_version_id=version.id,
            kind=item.kind,
            building_kind=item.building_kind,
            status=item.status,
            params=params if item.status == "effective" or item.kind == "text_only" else {},
            source_file_id=source.id if source and item.page else None,
            page=item.page,
            quote=item.quote,
            quote_verified=False,
            confidence=1.0,
            notes=item.notes,
            origin="office",
            created_by=actor_id,
        )
        db.add(rule)
        stored.append(rule)
    version.coverage = count_coverage(stored)
    if current is not None:
        current.status = "retired"
    rule_set.current_version_id = version.id
    rule_set.updated_at = utcnow()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="rule_set.office_version",
        entity_type="rule_set",
        entity_id=str(rule_set.id),
        before={"version": current.version if current else None},
        after={"version": number, "rules": len(stored), "note": body.note},
    )
    db.commit()
    return rule_set_detail(db, rule_set.id)


def list_overrides(db: Session, project_id: uuid.UUID) -> list[ProjectOverrideOut]:
    return [
        ProjectOverrideOut(
            id=o.id,
            zone_code=o.zone_code,
            kind=o.kind,
            building_kind=o.building_kind,
            status=o.status,
            params=o.params or {},
            note=o.note,
            updated_at=o.updated_at,
            updated_by=o.updated_by,
        )
        for o in db.execute(
            select(ProjectRuleOverride)
            .where(ProjectRuleOverride.project_id == project_id)
            .order_by(ProjectRuleOverride.zone_code, ProjectRuleOverride.kind)
        ).scalars()
    ]


def set_override(
    db: Session, project_id: uuid.UUID, body: ProjectOverrideIn, actor_id: str
) -> list[ProjectOverrideOut]:
    if site_service.site_footprint(db, project_id) is None:
        raise Problem(404, "site_not_found")
    params = _validated(body.kind, body.status, body.params)
    existing = db.execute(
        select(ProjectRuleOverride)
        .where(
            ProjectRuleOverride.project_id == project_id,
            ProjectRuleOverride.zone_code == body.zone_code,
            ProjectRuleOverride.kind == body.kind,
            ProjectRuleOverride.building_kind == body.building_kind,
        )
        .with_for_update()
    ).scalar_one_or_none()
    before = {"status": existing.status, "params": existing.params} if existing else None
    if existing is None:
        existing = ProjectRuleOverride(
            project_id=project_id,
            zone_code=body.zone_code,
            kind=body.kind,
            building_kind=body.building_kind,
            status=body.status,
            created_by=actor_id,
        )
        db.add(existing)
    existing.status = body.status
    existing.params = params
    existing.note = body.note
    existing.updated_at = utcnow()
    existing.updated_by = actor_id
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="project_rule_override.put",
        entity_type="project",
        entity_id=str(project_id),
        before=before,
        after={
            "zone": body.zone_code,
            "kind": body.kind,
            "building_kind": body.building_kind,
            "status": body.status,
            "params": params,
        },
    )
    db.commit()
    return list_overrides(db, project_id)


def delete_override(
    db: Session, project_id: uuid.UUID, override_id: uuid.UUID, actor_id: str
) -> list[ProjectOverrideOut]:
    override = db.get(ProjectRuleOverride, override_id)
    if override is None or override.project_id != project_id:
        raise Problem(404, "not_found")
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="project_rule_override.delete",
        entity_type="project",
        entity_id=str(project_id),
        before={"zone": override.zone_code, "kind": override.kind, "status": override.status},
    )
    db.delete(override)
    db.commit()
    return list_overrides(db, project_id)


def enqueue_import(db: Session, communes: list[str] | None, force: bool, actor_id: str) -> uuid.UUID:
    import app.rules.jobs  # noqa: F401  Jobarten anmelden (lokal, sonst Importzyklus)

    job_id = enqueue(db, "plu_import", {"communes": communes, "force": force}, created_by=actor_id)
    db.commit()
    return job_id


def enqueue_extract(db: Session, chapter_id: uuid.UUID, force: bool, actor_id: str) -> uuid.UUID:
    import app.rules.jobs  # noqa: F401

    chapter = db.get(RegulationChapter, chapter_id)
    if chapter is None:
        raise Problem(404, "not_found")
    chapter.status, chapter.updated_at = "pending", utcnow()
    job_id = enqueue(
        db, "rules_extract", {"chapter_id": str(chapter_id), "force": force}, created_by=actor_id
    )
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="regulation_chapter.extract",
        entity_type="regulation_chapter",
        entity_id=str(chapter_id),
        after={"force": force},
    )
    db.commit()
    return job_id
