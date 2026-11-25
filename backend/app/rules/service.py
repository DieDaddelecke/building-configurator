"""Regeln für ein Grundstück auflösen (Modul G2, Plan 3.4): Zonen, Regelwerke, Rückfall auf einen älteren
Planstand, hochgeladenes PLU und Zusatzdokumente. Andere Module rufen nur die öffentlichen Funktionen auf
(Plan 3.2).

Kunden sehen die aktuelle Version jedes Regelwerks sofort als Simulation (D11). Korrekturen des Büros sind
freiwillig: für die Zone (neue Version `office_reviewed`, `office.py`) oder nur für ein Projekt
(`project_rule_override`, `overrides.py`). Einplanen und Wiederaufnahme: `scheduling.py`.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.platform.problems import Problem
from app.rules import documents
from app.rules.domain import ENGINE_VERSION
from app.rules.domain.kinds import ParamProblem, validate_params
from app.rules.domain.resolve import (
    RESULT_STATUSES,
    ZoneState,
    apply_override,
    overall_status,
    split_slivers,
    use_older,
    zone_state,
)
from app.rules.models import (
    LandUsePlan,
    ProjectRegulation,
    ProjectRuleOverride,
    RegulationChapter,
    Rule,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)
from app.rules.schemas import (
    IgnoredZoneOut,
    OverlayOut,
    PassageOut,
    PlanOut,
    ProjectRulesOut,
    RuleOut,
    VersionOut,
    ZoneRulesOut,
)
from app.site import service as site_service
from app.site.service import SiteFootprint

FEATURE_FLAG = "rules_simulation"
LINE_OVERLAY_DISTANCE_M = 1.0
"""Linienhafte Vorgaben (z. B. Baulinie) liegen oft genau auf der Grenze; bis 1 m gelten sie als betroffen."""
NOTICES = ["notice.rules_simulation", "notice.rules_lotissement"]
UPLOAD_NOTICES = ["notice.rules_simulation", "notice.rules_upload"]
"""Hochgeladenes Reglement (AN2): ausgewertet ist nur dieses Dokument – ohne Zonenplan, überlagernde
Vorgaben, Servituden und Zusatzdokumente (docs/PLAN_AN2_PLU.md 3.4)."""

# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def plan_out(db: Session, plan: LandUsePlan) -> PlanOut:
    source = documents.latest_source(db, plan.id)
    return PlanOut(
        id=plan.id,
        origin="upload" if plan.origin == "upload" else "gpu",
        title=plan.title,
        du_type=plan.du_type,
        gpu_doc_id=plan.gpu_doc_id,
        gpu_update_date=plan.gpu_update_date,
        regulation_url=source.url if source else None,
    )


def version_out(version: RuleSetVersion) -> VersionOut:
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
        open_passages=[PassageOut(**p) for p in version.open_passages or []],
        out_of_scope_passages=[PassageOut(**p) for p in version.out_of_scope_passages or []],
    )


def _source_url(urls: dict[uuid.UUID, str], file_id: uuid.UUID | None, page: int | None) -> str | None:
    if file_id is None or file_id not in urls:
        return None
    return f"{urls[file_id]}#page={page}" if page else urls[file_id]


def _document_reason(plan: LandUsePlan) -> str:
    """Warum ein hochgeladenes Dokument keine Regeln liefert: Scan vor der Texterkennung (AN7) oder Fehler."""
    if plan.status == "scan":
        return "document_scan"
    return plan.error or "document_failed"


def scan_pages(db: Session, file_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, set[int]]:
    """Seiten je Datei, deren Text per Texterkennung gelesen wurde (AN7, PLAN_AN7_SCAN 3.3)."""
    ids = list(file_ids)
    pages: dict[uuid.UUID, set[int]] = defaultdict(set)
    if ids:
        for file_id, page in db.execute(
            select(SourcePage.source_file_id, SourcePage.page).where(
                SourcePage.source_file_id.in_(ids), SourcePage.ocr_confidence.is_not(None)
            )
        ).tuples():
            pages[file_id].add(page)
    return pages


def rule_out(
    rule: Rule,
    urls: dict[uuid.UUID, str],
    plan_id: uuid.UUID | None = None,
    scanned: dict[uuid.UUID, set[int]] | None = None,
) -> RuleOut:
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
        source_document_id=plan_id if rule.source_file_id is not None else None,
        search_note=rule.detail if rule.reason in ("not_found_after_search", "not_expressible") else None,
        from_scan=bool(
            scanned and rule.source_file_id is not None and rule.page in scanned.get(rule.source_file_id, ())
        ),
    )


def _override_out(override: ProjectRuleOverride, source: SourceFile | None = None) -> RuleOut:
    """Die Begründung (`note`) bleibt draußen: Sie ist nur für das Büro (AN4, PLAN_AN4 7.1 Nr. 8) und steht
    in der Liste der Korrekturen. Mit Fundstelle Seite, Zitat und Verweis wie eine gelesene Regel."""
    page = override.page if source is not None else None
    return RuleOut(
        kind=override.kind,
        building_kind=override.building_kind,
        status=override.status,
        reason="correction" if override.status == "unknown" else None,
        params=override.params or {},
        page=page,
        quote=override.quote if source is not None else None,
        quote_verified=override.quote_verified if source is not None else False,
        source_url=f"{source.url}#page={page}" if source is not None and page else None,
        confidence=1.0,
        notes=None,
        origin="project",
        source_document_id=source.land_use_plan_id if source is not None else None,
    )


def validated_params(kind: str, status: str, params: dict[str, Any]) -> dict[str, Any]:
    if status == "effective" or kind == "text_only":
        try:
            return validate_params(kind, params)
        except ParamProblem as problem:
            raise Problem(422, "rule_params_invalid", detail=problem.detail) from None
    return {}


def override_source_files(
    db: Session, overrides: Sequence[ProjectRuleOverride]
) -> dict[uuid.UUID, SourceFile]:
    ids = {o.source_file_id for o in overrides if o.source_file_id is not None}
    if not ids:
        return {}
    return {f.id: f for f in db.execute(select(SourceFile).where(SourceFile.id.in_(ids))).scalars()}


# ---------------------------------------------------------------------------
# Kunde
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoneGeometry:
    """Teilfläche Grundstück × Zone in Lambert-93 (WKB) für den Baurahmen (Plan G3 4.2)."""

    code: str
    wkb: bytes


@dataclass(frozen=True)
class ConstraintGeometry:
    """Überlagernde Vorgabe, auf das Grundstück und seine nahe Umgebung zugeschnitten."""

    category: str
    type_code: str | None
    label: str
    endpoint: str
    wkb: bytes


@dataclass(frozen=True)
class RulesResult:
    """Ergebnis der Regelauswahl: Anzeige (`out`) und – auf Anforderung – Geometrie für G3.

    Anzeige und Baurahmen entstehen aus **einem** Aufruf, damit sie nie verschiedene Zonen,
    Planstände oder Korrekturen verwenden (Plan G3 11.1 Nr. 7).
    """

    out: ProjectRulesOut
    zones: list[ZoneGeometry] = field(default_factory=list)
    constraints: list[ConstraintGeometry] = field(default_factory=list)
    rule_set_version_ids: list[uuid.UUID] = field(default_factory=list)
    override_count: int = 0
    engine_version: str = ENGINE_VERSION


def _unavailable(
    commune: str | None,
    reason: str,
    warnings: list[str],
    *,
    plan: PlanOut | None = None,
    notices: list[str] = NOTICES,
    status: Literal["unavailable", "in_progress"] = "unavailable",
) -> RulesResult:
    return RulesResult(
        out=ProjectRulesOut(
            status=status,
            reason=reason,
            commune_insee=commune,
            plan=plan,
            zones=[],
            ignored_zones=[],
            overlays=[],
            warnings=sorted(set(warnings)),
            notices=notices,
        )
    )


@dataclass(frozen=True)
class RulesOptions:
    """Welcher Stand der Regeln (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5): mit oder ohne die Korrekturen des
    Projekts, je Zone die aktuelle oder eine frühere Regelwerksversion. Ohne Angabe der Arbeitsstand."""

    overrides: bool = True
    versions: Mapping[str, uuid.UUID] = field(default_factory=dict)
    """Zonencode → Version eines Regelwerks dieser Zone; gehört sie nicht dazu, gilt die aktuelle."""


CURRENT = RulesOptions()


def project_rules(db: Session, project_id: uuid.UUID) -> ProjectRulesOut:
    """Simulation für das Grundstück (Anzeige)."""
    return resolve_rules(db, project_id).out


def envelope_rules(db: Session, project_id: uuid.UUID, options: RulesOptions = CURRENT) -> RulesResult:
    """Wie `project_rules`, zusätzlich mit Geometrie der Teilflächen und Vorgaben (Modul G3)."""
    return resolve_rules(db, project_id, geometry=True, options=options)


def resolve_rules(
    db: Session, project_id: uuid.UUID, *, geometry: bool = False, options: RulesOptions = CURRENT
) -> RulesResult:
    """Simulation für das Grundstück. Ist der aktuelle Planstand für dieses Grundstück nicht vollständig
    ausgewertet oder nicht lesbar, zeigt sie den vorigen Planstand als „veraltet“ (Plan 3.4, RW21).

    Hat das Projekt ein **hochgeladenes** règlement écrit (AN2), gilt es vor dem GPU-Weg – auch für ein
    Kataster-Grundstück (E-AN2-6): eine Zone, Teilfläche = ganzes Grundstück (`_uploaded_rules`)."""
    footprint = site_service.site_footprint(db, project_id)
    if footprint is None:
        raise Problem(404, "site_not_found")
    link = documents.project_plu(db, project_id)
    if link is not None:
        return _uploaded_rules(db, project_id, footprint, link, geometry=geometry, options=options)
    commune = footprint.commune_insees[0] if footprint.commune_insees else None
    warnings: list[str] = []
    if len(footprint.commune_insees) > 1:
        warnings.append("multiple_communes")
    state = db.get(RulesCommune, commune) if commune else None
    plan = db.get(LandUsePlan, state.land_use_plan_id) if state and state.land_use_plan_id else None
    usable = state is not None and state.status == "ok" and plan is not None and plan.status == "active"
    current = (
        _plan_rules(db, project_id, footprint, commune, plan, warnings, geometry=geometry, options=options)
        if usable and plan
        else None
    )
    if current is not None and current.out.status == "ok":
        return current

    fallback = (
        db.get(LandUsePlan, state.fallback_land_use_plan_id)
        if state is not None and state.fallback_land_use_plan_id
        else None
    )
    if fallback is not None:
        older = _plan_rules(
            db,
            project_id,
            footprint,
            commune,
            fallback,
            [*warnings, "rules_outdated" if usable else "plan_update_failed"],
            geometry=geometry,
            options=options,
        )
        if use_older(current.out.status if current is not None else None, older.out.status):
            for zone in older.out.zones:
                if zone.status in RESULT_STATUSES:
                    zone.status = "outdated"
            return older
    if current is not None:
        return current
    unavailable = state.status if state is not None and state.status != "ok" else "not_imported"
    return _unavailable(commune, unavailable, warnings)


def has_uploaded_plu(db: Session, project_id: uuid.UUID) -> bool:
    """Hat das Projekt ein hochgeladenes PLU (AN2)? Dann gibt es Regeln auch ohne Kataster (G3, 3.5)."""
    return documents.project_plu(db, project_id) is not None


@dataclass(frozen=True)
class SupplementRules:
    """Regeln eines Zusatzdokuments für das gewählte Lot (AN3, docs/PLAN_AN3_ANALYSE.md 3.7). Sie wirken
    nicht in Regeln und Baurahmen, sondern nur im Vergleich der Analyse (E-AN3-2)."""

    document_id: uuid.UUID
    title: str
    du_type: str
    lot: str | None
    """Sektor des Lots (`Lot-12`, `Ensemble`); leer, bis der Architekt es wählt."""
    status: str
    """`simulated`/`office_reviewed` mit Regeln, sonst `in_progress` oder `unavailable` mit Grund."""
    reason: str | None
    rules: list[RuleOut] = field(default_factory=list)
    hints: list[RuleOut] = field(default_factory=list)
    version_id: uuid.UUID | None = None
    updating: bool = False
    """Eine neue Auswertung läuft (z. B. weil ein weiteres Lot dazukam); bis dahin gelten diese Regeln."""


def supplement_rules(db: Session, project_id: uuid.UUID) -> list[SupplementRules]:
    """Regeln aller Zusatzdokumente des Projekts – dieselbe Zusammenstellung wie für das PLU (BR15)."""
    result: list[SupplementRules] = []
    for link in documents.supplement_links(db, project_id):
        plan = db.get(LandUsePlan, link.land_use_plan_id)
        assert plan is not None
        base: dict[str, Any] = {
            "document_id": plan.id,
            "title": plan.title,
            "du_type": plan.du_type,
            "lot": link.zone_code,
        }
        if plan.status == "importing":
            result.append(SupplementRules(**base, status="in_progress", reason="document_reading"))
            continue
        if plan.status != "active":
            result.append(SupplementRules(**base, status="unavailable", reason=_document_reason(plan)))
            continue
        if link.zone_code is None:
            result.append(SupplementRules(**base, status="unavailable", reason="lot_not_chosen"))
            continue
        rules = _rules_for_zones(
            db,
            project_id,
            plan,
            [
                _ZoneRow(
                    code=link.zone_code,
                    label=plan.title,
                    chapter_code=link.chapter_code,
                    area=1.0,
                    part_wkb=None,
                )
            ],
            site_area=1.0,
            commune=None,
            warnings=[],
            ignored=[],
            uncovered_share=0.0,
            overlay_rows=[],
            notices=[],
            geometry=False,
            # Korrekturen gelten dem PLU; ein Zonencode wie `Lot-12` darf das Zusatzdokument nicht ändern
            options=RulesOptions(overrides=False),
        )
        zone = rules.out.zones[0]
        result.append(
            SupplementRules(
                **base,
                status=zone.status,
                reason=zone.reason,
                rules=list(zone.rules),
                hints=list(zone.hints),
                version_id=zone.version.id if zone.version else None,
                updating="rules_updating" in rules.out.warnings,
            )
        )
    return result


@dataclass(frozen=True)
class _ZoneRow:
    """Teilfläche Grundstück × Zone: aus dem GPU verschnitten oder, beim Upload, das ganze Grundstück."""

    code: str
    label: str | None
    chapter_code: str | None
    area: float
    part_wkb: bytes | None


def _uploaded_rules(
    db: Session,
    project_id: uuid.UUID,
    footprint: SiteFootprint,
    link: ProjectRegulation,
    *,
    geometry: bool,
    options: RulesOptions,
) -> RulesResult:
    """Zweiter Einstieg (AN2, 3.4): gewähltes Dokument und Kapitel statt Gemeinde und Zonengeometrie.
    Kein Rückfall-Planstand, keine überlagernden Vorgaben, keine Gemeinde."""
    plan = db.get(LandUsePlan, link.land_use_plan_id)
    assert plan is not None
    document_plan = plan_out(db, plan)
    if plan.status == "importing":
        return _unavailable(
            None, "document_reading", [], plan=document_plan, notices=UPLOAD_NOTICES, status="in_progress"
        )
    if plan.status != "active":
        return _unavailable(None, _document_reason(plan), [], plan=document_plan, notices=UPLOAD_NOTICES)
    if link.zone_code is None:
        return _unavailable(None, "zone_not_chosen", [], plan=document_plan, notices=UPLOAD_NOTICES)
    chapter = db.execute(
        select(RegulationChapter).where(
            RegulationChapter.land_use_plan_id == plan.id, RegulationChapter.code == link.chapter_code
        )
    ).scalar_one_or_none()
    row = _ZoneRow(
        code=link.zone_code,
        label=chapter.title if chapter is not None else None,
        chapter_code=link.chapter_code,
        area=footprint.area_m2,
        part_wkb=footprint.wkb if geometry else None,
    )
    return _rules_for_zones(
        db,
        project_id,
        plan,
        [row],
        site_area=footprint.area_m2 or 1.0,
        commune=None,
        warnings=[],
        ignored=[],
        uncovered_share=0.0,
        overlay_rows=[],
        notices=UPLOAD_NOTICES,
        geometry=geometry,
        options=options,
    )


def _plan_rules(
    db: Session,
    project_id: uuid.UUID,
    footprint: SiteFootprint,
    commune: str | None,
    plan: LandUsePlan,
    base_warnings: list[str],
    *,
    geometry: bool = False,
    options: RulesOptions = CURRENT,
) -> RulesResult:
    """GPU-Weg: Zonen des Planstands mit dem Grundstück verschneiden, Vorgaben der Gemeinde dazu."""
    part = "ST_Union(ST_Intersection(z.geometry, s.g))"
    rows = db.execute(
        text(
            f"""
            WITH s AS (SELECT ST_GeomFromWKB(:wkb, 2154) AS g)
            SELECT z.code, max(z.label) AS label, max(z.chapter_code) AS chapter_code,
                   ST_Area({part}) AS area,
                   {f"ST_AsBinary(ST_MakeValid({part}))" if geometry else "NULL"} AS part_wkb
            FROM zone z, s
            WHERE z.land_use_plan_id = :plan AND z.geometry && s.g AND ST_Intersects(z.geometry, s.g)
            GROUP BY z.code
            ORDER BY area DESC
            """  # noqa: S608  nur ein fester Ausdruck, keine Eingabe
        ),
        {"wkb": footprint.wkb, "plan": plan.id},
    ).all()
    site_area = footprint.area_m2 or 1.0
    split = split_slivers(
        [
            _ZoneRow(
                code=r.code,
                label=r.label,
                chapter_code=r.chapter_code,
                area=float(r.area),
                part_wkb=bytes(r.part_wkb) if r.part_wkb is not None else None,
            )
            for r in rows
        ],
        site_area,
    )

    overlay_rows = db.execute(
        text(
            f"""
            WITH s AS (SELECT ST_GeomFromWKB(:wkb, 2154) AS g)
            SELECT o.category, o.type_code, o.label, o.endpoint,
                   {
                "ST_AsBinary(ST_MakeValid(ST_Intersection(o.geometry, ST_Buffer(s.g, :distance))))"
                if geometry
                else "NULL"
            } AS clipped
            FROM overlay_constraint o, s
            WHERE o.land_use_plan_id = :plan AND o.commune_insee = :commune
              AND ST_DWithin(o.geometry, s.g, :distance)
              AND (GeometryType(o.geometry) NOT LIKE '%POLYGON%' OR ST_Intersects(o.geometry, s.g))
            ORDER BY o.category, o.label
            """  # noqa: S608  nur ein fester Ausdruck, keine Eingabe
        ),
        {"wkb": footprint.wkb, "plan": plan.id, "commune": commune, "distance": LINE_OVERLAY_DISTANCE_M},
    ).all()
    return _rules_for_zones(
        db,
        project_id,
        plan,
        split.relevant,
        site_area=site_area,
        commune=commune,
        warnings=[*base_warnings, *split.warnings],
        ignored=[IgnoredZoneOut(code=r.code, area_m2=round(r.area, 2)) for r in split.ignored],
        uncovered_share=split.uncovered_share,
        overlay_rows=list(overlay_rows),
        notices=NOTICES,
        geometry=geometry,
        options=options,
    )


def _rules_for_zones(
    db: Session,
    project_id: uuid.UUID,
    plan: LandUsePlan,
    relevant: list[_ZoneRow],
    *,
    site_area: float,
    commune: str | None,
    warnings: Sequence[str],
    ignored: list[IgnoredZoneOut],
    uncovered_share: float,
    overlay_rows: list[Any],
    notices: list[str],
    geometry: bool,
    options: RulesOptions = CURRENT,
) -> RulesResult:
    """Regelwerke, Versionen, Kapitelstatus, Projektkorrekturen und Zitat-URLs je Zonenzeile – für beide
    Einstiege gleich, damit Anzeige und Baurahmen dieselbe Ausgabe bekommen (BR15, AN2 3.4)."""
    codes = [r.code for r in relevant]
    rule_sets = {
        rs.zone_code: rs
        for rs in db.execute(
            # Nur `house`: Regelwerke anderer Umfänge sind für den Regeldienst (PLAN_REGELDIENST 3.2)
            select(RuleSet).where(
                RuleSet.land_use_plan_id == plan.id, RuleSet.zone_code.in_(codes), RuleSet.scope == "house"
            )
        ).scalars()
    }
    pinned = {code: version_id for code, version_id in options.versions.items() if code in rule_sets}
    versions = {
        v.id: v
        for v in db.execute(
            select(RuleSetVersion).where(
                RuleSetVersion.id.in_(
                    [rs.current_version_id for rs in rule_sets.values() if rs.current_version_id]
                    + list(pinned.values())
                )
            )
        ).scalars()
    }
    # Eine frühere Version gilt nur, wenn sie zum Regelwerk dieser Zone gehört (AN4 3.5)
    chosen = {
        code: version_id
        for code, version_id in pinned.items()
        if version_id in versions and versions[version_id].rule_set_id == rule_sets[code].id
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
    if options.overrides:
        for override in db.execute(
            select(ProjectRuleOverride)
            .where(ProjectRuleOverride.project_id == project_id)
            .order_by(ProjectRuleOverride.building_kind)
        ).scalars():
            overrides[override.zone_code].append(override)
    override_sources = override_source_files(db, [o for items in overrides.values() for o in items])
    urls = {
        f.id: f.url
        for f in db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars()
    }
    scanned = scan_pages(db, urls)

    zones: list[ZoneRulesOut] = []
    states: list[ZoneState] = []
    for row in relevant:
        rule_set = rule_sets.get(row.code)
        version_id = chosen.get(row.code) or (rule_set.current_version_id if rule_set else None)
        version = versions.get(version_id) if version_id else None
        chapter = chapters.get(row.chapter_code) if row.chapter_code else None
        state = zone_state(
            version.status if version else None,
            chapter.status if chapter else None,
            version_origin=version.origin if version else None,
            pinned=row.code in chosen,
            chapter_error=chapter.error if chapter else None,
        )
        states.append(state)
        rules = (
            [rule_out(r, urls, plan.id, scanned) for r in rules_by_version.get(version.id, [])]
            if version
            else []
        )
        # „any“ zuerst, damit eine spezifische Korrektur danach die allgemeine einschränkt
        for override in sorted(overrides.get(row.code, []), key=lambda o: o.building_kind != "any"):
            source = override_sources.get(override.source_file_id) if override.source_file_id else None
            rules = apply_override(
                rules,
                _override_out(override, source),
                lambda rule, building_kind: rule.model_copy(update={"building_kind": building_kind}),
            )
        zones.append(
            ZoneRulesOut(
                code=row.code,
                label=row.label,
                chapter_code=row.chapter_code,
                area_m2=round(float(row.area), 2),
                share=round(float(row.area) / site_area, 4),
                status=state.status,
                reason=state.reason,
                rule_set_id=rule_set.id if rule_set else None,
                version=version_out(version) if version else None,
                rules=[r for r in rules if r.status != "text_only"],
                hints=[r for r in rules if r.status == "text_only"],
            )
        )

    overall, overall_reason = overall_status(states)
    updating = ["rules_updating"] if any(state.updating for state in states) else []
    overlays: list[OverlayOut] = []
    for row in overlay_rows:
        overlay = OverlayOut(
            category=row.category, type_code=row.type_code, label=row.label, endpoint=row.endpoint
        )
        if overlay not in overlays:  # dieselbe Vorgabe kommt in mehreren Teilen vor
            overlays.append(overlay)
    out = ProjectRulesOut(
        status=overall,
        reason=overall_reason,
        commune_insee=commune,
        plan=plan_out(db, plan),
        zones=zones,
        ignored_zones=ignored,
        uncovered_share=uncovered_share,
        overlays=overlays,
        warnings=sorted({*warnings, *updating}),
        notices=notices,
    )
    if not geometry:
        return RulesResult(out=out)
    return RulesResult(
        out=out,
        zones=[ZoneGeometry(code=row.code, wkb=row.part_wkb) for row in relevant if row.part_wkb is not None],
        constraints=[
            ConstraintGeometry(
                category=row.category,
                type_code=row.type_code,
                label=row.label,
                endpoint=row.endpoint,
                wkb=bytes(row.clipped),
            )
            for row in overlay_rows
            if row.clipped is not None
        ],
        rule_set_version_ids=sorted({v.id for v in versions.values()}),
        override_count=sum(len(items) for items in overrides.values()),
    )
