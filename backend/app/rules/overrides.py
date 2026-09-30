"""Korrekturen je Projekt (`project_rule_override`): anzeigen, setzen, löschen und die Stände der Regeln
für den Vergleich (Büro, seit AN4 auch im Analyse-Produkt: docs/PLAN_AN4_KORREKTUR.md 3.2;
aus `service.py` gelöst, REFACTORING_PLAN S19)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import audit
from app.platform.db import utcnow
from app.platform.problems import Problem
from app.rules import documents
from app.rules.domain.text import verify_quote
from app.rules.models import (
    LandUsePlan,
    ProjectRegulation,
    ProjectRuleOverride,
    RuleSetVersion,
    SourceFile,
    SourcePage,
)
from app.rules.schemas import (
    ProjectOverrideIn,
    ProjectOverrideOut,
    RuleSourceIn,
    RuleSourceOut,
    VersionOut,
)
from app.rules.service import (
    override_source_files,
    resolve_rules,
    validated_params,
    version_out,
)
from app.site import service as site_service


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
    sources = override_source_files(db, overrides)
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
    params = validated_params(body.kind, body.status, body.params)
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
