"""Endpunkte des Moduls G2 (Spez. 6.3, 6.4; Plan 3.4).

Kunden lesen die Regeln ihres Grundstücks hinter dem Feature-Flag `rules_simulation` (Plan 4.2).
Büro: Abdeckung und Regelwerke lesen (`architect`, `rules_admin`, `ops`), Korrekturen (`architect`,
`rules_admin`), Import und erneute Auswertung (`ops`, `rules_admin`). Keine dieser Büroaktionen ist
Voraussetzung für die Simulation beim Kunden (D11).
„Emprise Analyse“ (AN2): Der Architekt lädt für eigene Projekte ein règlement écrit hoch und wählt die
Zone (`require_owned_project`); die Datei liefert `GET /regulation-files/{id}` für die Zitate aus.
"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    RequestAuth,
    Role,
    StaffPrincipal,
    get_auth,
    require_owned_project,
    require_project_access,
    require_roles,
)
from app.platform.db import get_db
from app.platform.problems import Problem
from app.rules import documents, service
from app.rules.schemas import (
    CoverageOut,
    ExtractIn,
    ProjectOverrideIn,
    ProjectOverrideOut,
    ProjectRegulationOut,
    ProjectRulesOut,
    RuleSetOut,
    RuleSetVersionIn,
    RulesImportIn,
    UploadDuType,
    ZoneChoiceIn,
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


# ---------------------------------------------------------------------------
# Hochgeladenes Reglement (AN2, docs/PLAN_AN2_PLU.md): nur Architekt und eigenes Projekt, weil die
# Zonenwahl eine bezahlte Auswertung auslöst (3.7)
# ---------------------------------------------------------------------------

UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Datei stückweise lesen und bei Überschreiten der Grenze abbrechen, nicht erst danach."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise Problem(413, "upload_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/projects/{project_id}/regulations", response_model=list[ProjectRegulationOut])
def list_project_regulations(
    project_id: uuid.UUID,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> list[ProjectRegulationOut]:
    """Hochgeladene Dokumente des Projekts mit Lesestand, erkannten Kapiteln und Stand der Auswertung."""
    return documents.project_regulations(db, project_id)


@router.post("/projects/{project_id}/regulations", response_model=ProjectRegulationOut, status_code=202)
async def upload_project_regulation(
    request: Request,
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=300),
    du_type: UploadDuType = Form(default="PLU"),
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """règlement écrit als PDF hochladen (3.2). Ersetzt ein vorhandenes PLU des Projekts. Gelesen wird im
    Job `rules_document_read`; ausgewertet erst nach der Zonenwahl – das Hochladen kostet nichts."""
    settings = get_settings()
    rate_limit.check(request, "regulation_write", settings.site_write_limit_per_hour, 3600)
    data = await _read_limited(file, settings.regulation_upload_max_bytes)
    if not data:
        raise Problem(422, "not_a_pdf")
    # Prüfung des PDF und Ablage im Objektspeicher dauern bei großen Dateien Sekunden: nicht im Event-Loop
    return await run_in_threadpool(
        documents.upload,
        db,
        project_id,
        file_name=file.filename or "",
        data=data,
        title=title,
        du_type=du_type,
        actor=staff.actor_id,
    )


@router.put("/projects/{project_id}/regulations/{document_id}/zone", response_model=ProjectRegulationOut)
def choose_regulation_zone(
    request: Request,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    body: ZoneChoiceIn,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """Zone und Kapitel wählen (3.3). **Kostet**: plant die Auswertung des Kapitels ein, wenn sich seine
    Eingabe ändert (neues Kapitel oder neuer Sektor); sonst nichts."""
    rate_limit.check(request, "regulation_write", get_settings().site_write_limit_per_hour, 3600)
    return documents.choose_zone(db, get_settings(), project_id, document_id, body, staff.actor_id)


@router.delete("/projects/{project_id}/regulations/{document_id}", status_code=204)
def remove_project_regulation(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> Response:
    """Dokument vom Projekt lösen; das Dokument bleibt für andere Projekte bestehen (E-AN2-4)."""
    documents.remove(db, project_id, document_id, staff.actor_id)
    return Response(status_code=204)


@router.get(
    "/regulation-files/{file_id}",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def regulation_file(
    file_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> Response:
    """Planunterlage als PDF, **inline**, damit `#page=` im Zitat auf die Seite springt (3.6). Nur für
    das Büro; die Datei ist beim Hochladen als PDF geprüft, `nosniff` verhindert eine andere Deutung."""
    content, filename = documents.file_content(db, file_id)
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "").replace("?", "_")
    disposition = f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )
