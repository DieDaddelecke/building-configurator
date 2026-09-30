"""Endpunkte des Moduls G2 (Spez. 6.3, 6.4; Plan 3.4).

Kunden lesen die Regeln ihres Grundstücks hinter dem Feature-Flag `rules_simulation` (Plan 4.2).
Büro: Abdeckung und Regelwerke lesen (`architect`, `rules_admin`, `ops`), Korrekturen (`architect`,
`rules_admin`), Import, erneute Auswertung und das KI-Modell der Auswertung (`ops`, `rules_admin`). Keine
dieser Büroaktionen ist Voraussetzung für die Simulation beim Kunden (D11).
„Emprise Analyse“ (AN2): Der Architekt lädt für eigene Projekte ein règlement écrit hoch und wählt die
Zone (`require_owned_project`); die Datei liefert `GET /regulation-files/{id}` für die Zitate aus. Seit
AN3 auch Zusatzdokumente mit Lotwahl; seit AN4 Korrekturen je Projekt mit Begründung und Fundstelle und die
Formularbeschreibung der Regelarten (docs/PLAN_AN4_KORREKTUR.md).
"""

import uuid
from urllib.parse import quote

import httpx2
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.http import ExternalServiceError, shared_client
from app.platform import flags, rate_limit
from app.platform.auth.context import (
    Principal,
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
from app.rules import documents, model_choice, ocr, office, overrides, scheduling, service
from app.rules.schemas import (
    CoverageOut,
    ExtractIn,
    LotChoiceIn,
    ModelOptionOut,
    ProjectOverrideIn,
    ProjectOverrideOut,
    ProjectRegulationOut,
    ProjectRulesOut,
    RuleKindFormOut,
    RuleSetOut,
    RuleSetVersionIn,
    RulesImportIn,
    RulesModelIn,
    RulesModelOut,
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
AnyOrganisation = Depends(require_roles(Role.architect, Role.rules_admin, Role.ops, organisations=True))
"""Für Architekten aller Organisationen (AN6, PLAN_AN6_MANDANTEN 3.2); die übrigen `/admin`-Routen ohne
Projekt sind nur für die Organisation `operator`, die mit Projekt nur für die Organisation des Projekts."""


@router.get("/admin/rules/coverage", response_model=CoverageOut)
def rules_coverage(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> CoverageOut:
    """Abdeckung je Gemeinde und Kapitel mit Status, Läufen, Kosten und Monatsbudget (Plan 3.4, 6.8)."""
    return office.coverage(db, get_settings())


@router.get("/admin/rules/model", response_model=RulesModelOut)
def get_rules_model(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> RulesModelOut:
    """KI-Modell der Auswertung für Konfigurator und Analyse, mit Preisen und Kosten des Monats (PU11,
    VA09)."""
    return office.rules_model_out(db, get_settings())


@router.get("/admin/rules/models", response_model=list[ModelOptionOut])
def list_rules_models(
    staff: StaffPrincipal = Operator, client: httpx2.Client = Depends(shared_client)
) -> list[ModelOptionOut]:
    """Wählbare Modelle aus der Liste von OpenRouter mit erzwungenem Werkzeug (PU11); ohne PDF-Eingabe
    bekommen sie die Textschicht (PU12)."""
    try:
        options = model_choice.available_models(client, get_settings())
    except ExternalServiceError:
        raise Problem(503, "models_unavailable") from None
    return [
        ModelOptionOut(
            id=o.id,
            name=o.name,
            price_input_per_mtok=o.price_input_per_mtok,
            price_output_per_mtok=o.price_output_per_mtok,
            context_length=o.context_length,
            reads_pdf=o.reads_pdf,
        )
        for o in options
    ]


@router.put("/admin/rules/model", response_model=RulesModelOut)
def set_rules_model(
    body: RulesModelIn,
    staff: StaffPrincipal = Operator,
    db: Session = Depends(get_db),
    client: httpx2.Client = Depends(shared_client),
) -> RulesModelOut:
    """Modell für alle künftigen Auswertungen; die Vorgabe der Umgebung hebt die Wahl auf (PU11, VA09)."""
    settings = get_settings()
    reset = body.model == settings.rules_model
    try:
        options = [] if reset else model_choice.available_models(client, settings)
        name = staff.display_name or staff.email
        model_choice.choose(db, settings, options, body.model, staff.actor_id, name)
    except ExternalServiceError:
        raise Problem(503, "models_unavailable") from None
    except model_choice.ModelNotAvailable:
        raise Problem(422, "model_not_available") from None
    return office.rules_model_out(db, settings)


@router.post("/admin/rules/imports", status_code=202)
def start_rules_import(
    body: RulesImportIn, staff: StaffPrincipal = Operator, db: Session = Depends(get_db)
) -> dict[str, uuid.UUID]:
    return {"job_id": scheduling.enqueue_import(db, body.communes, body.force, staff.actor_id)}


@router.post("/admin/rules/chapters/{chapter_id}/extract", status_code=202)
def start_chapter_extraction(
    chapter_id: uuid.UUID, body: ExtractIn, staff: StaffPrincipal = Operator, db: Session = Depends(get_db)
) -> dict[str, uuid.UUID]:
    """Kapitel erneut auswerten (z. B. nach neuer Prompt-Version oder gescheitertem Lauf); kostet Token."""
    return {"job_id": scheduling.enqueue_extract(db, chapter_id, body.force, staff.actor_id)}


@router.get("/admin/rule-sets/{rule_set_id}", response_model=RuleSetOut)
def get_rule_set(
    rule_set_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> RuleSetOut:
    return office.rule_set_detail(db, rule_set_id)


@router.post("/admin/rule-sets/{rule_set_id}/versions", response_model=RuleSetOut, status_code=201)
def create_rule_set_version(
    rule_set_id: uuid.UUID,
    body: RuleSetVersionIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> RuleSetOut:
    """Korrektur für die Zone; gilt für spätere Simulationen aller Projekte in dieser Zone."""
    return office.create_office_version(db, rule_set_id, body, staff.actor_id)


@router.get("/admin/projects/{project_id}/rules", response_model=ProjectRulesOut)
def get_project_rules_staff(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> ProjectRulesOut:
    return service.project_rules(db, project_id)


@router.get("/admin/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def get_project_overrides(
    project_id: uuid.UUID, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> list[ProjectOverrideOut]:
    return overrides.list_overrides(db, project_id)


@router.put("/admin/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def put_project_override(
    project_id: uuid.UUID,
    body: ProjectOverrideIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    """Korrektur nur für dieses Projekt (z. B. Lotissement); andere Projekte der Zone bleiben unverändert."""
    return overrides.set_override(db, project_id, body, staff.actor_id)


@router.delete(
    "/admin/projects/{project_id}/rule-overrides/{override_id}", response_model=list[ProjectOverrideOut]
)
def delete_project_override(
    project_id: uuid.UUID,
    override_id: uuid.UUID,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    return overrides.delete_override(db, project_id, override_id, staff.actor_id)


@router.get("/admin/rule-kinds", response_model=list[RuleKindFormOut])
def get_rule_kinds(staff: StaffPrincipal = AnyOrganisation) -> list[RuleKindFormOut]:
    """Formularbeschreibung der Regelarten aus demselben Schema wie Prüfung und Modellausgabe (AN4, 3.1)."""
    return office.rule_kind_forms()


# ---------------------------------------------------------------------------
# Korrekturen im Analyse-Produkt (AN4, docs/PLAN_AN4_KORREKTUR.md 3.2): der Architekt für eigene Projekte,
# mit Pflichtbegründung und optionaler Fundstelle; dieselben Funktionen wie die Büro-Endpunkte oben
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def list_own_overrides(
    project_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    """Korrekturen des Projekts mit Begründung, Fundstelle und ob sie wirken."""
    return overrides.list_overrides(db, project_id)


@router.put("/projects/{project_id}/rule-overrides", response_model=list[ProjectOverrideOut])
def put_own_override(
    project_id: uuid.UUID,
    body: ProjectOverrideIn,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    """Regel korrigieren oder ergänzen; wirkt sofort in Regeln, Baurahmen und Analyse (kostet nichts)."""
    return overrides.set_override(db, project_id, body, staff.actor_id)


@router.delete("/projects/{project_id}/rule-overrides/{override_id}", response_model=list[ProjectOverrideOut])
def delete_own_override(
    project_id: uuid.UUID,
    override_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> list[ProjectOverrideOut]:
    """Korrektur zurücknehmen: Es gilt wieder der gelesene Wert."""
    return overrides.delete_override(db, project_id, override_id, staff.actor_id)


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
    staff: Principal = Depends(require_owned_project),
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
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """règlement écrit als PDF hochladen (3.2). Ersetzt ein vorhandenes PLU des Projekts. Gelesen wird im
    Job `rules_document_read`; ausgewertet erst nach der Zonenwahl – das Hochladen kostet nichts.
    Mit `du_type` `lotissement` oder `cahier_des_charges` ein Zusatzdokument (AN3), höchstens drei."""
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
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """Zone und Kapitel wählen (3.3). **Kostet**: plant die Auswertung des Kapitels ein, wenn sich seine
    Eingabe ändert (neues Kapitel oder neuer Sektor); sonst nichts."""
    rate_limit.check(request, "regulation_write", get_settings().site_write_limit_per_hour, 3600)
    return documents.choose_zone(db, get_settings(), project_id, document_id, body, staff.actor_id)


@router.put("/projects/{project_id}/regulations/{document_id}/lot", response_model=ProjectRegulationOut)
def choose_regulation_lot(
    request: Request,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    body: LotChoiceIn,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """Lot eines Zusatzdokuments wählen (AN3, docs/PLAN_AN3_ANALYSE.md 3.7). **Kostet** wie die Zonenwahl:
    plant die Auswertung des Dokuments ein, wenn ein neues Lot dazukommt."""
    rate_limit.check(request, "regulation_write", get_settings().site_write_limit_per_hour, 3600)
    return documents.choose_lot(db, get_settings(), project_id, document_id, body, staff.actor_id)


@router.post(
    "/projects/{project_id}/regulations/{document_id}/ocr",
    response_model=ProjectRegulationOut,
    status_code=202,
)
def request_regulation_ocr(
    request: Request,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ProjectRegulationOut:
    """Texterkennung der Seiten ohne Textschicht bestätigen (AN7, docs/PLAN_AN7_SCAN.md 3.2). Kostet nichts,
    dauert je Seite einige Sekunden; läuft sie schon oder ist alles erkannt, ändert sich nichts."""
    rate_limit.check(request, "regulation_write", get_settings().site_write_limit_per_hour, 3600)
    return ocr.request(db, project_id, document_id, staff.actor_id)


@router.delete("/projects/{project_id}/regulations/{document_id}", status_code=204)
def remove_project_regulation(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
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
    file_id: uuid.UUID, staff: StaffPrincipal = AnyOrganisation, db: Session = Depends(get_db)
) -> Response:
    """Planunterlage als PDF, **inline**, damit `#page=` im Zitat auf die Seite springt (3.6). Nur für
    Mitarbeitende; eine fremde Organisation nur Dateien, die ein eigenes Projekt nutzt (AN6). Die Datei ist
    beim Hochladen als PDF geprüft, `nosniff` verhindert eine andere Deutung."""
    content, filename = documents.file_content(
        db, file_id, None if staff.is_operator else staff.organisation_id
    )
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
