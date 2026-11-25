"""Regeldienst: Regeln einer Gemeinde und Zone für andere Dienste lesen (docs/PLAN_REGELDIENST.md 4).

Nur Lesen, ohne Projekt und ohne Kundendaten. Die Route plant nie eine Auswertung ein: Ein Umfang ohne
Auswertung heißt `not_extracted`, und bezahlte Läufe startet nur der Betrieb über die Kommandozeile
(`rules-extract --scope collectif`). Kein Rückgriff auf ältere Planstände: Gilt ein neuer Planstand, der
noch nicht ausgewertet ist, liefert der Dienst keine Regeln des alten.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform.problems import Problem
from app.rules.domain.kinds import SCOPES, RuleScope
from app.rules.domain.resolve import ZoneState, feed_state, zone_state
from app.rules.models import (
    LandUsePlan,
    RegulationChapter,
    RegulationChapterScope,
    Rule,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    Zone,
)
from app.rules.schemas import (
    FeedCommuneOut,
    FeedVersionOut,
    FeedZoneOut,
    FeedZoneRefOut,
    FeedZoneRulesOut,
    FeedZoneStateOut,
    PassageOut,
)
from app.rules.service import NOTICES, plan_out, rule_out, scan_pages

FEED_NOTICES = [*NOTICES, "notice.rules_feed_suggestion"]
"""Die Regeln sind Vorschläge für eine Studie, keine Prüfung des Bauantrags (L7)."""


def _commune(db: Session, insee: str) -> tuple[RulesCommune, LandUsePlan | None]:
    commune = db.get(RulesCommune, insee)
    if commune is None:
        raise Problem(404, "commune_unknown")
    plan = db.get(LandUsePlan, commune.land_use_plan_id) if commune.land_use_plan_id else None
    if plan is not None and plan.status != "active":
        plan = None
    return commune, plan


def _zones(db: Session, plan: LandUsePlan, insee: str) -> dict[str, tuple[str | None, str | None]]:
    """Zonen des Planstands in dieser Gemeinde: Code → (Bezeichnung, Kapitel)."""
    # Eine Zone besteht oft aus mehreren Flächen (`gpu_gid`); Bezeichnung und Kapitel sind dieselben
    rows = db.execute(
        select(Zone.code, func.max(Zone.label), func.max(Zone.chapter_code))
        .where(Zone.land_use_plan_id == plan.id, Zone.commune_insee == insee)
        .group_by(Zone.code)
        .order_by(Zone.code)
    ).tuples()
    return {code: (label, chapter_code) for code, label, chapter_code in rows}


def _state(
    scope: str,
    version: RuleSetVersion | None,
    chapter: RegulationChapter | None,
    extra: RegulationChapterScope | None,
) -> tuple[ZoneState, datetime | None]:
    """Stand der Zone im Umfang und Zeitpunkt seiner letzten Änderung."""
    if scope == "house":
        state = zone_state(
            version.status if version else None,
            chapter.status if chapter else None,
            chapter_error=chapter.error if chapter else None,
        )
        return state, chapter.updated_at if chapter else None
    state = feed_state(
        version.status if version else None,
        extra.status if extra else None,
        chapter_known=chapter is not None,
        state_error=extra.error if extra else None,
    )
    return state, extra.updated_at if extra else None


def commune_overview(db: Session, insee: str) -> FeedCommuneOut:
    commune, plan = _commune(db, insee)
    if plan is None or commune.status != "ok":
        return FeedCommuneOut(
            commune_insee=insee, status=commune.status, reason=commune.error, plan=None, zones=[]
        )
    zones = _zones(db, plan, insee)
    chapters = {
        c.code: c
        for c in db.execute(
            select(RegulationChapter).where(RegulationChapter.land_use_plan_id == plan.id)
        ).scalars()
    }
    extras = {
        (s.chapter_id, s.scope): s
        for s in db.execute(
            select(RegulationChapterScope).where(
                RegulationChapterScope.chapter_id.in_([c.id for c in chapters.values()])
            )
        ).scalars()
    }
    sets = {
        (s.zone_code, s.scope): s
        for s in db.execute(
            select(RuleSet).where(RuleSet.land_use_plan_id == plan.id, RuleSet.zone_code.in_(list(zones)))
        ).scalars()
    }
    versions = {
        v.id: v
        for v in db.execute(
            select(RuleSetVersion).where(
                RuleSetVersion.id.in_([s.current_version_id for s in sets.values() if s.current_version_id])
            )
        ).scalars()
    }
    out: list[FeedZoneOut] = []
    for code, (label, chapter_code) in zones.items():
        chapter = chapters.get(chapter_code) if chapter_code else None
        states: list[FeedZoneStateOut] = []
        for scope in SCOPES:
            rule_set = sets.get((code, scope))
            version = (
                versions.get(rule_set.current_version_id)
                if rule_set and rule_set.current_version_id
                else None
            )
            extra = extras.get((chapter.id, scope)) if chapter else None
            state, updated_at = _state(scope, version, chapter, extra)
            states.append(
                FeedZoneStateOut(
                    scope=scope,
                    status=state.status,
                    reason=state.reason,
                    updated_at=updated_at,
                )
            )
        out.append(FeedZoneOut(code=code, label=label, chapter_code=chapter_code, states=states))
    return FeedCommuneOut(
        commune_insee=insee, status="ok", reason=commune.error, plan=plan_out(db, plan), zones=out
    )


def zone_rules(db: Session, insee: str, zone_code: str, scope: RuleScope) -> FeedZoneRulesOut:
    commune, plan = _commune(db, insee)
    if plan is None or commune.status != "ok":
        raise Problem(404, "commune_without_plan", commune_status=commune.status)
    zones = _zones(db, plan, insee)
    if zone_code not in zones:
        raise Problem(404, "commune_zone_unknown")
    label, chapter_code = zones[zone_code]
    chapter = (
        db.execute(
            select(RegulationChapter).where(
                RegulationChapter.land_use_plan_id == plan.id, RegulationChapter.code == chapter_code
            )
        ).scalar_one_or_none()
        if chapter_code
        else None
    )
    extra = db.get(RegulationChapterScope, (chapter.id, scope)) if chapter and scope != "house" else None
    rule_set = db.execute(
        select(RuleSet).where(
            RuleSet.land_use_plan_id == plan.id, RuleSet.zone_code == zone_code, RuleSet.scope == scope
        )
    ).scalar_one_or_none()
    version = (
        db.get(RuleSetVersion, rule_set.current_version_id)
        if rule_set is not None and rule_set.current_version_id
        else None
    )
    state, _ = _state(scope, version, chapter, extra)
    rules = []
    if version is not None:
        urls = {
            f.id: f.url
            for f in db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars()
        }
        scanned = scan_pages(db, urls)
        rules = [
            rule_out(r, urls, plan.id, scanned)
            for r in db.execute(
                select(Rule)
                .where(Rule.rule_set_version_id == version.id)
                .order_by(Rule.kind, Rule.building_kind)
            ).scalars()
        ]
    return FeedZoneRulesOut(
        commune_insee=insee,
        scope=scope,
        zone=FeedZoneRefOut(code=zone_code, label=label, chapter_code=chapter_code),
        status=state.status,
        reason=state.reason,
        plan=plan_out(db, plan),
        version=(
            FeedVersionOut(
                id=version.id,
                version=version.version,
                status=version.status,
                origin=version.origin,
                model=version.model,
                prompt_version=version.prompt_version,
                engine_version=version.engine_version,
                created_at=version.created_at,
                coverage=version.coverage or {},
            )
            if version
            else None
        ),
        rules=[r for r in rules if r.status != "text_only"],
        hints=[r for r in rules if r.status == "text_only"],
        open_passages=[PassageOut(**p) for p in (version.open_passages or [])] if version else [],
        notices=FEED_NOTICES,
    )
