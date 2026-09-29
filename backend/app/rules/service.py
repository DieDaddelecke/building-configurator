"""Anwendungsfälle des Moduls G2 (Plan 3.4). Andere Module rufen nur diese Funktionen auf (Plan 3.2).

Kunden sehen die aktuelle Version jedes Regelwerks sofort als Simulation (D11). Korrekturen des Büros sind
freiwillig: für die Zone (neue Version `office_reviewed`) oder nur für ein Projekt (`project_rule_override`).
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform import audit
from app.platform.db import utcnow
from app.platform.jobs import enqueue
from app.platform.logging import get_logger
from app.platform.problems import Problem
from app.platform.shared import shared_session
from app.rules import documents, model_choice
from app.rules.budget import ORGANISATION_BUDGET_ERROR, organisation_budget_left
from app.rules.domain import ENGINE_VERSION
from app.rules.domain.assess import coverage as count_coverage
from app.rules.domain.form import kind_forms
from app.rules.domain.kinds import BUILDING_SPECIFIC_KINDS, ParamProblem, validate_params
from app.rules.domain.text import verify_quote
from app.rules.extract import RUNNING_STALE_AFTER, month_cost
from app.rules.models import (
    LandUsePlan,
    ProjectRegulation,
    ProjectRuleOverride,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)
from app.rules.schemas import (
    ChapterCoverageOut,
    CommuneCoverageOut,
    CoverageOut,
    IgnoredZoneOut,
    OverlayOut,
    ParamFieldOut,
    PassageOut,
    PlanOut,
    ProjectOverrideIn,
    ProjectOverrideOut,
    ProjectRulesOut,
    RuleDetailOut,
    RuleKindFormOut,
    RuleOut,
    RuleSetOut,
    RuleSetVersionIn,
    RulesModelOut,
    RuleSourceIn,
    RuleSourceOut,
    VersionOut,
    ZoneRulesOut,
)
from app.site import service as site_service
from app.site.service import SiteFootprint

log = get_logger("rules_service")
FEATURE_FLAG = "rules_simulation"
SLIVER_MIN_M2 = 1.0
SLIVER_MIN_SHARE = 0.01
"""Teilflächen unter 1 m² oder 1 % der Grundstücksfläche werden ignoriert (Spez. 5.2.2)."""
UNCOVERED_WARNING_SHARE = 0.01
"""Liegt mehr als dieser Anteil des Grundstücks in keiner Zone des Planwerks, erscheint eine Warnung."""
LINE_OVERLAY_DISTANCE_M = 1.0
"""Linienhafte Vorgaben (z. B. Baulinie) liegen oft genau auf der Grenze; bis 1 m gelten sie als betroffen."""
NOTICES = ["notice.rules_simulation", "notice.rules_lotissement"]
UPLOAD_NOTICES = ["notice.rules_simulation", "notice.rules_upload"]
"""Hochgeladenes Reglement (AN2): ausgewertet ist nur dieses Dokument – ohne Zonenplan, überlagernde
Vorgaben, Servituden und Zusatzdokumente (docs/PLAN_AN2_PLU.md 3.4)."""
RESULT_STATUSES = {"simulated", "office_reviewed"}
SPECIFIC_BUILDING_KINDS = ("main", "annex", "pool")

# Wiederaufnahme (rules_housekeeping)
PENDING_WITHOUT_JOB_AFTER = timedelta(minutes=30)
RETRY_TRANSIENT_AFTER = timedelta(hours=24)
RETRY_TRANSIENT_MAX_FAILED_RUNS_WEEK = 6
TRANSIENT_ERRORS = ("rate_limited", "http_5", "transport:", "interrupted:")
"""Gründe, die sich von selbst erledigen können. `refusal`, `max_tokens` eines einzelnen Sektors,
`bad_request`, `auth`, `chapter_too_long` brauchen eine Änderung und bleiben für den Betrieb stehen."""


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def _plan_out(db: Session, plan: LandUsePlan) -> PlanOut:
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


def _rule_out(
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


def apply_override(
    rules: list[RuleOut], override: ProjectRuleOverride, source: SourceFile | None = None
) -> list[RuleOut]:
    """Korrektur für ein Projekt einsetzen. Die spezifischere Regel geht vor:

    - `any` ersetzt alle Regeln dieser Art.
    - `main`, `annex` oder `pool` ersetzt die Regel dieses Baukörpers. Eine automatische Regel für `any`
      gilt dann nur noch für die übrigen Baukörper und erscheint für diese einzeln; bei Regelarten, die das
      Grundstück als Ganzes betreffen (Grundfläche, Stellplätze …), ersetzt die Korrektur sie ganz.
    """
    specific = override.building_kind
    present = {(r.kind, r.building_kind) for r in rules}
    result: list[RuleOut] = []
    for rule in rules:
        if rule.kind != override.kind:
            result.append(rule)
        elif specific == "any" or rule.building_kind == specific:
            continue
        elif rule.building_kind == "any":
            if override.kind in BUILDING_SPECIFIC_KINDS:
                result.extend(
                    rule.model_copy(update={"building_kind": other})
                    for other in SPECIFIC_BUILDING_KINDS
                    if other != specific and (rule.kind, other) not in present
                )
        else:
            result.append(rule)
    return [*result, _override_out(override, source)]


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
        current_has_rules = current is not None and current.out.status == "partial"
        if older.out.status == "ok" or (older.out.status == "partial" and not current_has_rules):
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
        warnings: list[str] = []
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
            warnings=warnings,
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
                updating="rules_updating" in warnings,
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
    plan_out = _plan_out(db, plan)
    if plan.status == "importing":
        return _unavailable(
            None, "document_reading", [], plan=plan_out, notices=UPLOAD_NOTICES, status="in_progress"
        )
    if plan.status != "active":
        return _unavailable(None, _document_reason(plan), [], plan=plan_out, notices=UPLOAD_NOTICES)
    if link.zone_code is None:
        return _unavailable(None, "zone_not_chosen", [], plan=plan_out, notices=UPLOAD_NOTICES)
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
    warnings = list(base_warnings)
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
    relevant = [r for r in rows if r.area >= SLIVER_MIN_M2 and r.area >= SLIVER_MIN_SHARE * site_area]
    ignored = [
        IgnoredZoneOut(code=r.code, area_m2=round(float(r.area), 2)) for r in rows if r not in relevant
    ]
    if len(relevant) > 1:
        warnings.append("multiple_zones")
    uncovered = max(0.0, 1.0 - sum(float(r.area) for r in rows) / site_area)
    if rows and uncovered >= UNCOVERED_WARNING_SHARE:
        warnings.append("zone_coverage_incomplete")

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
        [
            _ZoneRow(
                code=r.code,
                label=r.label,
                chapter_code=r.chapter_code,
                area=float(r.area),
                part_wkb=bytes(r.part_wkb) if r.part_wkb is not None else None,
            )
            for r in relevant
        ],
        site_area=site_area,
        commune=commune,
        warnings=warnings,
        ignored=ignored,
        uncovered_share=round(uncovered, 4) if rows else 0.0,
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
    warnings: list[str],
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
            select(RuleSet).where(RuleSet.land_use_plan_id == plan.id, RuleSet.zone_code.in_(codes))
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
    override_sources = _override_sources(db, [o for items in overrides.values() for o in items])
    urls = {
        f.id: f.url
        for f in db.execute(select(SourceFile).where(SourceFile.land_use_plan_id == plan.id)).scalars()
    }
    scanned = scan_pages(db, urls)

    zones: list[ZoneRulesOut] = []
    for row in relevant:
        rule_set = rule_sets.get(row.code)
        version_id = chosen.get(row.code) or (rule_set.current_version_id if rule_set else None)
        version = versions.get(version_id) if version_id else None
        chapter = chapters.get(row.chapter_code) if row.chapter_code else None
        status: str
        reason: str | None = None
        if version is not None and row.code in chosen:
            # Frühere Version zum Vergleich: Status nach Herkunft, nicht `retired` (PLAN_AN4 7.1 Nr. 4)
            status = "office_reviewed" if version.origin == "office" else "simulated"
        elif version is not None:
            status = version.status
            if chapter is not None and chapter.status in ("pending", "extracting"):
                warnings.append("rules_updating")
        elif chapter is None:
            status, reason = "unavailable", "chapter_not_found"
        elif chapter.status in ("pending", "extracting"):
            status = "in_progress"
        else:
            status, reason = "unavailable", chapter.error or chapter.status
        rules = (
            [_rule_out(r, urls, plan.id, scanned) for r in rules_by_version.get(version.id, [])]
            if version
            else []
        )
        # „any“ zuerst, damit eine spezifische Korrektur danach die allgemeine einschränkt
        for override in sorted(overrides.get(row.code, []), key=lambda o: o.building_kind != "any"):
            source = override_sources.get(override.source_file_id) if override.source_file_id else None
            rules = apply_override(rules, override, source)
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
                version=version_out(version) if version else None,
                rules=[r for r in rules if r.status != "text_only"],
                hints=[r for r in rules if r.status == "text_only"],
            )
        )

    statuses = {z.status for z in zones}
    if not zones:
        overall, overall_reason = "unavailable", "no_zone"
    elif statuses <= RESULT_STATUSES:
        overall, overall_reason = "ok", None
    elif "in_progress" in statuses and not statuses & RESULT_STATUSES:
        overall, overall_reason = "in_progress", None
    elif statuses & RESULT_STATUSES:
        overall, overall_reason = "partial", None
    else:
        overall, overall_reason = "unavailable", zones[0].reason
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
        plan=_plan_out(db, plan),
        zones=zones,
        ignored_zones=ignored,
        uncovered_share=uncovered_share,
        overlays=overlays,
        warnings=sorted(set(warnings)),
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


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


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
                plan=_plan_out(db, plan) if plan else None,
                fallback_plan=_plan_out(db, fallback) if fallback else None,
                chapters=chapters_out,
            )
        )
    return CoverageOut(
        configured=settings.openrouter_api_key is not None,
        model=_effective_model(settings),
        month_cost_usd=round(month_cost(db), 2),
        budget_month_usd=settings.rules_budget_month_usd,
        communes=communes,
    )


def _effective_model(settings: Settings) -> str:
    with shared_session() as shared_db:
        return model_choice.effective_settings(shared_db, settings).rules_model


def rules_model_out(db: Session, shared_db: Session, settings: Settings) -> RulesModelOut:
    """Eingestelltes KI-Modell mit Preisen, Kosten des Monats dieser Instanz und Budget (PLAN_AN2_PLU 8;
    die Wahl steht in der gemeinsamen Datenbank, VA09)."""
    chosen = model_choice.current(shared_db, settings)
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
        plan=_plan_out(db, plan),
        current=version_out(current) if current else None,
        versions=[version_out(v) for v in versions],
        rules=[
            RuleDetailOut(
                **_rule_out(r, urls, plan.id, scanned).model_dump(),
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


# ---------------------------------------------------------------------------
# Korrekturen je Projekt (Büro, seit AN4 auch im Analyse-Produkt: docs/PLAN_AN4_KORREKTUR.md 3.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleStates:
    """Stände der Regeln eines Projekts für den Vergleich (AN4, 3.5)."""

    corrected: bool
    """Wirkt eine Korrektur (in einer Zone der aktuellen Regeln)?"""
    earlier: list[tuple[str, VersionOut]]
    """Frühere Versionen je Zone, neueste zuerst."""
    current: dict[str, VersionOut]


def rule_states(db: Session, project_id: uuid.UUID) -> RuleStates:
    zones = {zone.code: zone for zone in resolve_rules(db, project_id).out.zones}
    corrected = (
        db.execute(
            select(ProjectRuleOverride.id).where(
                ProjectRuleOverride.project_id == project_id,
                ProjectRuleOverride.zone_code.in_(list(zones)),
            )
        ).first()
        is not None
    )
    earlier: list[tuple[str, VersionOut]] = []
    for zone in zones.values():
        if zone.rule_set_id is None:
            continue
        current = zone.version.id if zone.version else None
        earlier.extend(
            (zone.code, version_out(version))
            for version in db.execute(
                select(RuleSetVersion)
                .where(RuleSetVersion.rule_set_id == zone.rule_set_id, RuleSetVersion.id != current)
                .order_by(RuleSetVersion.version.desc())
            ).scalars()
        )
    return RuleStates(
        corrected=corrected,
        earlier=earlier,
        current={code: zone.version for code, zone in zones.items() if zone.version is not None},
    )


def _override_sources(db: Session, overrides: Sequence[ProjectRuleOverride]) -> dict[uuid.UUID, SourceFile]:
    ids = {o.source_file_id for o in overrides if o.source_file_id is not None}
    if not ids:
        return {}
    return {f.id: f for f in db.execute(select(SourceFile).where(SourceFile.id.in_(ids))).scalars()}


@dataclass(frozen=True)
class _ProjectState:
    """Zonen der aktuellen Regeln und Dokumente, die am Projekt hängen – Maßstab für Zonenprüfung,
    „wirksam“ und „Fundstelle am Projekt“."""

    zones: frozenset[str]
    documents: frozenset[uuid.UUID]


def _project_state(db: Session, project_id: uuid.UUID) -> _ProjectState:
    linked = {
        link.land_use_plan_id
        for link in db.execute(
            select(ProjectRegulation).where(ProjectRegulation.project_id == project_id)
        ).scalars()
    }
    if site_service.site_footprint(db, project_id) is None:
        return _ProjectState(frozenset(), frozenset(linked))
    out = resolve_rules(db, project_id).out
    if out.plan is not None:
        linked.add(out.plan.id)
    return _ProjectState(frozenset(z.code for z in out.zones), frozenset(linked))


def list_overrides(db: Session, project_id: uuid.UUID) -> list[ProjectOverrideOut]:
    overrides = list(
        db.execute(
            select(ProjectRuleOverride)
            .where(ProjectRuleOverride.project_id == project_id)
            .order_by(ProjectRuleOverride.zone_code, ProjectRuleOverride.kind)
        ).scalars()
    )
    if not overrides:
        return []
    state = _project_state(db, project_id)
    sources = _override_sources(db, overrides)
    titles = {
        plan.id: plan.title
        for plan in db.execute(
            select(LandUsePlan).where(LandUsePlan.id.in_({f.land_use_plan_id for f in sources.values()}))
        ).scalars()
    }

    def source_out(o: ProjectRuleOverride) -> RuleSourceOut | None:
        if o.page is None:
            return None
        file = sources.get(o.source_file_id) if o.source_file_id else None
        return RuleSourceOut(
            document_id=file.land_use_plan_id if file else None,
            document_title=titles.get(file.land_use_plan_id) if file else None,
            page=o.page,
            quote=o.quote,
            quote_verified=o.quote_verified,
            source_url=f"{file.url}#page={o.page}" if file else None,
            attached=file is not None and file.land_use_plan_id in state.documents,
        )

    return [
        ProjectOverrideOut(
            id=o.id,
            zone_code=o.zone_code,
            kind=o.kind,
            building_kind=o.building_kind,
            status=o.status,
            params=o.params or {},
            note=o.note,
            source=source_out(o),
            active=o.zone_code in state.zones,
            created_at=o.created_at,
            created_by=o.created_by,
            updated_at=o.updated_at,
            updated_by=o.updated_by,
        )
        for o in overrides
    ]


@dataclass(frozen=True)
class _Source:
    file: SourceFile
    page: int
    quote: str | None
    verified: bool


def _checked_source(db: Session, source: RuleSourceIn, state: _ProjectState) -> _Source:
    """Fundstelle prüfen: ein Dokument des Projekts, eine Seite darin; das Zitat wird wie bei der Auswertung
    auf der Seite und den Nachbarseiten gesucht (`verify_quote`). Nicht gefunden bleibt es gespeichert und
    erscheint als unbestätigt; gefunden berichtigt es die Seite."""
    plan = db.get(LandUsePlan, source.document_id)
    file = documents.latest_source(db, plan.id) if plan is not None else None
    if file is None or source.document_id not in state.documents:
        raise Problem(422, "source_document_unknown")
    if source.page > file.page_count:
        raise Problem(422, "source_page_invalid", detail=f"page_count={file.page_count}")
    quote = (source.quote or "").strip() or None
    if quote is None:
        return _Source(file, source.page, None, False)
    pages = {
        row.page: row.text
        for row in db.execute(
            select(SourcePage).where(
                SourcePage.source_file_id == file.id,
                SourcePage.page.between(source.page - 1, source.page + 1),
            )
        ).scalars()
    }
    check = verify_quote(quote, pages, source.page)
    page = check.page if check.verified and check.page is not None else source.page
    return _Source(file, page, quote, check.verified)


def set_override(
    db: Session, project_id: uuid.UUID, body: ProjectOverrideIn, actor_id: str
) -> list[ProjectOverrideOut]:
    """Korrektur setzen oder ändern. Die Zone muss eine Zone der aktuellen Regeln sein: Sonst wirkte sie
    nicht oder träfe ein Zusatzdokument mit gleichem Sektor (`Lot-12`, PLAN_AN4 7.1 Nr. 3)."""
    if site_service.site_footprint(db, project_id) is None:
        raise Problem(404, "site_not_found")
    state = _project_state(db, project_id)
    if body.zone_code not in state.zones:
        raise Problem(422, "zone_unknown")
    params = _validated(body.kind, body.status, body.params)
    source = _checked_source(db, body.source, state) if body.source is not None else None
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
    before = (
        {"status": existing.status, "params": existing.params, "page": existing.page} if existing else None
    )
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
    existing.source_file_id = source.file.id if source else None
    existing.page = source.page if source else None
    existing.quote = source.quote if source else None
    existing.quote_verified = source.verified if source else False
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
            "source": (
                {
                    "document": str(source.file.land_use_plan_id),
                    "page": source.page,
                    "quote_verified": source.verified,
                }
                if source
                else None
            ),
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
        before={
            "zone": override.zone_code,
            "kind": override.kind,
            "status": override.status,
            "params": override.params,
            "page": override.page,
        },
    )
    db.delete(override)
    db.commit()
    return list_overrides(db, project_id)


def enqueue_import(db: Session, communes: list[str] | None, force: bool, actor_id: str) -> uuid.UUID:
    import app.rules.jobs  # noqa: F401  Jobarten anmelden (lokal, sonst Importzyklus)

    job_id = enqueue(db, "plu_import", {"communes": communes, "force": force}, created_by=actor_id)
    db.commit()
    return job_id


_ACTIVE_EXTRACT_JOB = text(
    "SELECT id FROM job WHERE kind = 'rules_extract' AND status IN ('queued', 'running') "
    "AND payload->>'chapter_id' = :chapter ORDER BY created_at LIMIT 1"
)


def _active_extract_job(db: Session, chapter_id: uuid.UUID) -> uuid.UUID | None:
    return db.execute(_ACTIVE_EXTRACT_JOB, {"chapter": str(chapter_id)}).scalar()


def enqueue_extract(db: Session, chapter_id: uuid.UUID, force: bool, actor_id: str) -> uuid.UUID:
    """Kapitel auswerten. Wartet oder läuft schon ein Job für das Kapitel, bleibt es bei diesem: ein zweiter
    Klick kostet nicht noch einmal."""
    import app.rules.jobs  # noqa: F401

    chapter = db.get(RegulationChapter, chapter_id)
    if chapter is None:
        raise Problem(404, "not_found")
    active = _active_extract_job(db, chapter_id)
    if active is not None:
        return active
    if chapter.status != "extracting":
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


def housekeeping(db: Session, settings: Settings) -> dict[str, Any]:
    """Liegengebliebene und aus behebbarem Grund gescheiterte Kapitel wieder aufnehmen (stündlich, D11).

    - `extracting` länger als das Zeitlimit: abgebrochen (`interrupted:stale`).
    - `pending` ohne wartenden Job: neu einplanen.
    - `not_configured`, sobald ein Schlüssel eingetragen ist; `budget_exceeded` und
      `organisation_budget_exceeded` (AN6), sobald das Budget wieder
      reicht (neuer Monat, höheres Budget); vorübergehende Fehler nach 24 h, höchstens 6 gescheiterte Aufrufe
      je Woche.
    - Ausgewertet mit älterer Version der Schranken: neu bewerten (ohne Aufruf, wenn die Antworten vorliegen).
    """
    import app.rules.jobs  # noqa: F401

    now = utcnow()
    chapters = list(
        db.execute(
            select(RegulationChapter)
            .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
            .where(LandUsePlan.status == "active", func.cardinality(RegulationChapter.sectors) > 0)
            .with_for_update(of=RegulationChapter, skip_locked=True)
        ).scalars()
    )
    budget_left = month_cost(db) < settings.rules_budget_month_usd
    counts: dict[str, int] = defaultdict(int)
    for chapter in chapters:
        if chapter.status == "extracting" and now - chapter.updated_at > RUNNING_STALE_AFTER:
            chapter.status, chapter.error, chapter.updated_at = "failed", "interrupted:stale", now
            counts["stale"] += 1
        reason = _restart_reason(db, settings, chapter, now, budget_left)
        if reason is None or _active_extract_job(db, chapter.id) is not None:
            continue
        chapter.status, chapter.updated_at = "pending", now
        enqueue(
            db,
            "rules_extract",
            {"chapter_id": str(chapter.id)},
            idempotency_key=f"rules_housekeeping:{chapter.id}:{reason}:{now:%Y%m%d%H}",
            created_by=f"system:rules_housekeeping:{reason}",
        )
        counts[reason] += 1
    db.commit()
    if counts:
        log.info("rules_housekeeping", **counts)
    return dict(counts)


def _restart_reason(
    db: Session, settings: Settings, chapter: RegulationChapter, now: Any, budget_left: bool
) -> str | None:
    if chapter.status == "pending":
        return "pending" if now - chapter.updated_at > PENDING_WITHOUT_JOB_AFTER else None
    if chapter.status == "succeeded":
        stale_engine = chapter.engine_version is not None and chapter.engine_version != ENGINE_VERSION
        return "engine_changed" if stale_engine else None
    if chapter.status != "failed" or chapter.error is None:
        return None
    if chapter.error == "not_configured":
        return "configured" if settings.openrouter_api_key is not None else None
    if chapter.error == "budget_exceeded":
        return "budget" if budget_left else None
    if chapter.error == ORGANISATION_BUDGET_ERROR:
        # Neuer Monat oder erhöhtes Budget der zahlenden Organisation (AN6, PLAN_AN6_MANDANTEN 7.1 Nr. 20)
        left = budget_left and organisation_budget_left(db, settings, chapter.billing_organisation_id)
        return "budget" if left else None
    if chapter.error.startswith(TRANSIENT_ERRORS) and now - chapter.updated_at > RETRY_TRANSIENT_AFTER:
        failed_week = db.execute(
            select(func.count())
            .select_from(RuleExtractionRun)
            .where(
                RuleExtractionRun.chapter_id == chapter.id,
                RuleExtractionRun.status == "failed",
                RuleExtractionRun.created_at > now - timedelta(days=7),
            )
        ).scalar_one()
        return "transient" if failed_week < RETRY_TRANSIENT_MAX_FAILED_RUNS_WEEK else None
    return None
