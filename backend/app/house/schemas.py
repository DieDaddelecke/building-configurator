"""Ein- und Ausgaben der Büro-API des Hausmodells (HM3: IFC-Import, Entwurf, Prüfung, Freigabe).

Dokumente, Entwurf und Importbericht sind die Modelle aus `contract` und `domain.draft`; hier nur die
Hülle für die Oberfläche unter `/buero/katalog`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.house.contract import HouseCompatibilityIssue, HouseTemplate, HouseText
from app.house.domain.draft import HouseDraftDecisions, HouseImportReport

TemplateStatus = Literal["draft", "reviewed", "published", "rejected", "retired"]
CatalogStatus = Literal["draft", "published", "retired"]
SLUG_PATTERN = r"^[a-z][a-z0-9_]{1,59}$"
"""Wie die Kennung der Haustypen im Katalog (`catalog/service.py` SLUG_RE, Konfigurator `type`), damit ein
importierter Haustyp dort unter derselben Kennung erscheinen kann; Teilmenge der Vertrags-ID."""


class HouseJobOut(BaseModel):
    status: Literal["queued", "running", "succeeded", "failed"]
    attempts: int
    max_attempts: int


class HouseCompatibilityOut(BaseModel):
    """Prüfbefund aus `engine` für die Katalogversion des Entwurfs."""

    catalog_version: int
    domain_version: str
    supported: bool
    issues: list[HouseCompatibilityIssue]
    checked_at: datetime
    checked_by: str | None
    approved_at: datetime | None
    approved_by: str | None


class HouseChoiceOut(BaseModel):
    id: str
    name: HouseText


class HouseSlotChoiceOut(BaseModel):
    id: str
    category: str
    name: HouseText
    values: list[HouseChoiceOut]


class HouseCatalogChoicesOut(BaseModel):
    """Was der Entwurf zur Wahl stellt: Raumtypen, Slots und Werte der Katalogversion des Entwurfs."""

    version: int
    current: bool
    """Die Katalogversion ist die zuletzt veröffentlichte des Markts; sonst nimmt die nächste Änderung des
    Entwurfs die neue."""
    room_types: list[HouseChoiceOut]
    slots: list[HouseSlotChoiceOut]


class HouseTemplateVersionSummaryOut(BaseModel):
    version: int
    status: TemplateStatus
    ifc_file_name: str
    created_at: datetime
    created_by: str | None
    importing: bool
    """Der Job liest die Datei noch; Entwurf und Bericht fehlen."""
    publishable: bool | None


class HouseTemplateSummaryOut(BaseModel):
    slug: str
    name: HouseText | None
    current_version: int | None
    """Zuletzt veröffentlichte Version."""
    versions: list[HouseTemplateVersionSummaryOut]
    """Neueste zuerst."""


class HouseTemplateVersionOut(BaseModel):
    slug: str
    version: int
    status: TemplateStatus
    current: bool
    ifc_file_name: str
    ifc_sha256: str
    ifc_size_bytes: int
    created_at: datetime
    created_by: str | None
    reviewed_at: datetime | None
    reviewed_by: str | None
    published_at: datetime | None
    published_by: str | None
    rejected_at: datetime | None
    rejected_by: str | None
    retired_at: datetime | None
    retired_by: str | None
    job: HouseJobOut | None
    decisions: HouseDraftDecisions
    template: HouseTemplate | None
    """Template-Entwurf, sobald er sich bilden ließ; Grundlage der Vorschau."""
    report: HouseImportReport | None
    catalog: HouseCatalogChoicesOut
    compatibility: HouseCompatibilityOut | None
    people: dict[str, str]
    """Konto-ID → Anzeigename oder E-Mail für die `…_by`-Felder; `cli` und unbekannte IDs fehlen."""


class HouseCatalogVersionOut(BaseModel):
    market: Literal["FR"]
    version: int
    status: CatalogStatus
    current: bool
    sha256: str
    source: str
    created_at: datetime
    created_by: str | None
    published_at: datetime | None
    published_by: str | None
    room_types: int
    slots: int
    option_values: int
