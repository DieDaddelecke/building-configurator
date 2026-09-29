"""Ein- und Ausgaben der Regelwerks-API (Spez. 6.3, 6.4; Plan 3.4).

Jede Kundenantwort trägt `simulation: true`: Die Regeln sind automatisch ausgewertet und nicht verbindlich
(Entscheidung D11, L7).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.rules.domain.kinds import BuildingKind, RuleKind

RuleStatus = Literal["effective", "unknown", "not_regulated", "text_only"]
ZoneStatus = Literal["simulated", "office_reviewed", "outdated", "in_progress", "unavailable"]
"""`outdated`: Regeln des vorigen Planstands, solange der neue nicht ausgewertet oder nicht lesbar ist."""


class RuleOut(BaseModel):
    kind: str
    building_kind: str
    status: RuleStatus
    reason: str | None
    params: dict[str, Any]
    page: int | None
    quote: str | None
    quote_verified: bool
    source_url: str | None
    """Planunterlage mit Seitensprung (`#page=`): im GPU oder, hochgeladen, `/api/v1/regulation-files/…`."""
    confidence: float
    notes: str | None
    origin: Literal["extraction", "office", "project"]
    source_document_id: uuid.UUID | None = None
    """Dokument der Fundstelle (Planstand oder Zusatzdokument). Bei einer Projektkorrektur mit Fundstelle in
    einem Zusatzdokument ist sie eine Übernahme daraus (AN4, docs/PLAN_AN4_KORREKTUR.md 3.4)."""
    search_note: str | None = None
    """Nachsuche (PLAN_G2_VOLLSTAENDIGKEIT 3.7): bei `not_found_after_search` die geprüften Stellen und
    Begriffe, bei `not_expressible` die Seite des Hinweises; sonst leer."""
    from_scan: bool = False
    """Zitat auf einer Seite, deren Text per Texterkennung gelesen wurde (AN7, PLAN_AN7_SCAN 3.3)."""


class RuleDetailOut(RuleOut):
    detail: str | None
    alternatives: list[dict[str, Any]]
    similarity: float


class PassageOut(BaseModel):
    """Textstelle mit Vorschriftscharakter (PLAN_G2_VOLLSTAENDIGKEIT 3.3); Seite im Originaldokument."""

    page: int
    text: str
    reason: str | None = None
    """Nur bei nicht einschlägigen Stellen: Grund der Nachsuche (`networks`, `other_use` …)."""


class VersionOut(BaseModel):
    id: uuid.UUID
    version: int
    status: Literal["simulated", "office_reviewed", "retired"]
    origin: Literal["extraction", "office"]
    model: str | None
    created_at: datetime
    created_by: str | None
    note: str | None
    coverage: dict[str, int]
    """Zählung je Status, `mandatory_unknown`; seit der Nachsuche auch `passages_total`,
    `passages_assigned`, `passages_out_of_scope`, `passages_open`, `gap_search` (1 = gelaufen)."""
    open_passages: list[PassageOut] = []
    """Stellen ohne Regel: Der Architekt prüft sie selbst (keine stille Lücke)."""
    out_of_scope_passages: list[PassageOut] = []
    """Stellen, die die Nachsuche als „betrifft kein Einfamilienhaus“ eingestuft hat."""


class ZoneRulesOut(BaseModel):
    code: str
    label: str | None
    chapter_code: str | None
    area_m2: float
    share: float
    status: ZoneStatus
    reason: str | None
    rule_set_id: uuid.UUID | None
    version: VersionOut | None
    rules: list[RuleOut]
    hints: list[RuleOut]


class IgnoredZoneOut(BaseModel):
    code: str
    area_m2: float


class OverlayOut(BaseModel):
    category: Literal["prescription", "information", "servitude"]
    type_code: str | None
    label: str
    endpoint: str


class PlanOut(BaseModel):
    id: uuid.UUID
    origin: Literal["gpu", "upload"]
    """`upload`: vom Architekten hochgeladenes règlement écrit (AN2); dann ohne GPU-Kennung und -Datum."""
    title: str
    du_type: str
    gpu_doc_id: str | None
    gpu_update_date: str | None
    regulation_url: str | None


class ProjectRulesOut(BaseModel):
    simulation: Literal[True] = True
    status: Literal["ok", "partial", "in_progress", "unavailable"]
    reason: str | None
    commune_insee: str | None
    plan: PlanOut | None
    zones: list[ZoneRulesOut]
    ignored_zones: list[IgnoredZoneOut]
    uncovered_share: float = 0.0
    """Anteil des Grundstücks ohne Zone des Planwerks (z. B. Teil in einem Nachbarplan); ab 1 % Warnung."""
    overlays: list[OverlayOut]
    warnings: list[str]
    notices: list[str]


class ChapterCoverageOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    first_page: int
    last_page: int
    sectors: list[str]
    status: Literal["pending", "extracting", "succeeded", "failed"]
    error: str | None
    updated_at: datetime
    runs: int
    cost_usd: float
    last_model: str | None
    rule_sets: dict[str, VersionOut | None]
    rule_set_ids: dict[str, uuid.UUID]


class CommuneCoverageOut(BaseModel):
    commune_insee: str
    status: str
    error: str | None
    checked_at: datetime | None
    plan: PlanOut | None
    fallback_plan: PlanOut | None = None
    """Voriger Planstand, den Kunden als „veraltet“ sehen, bis `plan` ausgewertet ist."""
    chapters: list[ChapterCoverageOut]


class CoverageOut(BaseModel):
    configured: bool
    """API-Schlüssel für OpenRouter gesetzt."""
    model: str
    month_cost_usd: float
    budget_month_usd: float
    communes: list[CommuneCoverageOut]


class RulesModelOut(BaseModel):
    """KI-Modell der Auswertung für die ganze Instanz (PLAN_AN2_PLU 8, PU11)."""

    model: str
    source: Literal["setting", "default"]
    """`default`: Modell aus der Umgebung; `setting`: im Büro gewählt."""
    default_model: str
    price_input_per_mtok: float
    price_output_per_mtok: float
    updated_at: datetime | None
    input: Literal["pdf", "text"]
    """Wie die Reglements ans Modell gehen: als PDF oder als Textschicht (PU12)."""
    configured: bool
    """API-Schlüssel für OpenRouter gesetzt."""
    month_cost_usd: float
    budget_month_usd: float
    updated_by_name: str | None = None
    """Wer zuletzt gewählt hat (Anzeigename; die Wahl gilt für beide Produkte, VA09)."""


class ModelOptionOut(BaseModel):
    id: str
    name: str
    price_input_per_mtok: float
    price_output_per_mtok: float
    context_length: int | None
    reads_pdf: bool


class RulesModelIn(BaseModel):
    model: str = Field(min_length=3, max_length=60)


class RuleSetOut(BaseModel):
    id: uuid.UUID
    zone_code: str
    plan: PlanOut
    current: VersionOut | None
    versions: list[VersionOut]
    rules: list[RuleDetailOut]


class RuleIn(BaseModel):
    kind: RuleKind
    building_kind: BuildingKind = "main"
    status: RuleStatus
    params: dict[str, Any] = Field(default_factory=dict)
    page: int | None = Field(default=None, ge=1)
    quote: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=2000)


class RuleSetVersionIn(BaseModel):
    """Korrektur für die Zone: vollständige Liste der Regeln; ergibt eine neue Version `office_reviewed`."""

    rules: list[RuleIn] = Field(max_length=200)
    note: str = Field(min_length=3, max_length=2000)


class RuleSourceIn(BaseModel):
    """Fundstelle einer Korrektur (AN4, docs/PLAN_AN4_KORREKTUR.md 3.2): ein Dokument des Projekts, eine
    Seite und optional ein Zitat, das auf der Seite gesucht wird."""

    document_id: uuid.UUID
    page: int = Field(ge=1)
    quote: str | None = Field(default=None, max_length=4000)


class ProjectOverrideIn(BaseModel):
    """Korrektur nur für ein Projekt (z. B. Regeln eines Lotissement). Die Begründung ist Pflicht und nur für
    das Büro sichtbar."""

    zone_code: str = Field(min_length=1, max_length=20)
    kind: RuleKind
    building_kind: BuildingKind = "main"
    status: Literal["effective", "unknown", "not_regulated"]
    params: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(min_length=3, max_length=2000)
    source: RuleSourceIn | None = None


class RuleSourceOut(BaseModel):
    document_id: uuid.UUID | None
    """Leer, wenn die Datei nicht mehr besteht; Seite und Zitat bleiben als Text."""
    document_title: str | None
    page: int
    quote: str | None
    quote_verified: bool
    source_url: str | None
    attached: bool
    """Hängt das Dokument noch am Projekt (PLU, Zusatzdokument oder Planstand der Regeln)?"""


class ProjectOverrideOut(BaseModel):
    id: uuid.UUID
    zone_code: str
    kind: str
    building_kind: str
    status: RuleStatus
    params: dict[str, Any]
    note: str | None
    source: RuleSourceOut | None
    active: bool
    """Wirkt die Korrektur? Nicht, wenn das Projekt die Zone nicht mehr hat (Zone oder PLU gewechselt)."""
    created_at: datetime | None
    created_by: str | None
    updated_at: datetime
    updated_by: str | None


class ParamFieldOut(BaseModel):
    """Feld des Regelformulars (AN4, 3.1), abgeleitet aus `rules/domain/kinds.py`."""

    name: str
    type: Literal["number", "flag", "choice", "items", "text"]
    required: bool
    default: Any = None
    options: list[str]
    min: float | None = None
    max: float | None = None
    unit: Literal["m", "m2", "deg", "share", "factor", "per_area", "count"] | None = None


class RuleKindFormOut(BaseModel):
    kind: RuleKind
    building_specific: bool
    """Kann je Baukörper verschieden sein (Abstände, Höhe, Dach, Fassade); sonst gilt sie fürs Grundstück."""
    mandatory: bool
    params: list[ParamFieldOut]


class RulesImportIn(BaseModel):
    communes: list[str] | None = Field(default=None, max_length=50)
    force: bool = False


class ExtractIn(BaseModel):
    force: bool = False
    """Ohne `force` werden gespeicherte Aufrufe derselben Eingabe genutzt; mit `force` kostet es erneut."""


# ---------------------------------------------------------------------------
# Hochgeladenes Reglement (AN2, docs/PLAN_AN2_PLU.md)
# ---------------------------------------------------------------------------

UploadDuType = Literal["PLU", "PLUi", "PSMV", "lotissement", "cahier_des_charges"]
"""Planwerke (PLU, PLUi, PSMV) und Zusatzdokumente (AN3, `extraction.SUPPLEMENT_DU_TYPES`)."""
ZONE_CODE_PATTERN = r"^[0-9A-Za-z][0-9A-Za-z_\-]{0,19}$"
LOT_PATTERN = r"^[0-9A-Za-z][0-9A-Za-z_\-]{0,15}$"


class DocumentChapterOut(BaseModel):
    """Kapitel eines hochgeladenen Reglements. `idle`: erkannt, aber für keine Zone gewählt – ohne Kosten."""

    code: str
    title: str
    first_page: int
    last_page: int
    general_pages: list[int]
    detection: str
    sectors: list[str]
    suggested_sectors: list[str]
    status: Literal["idle", "pending", "extracting", "succeeded", "failed"]
    error: str | None
    runs: int
    cost_usd: float


class OcrOut(BaseModel):
    """Texterkennung der Seiten ohne Textschicht (AN7, docs/PLAN_AN7_SCAN.md 3.2)."""

    state: Literal["none", "offered", "running", "done", "failed"]
    """`offered`: Scan erkannt, der Hinweis wartet auf Bestätigung; `none` bei einzelnen leeren Seiten, die
    noch niemand erkennen ließ."""
    pages_total: int
    """Seiten ohne Textschicht."""
    pages_done: int
    uncertain_pages: list[int]
    """Erkannt, aber mit geringer Sicherheit (mittlere Wortsicherheit unter 70)."""
    still_empty_pages: list[int]
    """Auch nach der Erkennung ohne Text (Pläne, Abbildungen, leere Seiten)."""
    estimated_seconds: int
    """Geschätzte Dauer für die noch offenen Seiten."""
    error: str | None


class RegulationDocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    du_type: str
    status: Literal["importing", "active", "failed", "scan"]
    """`importing`: der Job liest noch Text und Kapitel; `failed` mit Grund in `error`; `scan`: gescanntes
    PDF, nutzbar erst nach der Texterkennung (`ocr`, AN7)."""
    error: str | None
    file_name: str | None
    file_url: str | None
    sha256: str | None = None
    """Prüfsumme der Datei; der Bericht nennt sie gekürzt (AN5 3.6)."""
    page_count: int | None
    empty_pages: list[int]
    """Seiten ohne Textschicht im PDF, auch nach einer Texterkennung (deren Stand steht in `ocr`)."""
    ocr: OcrOut | None = None
    created_at: datetime
    chapters: list[DocumentChapterOut]


class ProjectRegulationOut(BaseModel):
    role: Literal["plu", "supplement"]
    """`plu`: das règlement écrit, aus dem Regeln und Baurahmen entstehen. `supplement`: Zusatzdokument
    (lotissement, cahier des charges), nur im Vergleich der Analyse (AN3)."""
    zone_code: str | None
    """Beim PLU der Sektor (`Uba`), beim Zusatzdokument das Lot (`Lot-12`, ohne Lot `Ensemble`)."""
    chapter_code: str | None
    document: RegulationDocumentOut


class LotChoiceIn(BaseModel):
    """Lot eines Zusatzdokuments wählen (AN3, docs/PLAN_AN3_ANALYSE.md 3.7). Ohne Lot gilt das Dokument als
    Ganzes (`Ensemble`); ein Seitenbereich ersetzt das ganze Dokument, z. B. über 150 Seiten."""

    lot: str | None = Field(default=None, pattern=LOT_PATTERN)
    first_page: int | None = Field(default=None, ge=1)
    last_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> "LotChoiceIn":
        if (self.first_page is None) != (self.last_page is None):
            raise ValueError("first_page und last_page nur gemeinsam")
        if self.first_page is not None and self.last_page is not None and self.last_page < self.first_page:
            raise ValueError("last_page vor first_page")
        return self


class ZoneChoiceIn(BaseModel):
    """Zone eines hochgeladenen Reglements wählen: erkanntes Kapitel oder Seitenbereich von Hand (3.3).

    `zone_code` ist der Sektor, für den ausgewertet wird (`Uba` im Kapitel `Ub`). Ohne `first_page` gilt
    das erkannte Kapitel `chapter_code`; mit `first_page`/`last_page` ein Kapitel von Hand (Code:
    `chapter_code`, sonst der Zonencode), optional mit eigenem Bereich der allgemeinen Bestimmungen."""

    zone_code: str = Field(pattern=ZONE_CODE_PATTERN)
    chapter_code: str | None = Field(default=None, pattern=ZONE_CODE_PATTERN)
    first_page: int | None = Field(default=None, ge=1)
    last_page: int | None = Field(default=None, ge=1)
    general_first_page: int | None = Field(default=None, ge=1)
    general_last_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> "ZoneChoiceIn":
        if (self.first_page is None) != (self.last_page is None):
            raise ValueError("first_page und last_page nur gemeinsam")
        if (self.general_first_page is None) != (self.general_last_page is None):
            raise ValueError("general_first_page und general_last_page nur gemeinsam")
        if self.first_page is None and self.chapter_code is None:
            raise ValueError("chapter_code oder Seitenbereich angeben")
        if self.first_page is not None and self.last_page is not None and self.last_page < self.first_page:
            raise ValueError("last_page vor first_page")
        if (
            self.general_first_page is not None
            and self.general_last_page is not None
            and self.general_last_page < self.general_first_page
        ):
            raise ValueError("general_last_page vor general_first_page")
        return self


# ---------------------------------------------------------------------------
# Referenzlisten in der gemeinsamen Verwaltung (PLAN_G2_VOLLSTAENDIGKEIT 3.10, VA03, VA10)
# ---------------------------------------------------------------------------

ExpectedStatus = Literal["effective", "not_regulated", "text_only", "graphic_reference", "not_expressible"]
MeasureOutcome = Literal["hit", "wrong_value", "named_gap", "dismissed", "silent_gap"]


class ReferenceEntryIn(BaseModel):
    kind: RuleKind
    building_kind: BuildingKind
    expected: ExpectedStatus
    params: dict[str, Any] = {}
    """Nur die maßgeblichen Parameter; verglichen wird nur, was hier steht."""
    page: int | None = Field(default=None, ge=1)
    quote: str = Field(min_length=3, max_length=4000)
    note: str = Field(default="", max_length=2000)


class ReferenceEntryOut(ReferenceEntryIn):
    id: uuid.UUID
    position: int


class ReferenceListIn(BaseModel):
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_title: str = Field(min_length=1, max_length=300)
    sector: str = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=4000)


class ReferenceListPatch(BaseModel):
    document_title: str | None = Field(default=None, min_length=1, max_length=300)
    status: Literal["draft", "checked"] | None = None
    note: str | None = Field(default=None, max_length=4000)


class ReferenceSummaryOut(BaseModel):
    """Messung der aktuellen Auswertung dieser Instanz, kurz; leer, wenn das Dokument hier fehlt."""

    version: int
    recall: float
    counts: dict[str, int]


class ReferenceListOut(BaseModel):
    id: uuid.UUID
    document_sha256: str
    document_title: str
    sector: str
    status: Literal["draft", "checked"]
    note: str
    entries_count: int
    updated_at: datetime
    updated_by_name: str | None
    summary: ReferenceSummaryOut | None


class ReferenceListDetailOut(ReferenceListOut):
    entries: list[ReferenceEntryOut]


class ReferenceCandidateOut(BaseModel):
    """Ausgewertetes Dokument dieser Instanz, für das eine Liste angelegt werden kann."""

    document_sha256: str
    document_title: str
    sectors: list[str]


class FoundRuleOut(BaseModel):
    kind: str
    building_kind: str
    status: str
    reason: str | None
    params: dict[str, Any]
    page: int | None


class MeasuredEntryOut(BaseModel):
    entry_id: uuid.UUID
    outcome: MeasureOutcome
    detail: str
    found: FoundRuleOut | None


class ReferenceMeasurementOut(BaseModel):
    version: int
    versions: list[int]
    """Alle Versionen dieses Sektors in dieser Instanz, zum Vergleich früherer Auswertungen."""
    model: str | None
    created_at: datetime
    recall: float
    counts: dict[str, int]
    coverage: dict[str, int]
    results: list[MeasuredEntryOut]
    extra: list[FoundRuleOut]
