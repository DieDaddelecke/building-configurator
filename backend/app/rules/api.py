"""Endpunkte des Moduls G2 (Spez. 6.3, 6.4; Plan 3.4).

Kunden lesen die Regeln ihres Grundstücks hinter dem Feature-Flag `rules_simulation` (Plan 4.2).
Büro: Abdeckung und Regelwerke lesen (`architect`, `rules_admin`, `ops`), Korrekturen (`architect`,
`rules_admin`), Import und erneute Auswertung (`ops`, `rules_admin`). Keine dieser Büroaktionen ist
Voraussetzung für die Simulation beim Kunden (D11).
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.problems import Problem
from app.rules import service
from app.rules.schemas import (
    CoverageOut,
    ExtractIn,
    ProjectOverrideIn,
    ProjectOverrideOut,
    ProjectRulesOut,
    RuleSetOut,
    RuleSetVersionIn,
    RulesImportIn,
)

router = APIRouter(tags=["rules"])


def require_rules_feature(auth: RequestAuth = Depends(get_auth), db: Session = Depends(get_db)) -> None:
    if not flags.is_enabled(db, service.FEATURE_FLAG, auth):
        raise Problem(403, "feature_disabled")


@router.get(
    "/projects/{project_id}/rules",
    response_model=ProjectRulesOut,
    dependencies=[Depends(require_rules_feature)],
)
def get_project_rules(
    request: Request,
    project_id: uuid.UUID = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ProjectRulesOut:
    """Zonen, Regeln mit Zitat und Status, Vorgaben und Hinweise – als Simulation (Plan 3.4, D11)."""
    rate_limit.check(request, "rules_read", get_settings().rules_limit_per_minute, 60)
    return service.project_rules(db, project_id)


Reader = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops))
Editor = Depends(require_roles(Role.architect, Role.rules_admin))
Operator = Depends(require_roles(Role.ops, Role.rules_admin))


@router.get("/admin/rules/coverage", response_model=CoverageOut)
def rules_coverage(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> CoverageOut:
    """Abdeckung je Gemeinde und Kapitel mit Status, Läufen, Kosten und Monatsbudget (Plan 3.4, 6.8)."""
    return service.coverage(db, get_settings())


@router.post("/admin/rules/imports", status_code=202)
def start_rules_import(
    body: RulesImportIn, staff: StaffPrincipal = Operator, db: Session = Depends(get_db)
) -> dict[str, uuid.UUID]:
    return {"job_id": service.enqueue_import(db, body.communes, body.force, staff.actor_id)}


@router.post("/admin/rules/chapters/{chapter_id}/extract", status_code=202)
def start_chapter_extraction(
    chapter_id: uuid.UUID, body: ExtractIn, staff: StaffPrincipal = Operator, db: Session = Depends(get_db)
) -> dict[str, uuid.UUID]:
    """Kapitel erneut auswerten (z. B. nach neuer Prompt-Version oder gescheitertem Lauf); kostet Token."""
    return {"job_id": service.enqueue_extract(db, chapter_id, body.force, staff.actor_id)}


@router.get("/admin/rule-sets/{rule_set_id}", response_model=RuleSetOut)
def get_rule_set(
    rule_set_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> RuleSetOut:
    return service.rule_set_detail(db, rule_set_id)


@router.post("/admin/rule-sets/{rule_set_id}/versions", response_model=RuleSetOut, status_code=201)
def create_rule_set_version(
    rule_set_id: uuid.UUID,
    body: RuleSetVersionIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> RuleSetOut:
    """Korrektur für die Zone; gilt für spätere Simulationen aller Projekte in dieser Zone."""
    return service.create_office_version(db, rule_set_id, body, staff.actor_id)


@router.get("/admin/projects/{project_id}/rules", response_model=ProjectRulesOut)
def get_project_rules_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> ProjectRulesOut:
    return service.project_rules(db, project_id)


@router.get("/admin/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def get_project_overrides(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> list[ProjectOverrideOut]:
    return service.list_overrides(db, project_id)


@router.put("/admin/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def put_project_override(
    project_id: uuid.UUID,
    body: ProjectOverrideIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    """Korrektur nur für dieses Projekt (z. B. Lotissement); andere Projekte der Zone bleiben unverändert."""
    return service.set_override(db, project_id, body, staff.actor_id)


@router.delete(
    "/admin/projects/{project_id}/rule-overrides/{override_id}", response_model=list[ProjectOverrideOut]
)
def delete_project_override(
    project_id: uuid.UUID,
    override_id: uuid.UUID,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    return service.delete_override(db, project_id, override_id, staff.actor_id)
