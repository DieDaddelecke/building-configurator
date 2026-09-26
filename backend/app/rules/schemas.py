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


class RuleDetailOut(RuleOut):
    detail: str | None
    alternatives: list[dict[str, Any]]
    similarity: float


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


class ProjectOverrideIn(BaseModel):
    """Korrektur nur für ein Projekt (z. B. Regeln eines Lotissement)."""

    zone_code: str = Field(min_length=1, max_length=20)
    kind: RuleKind
    building_kind: BuildingKind = "main"
    status: RuleStatus
    params: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(min_length=3, max_length=2000)


class ProjectOverrideOut(BaseModel):
    id: uuid.UUID
    zone_code: str
    kind: str
    building_kind: str
    status: RuleStatus
    params: dict[str, Any]
    note: str | None
    updated_at: datetime
    updated_by: str | None


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


class RegulationDocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    du_type: str
    status: Literal["importing", "active", "failed"]
    """`importing`: der Job liest noch Text und Kapitel; `failed` mit Grund in `error`."""
    error: str | None
    file_name: str | None
    file_url: str | None
    page_count: int | None
    empty_pages: list[int]
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
