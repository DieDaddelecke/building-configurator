"""Arbeitsplatz des Büros im Modul G2: Abdeckung der Gemeinden, Modell der Auswertung, Formulare je Art
und eine Bürofassung für eine Zone (D11; aus `service.py` gelöst, REFACTORING_PLAN S19)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit
from app.platform.db import utcnow
from app.platform.problems import Problem
from app.rules import model_choice
from app.rules.domain import ENGINE_VERSION
from app.rules.domain.assess import coverage as count_coverage
from app.rules.domain.form import kind_forms
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
)
from app.rules.runs import month_cost
from app.rules.schemas import (
    ChapterCoverageOut,
    CommuneCoverageOut,
    CoverageOut,
    ParamFieldOut,
    RuleDetailOut,
    RuleKindFormOut,
    RuleSetOut,
    RuleSetVersionIn,
    RulesModelOut,
)
from app.rules.service import (
    plan_out,
    rule_out,
    scan_pages,
    validated_params,
    version_out,
)


def coverage(db: Session, settings: Settings) -> CoverageOut:
    communes: list[CommuneCoverageOut] = []
    states = {s.commune_insee: s for s in db.execute(select(RulesCommune)).scalars()}
    for insee in sorted(set(settings.cadastre_communes) | set(states)):
        state = states.get(insee)
        plan = db.get(LandUsePlan, state.land_use_plan_id) if state and state.land_use_plan_id else None
        fallback = (
            db.get(LandUsePlan, state.fallback_land_use_plan_id)
            if state and state.fallback_land_use_plan_id
            else None
        )
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
                                version_out(current[version_id])
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
                plan=plan_out(db, plan) if plan else None,
                fallback_plan=plan_out(db, fallback) if fallback else None,
                chapters=chapters_out,
            )
        )
    return CoverageOut(
        configured=settings.openrouter_api_key is not None,
        model=model_choice.effective_settings(db, settings).rules_model,
        month_cost_usd=round(month_cost(db), 2),
        budget_month_usd=settings.rules_budget_month_usd,
        communes=communes,
    )


def rules_model_out(db: Session, settings: Settings) -> RulesModelOut:
    """Eingestelltes KI-Modell mit Preisen, Kosten des Monats und Budget (PLAN_AN2_PLU 8, VA09)."""
    chosen = model_choice.current(db, settings)
    return RulesModelOut(
        model=chosen.model,
        source=chosen.source,
        default_model=chosen.default_model,
        price_input_per_mtok=chosen.price_input_per_mtok,
        price_output_per_mtok=chosen.price_output_per_mtok,
        updated_at=chosen.updated_at,
        input=chosen.input,
        configured=settings.openrouter_api_key is not None,
        month_cost_usd=round(month_cost(db), 2),
        budget_month_usd=settings.rules_budget_month_usd,
        updated_by_name=chosen.updated_by_name,
    )


def rule_kind_forms() -> list[RuleKindFormOut]:
    """Formularbeschreibung aller Regelarten (AN4, docs/PLAN_AN4_KORREKTUR.md 3.1)."""
    return [
        RuleKindFormOut(
            kind=form.kind,
            building_specific=form.building_specific,
            mandatory=form.mandatory,
            params=[
                ParamFieldOut(
                    name=p.name,
                    type=p.type,
                    required=p.required,
                    default=p.default,
                    options=list(p.options),
                    min=p.min,
                    max=p.max,
                    unit=p.unit,
                )
                for p in form.params
            ],
        )
        for form in kind_forms()
    ]


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
    scanned = scan_pages(db, urls)
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
        plan=plan_out(db, plan),
        current=version_out(current) if current else None,
        versions=[version_out(v) for v in versions],
        rules=[
            RuleDetailOut(
                **rule_out(r, urls, plan.id, scanned).model_dump(),
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
        db.execute(
            select(SourceFile)
            .where(SourceFile.land_use_plan_id == rule_set.land_use_plan_id)
            .order_by(SourceFile.created_at.desc())
        )
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
    prepared = [(item, validated_params(item.kind, item.status, item.params)) for item in body.rules]
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
