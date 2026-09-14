"""Ein- und Ausgaben der Regelwerks-API (Spez. 6.3, 6.4; Plan 3.4).

Jede Kundenantwort trägt `simulation: true`: Die Regeln sind automatisch ausgewertet und nicht verbindlich
(Entscheidung D11, L7).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.rules.domain.kinds import BuildingKind, RuleKind

RuleStatus = Literal["effective", "unknown", "not_regulated", "text_only"]
ZoneStatus = Literal["simulated", "office_reviewed", "in_progress", "unavailable"]


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
    """Planunterlage im GPU mit Seitensprung (`#page=`)."""
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
    title: str
    du_type: str
    gpu_doc_id: str
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
    chapters: list[ChapterCoverageOut]


class CoverageOut(BaseModel):
    configured: bool
    """API-Schlüssel für die Claude API gesetzt."""
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
    force: bool = True
