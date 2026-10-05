"""Ein- und Ausgaben der Konfiguration des Hausmodells (docs/PLAN_HAUSMODELL.md 3.7–3.9; HM4).

Jede Antwort ist eine Simulation (D11, L7). Beträge sind brutto und gerundet: Gesamtpreis auf 1.000 €,
Aufpreise auf 100 € (E-HM-2, L1); exakte Beträge stehen nur im Snapshot für das Büro. Koordinaten in lokalen
Metern wie in H2 (Spez. 6.1).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.configuration.schemas import (
    AreasOut,
    CheckOut,
    Mode,
    OrientationOut,
    OutbuildingsOut,
    PlacementEvaluationOut,
    PlacementOut,
    PlacementRequest,
)
from app.house.contract import (
    HouseCatalog,
    HouseConfiguration,
    HouseResolutionNote,
    HouseRuleResult,
    HouseTemplate,
    HouseText,
    Status,
)
from app.house.schemas import SLUG_PATTERN
from app.site.schemas import LocalRing

SiteOutcome = Literal["deviation", "warning", "info"]


class HouseFactsOut(BaseModel):
    """Kennwerte und Umrisse aus der Hausbeschreibung (lokale Modellmeter, Y = Modellnord)."""

    storeys: str
    """`R`, `R+1` …"""
    roof_form: str
    """Dachform des Kerns (Ergänzung 11), nicht der Begriff der PLU-Regel."""
    pitch_deg: float | None
    """Neigung, wenn alle Dachflächen gleich geneigt sind."""
    pitches_deg: list[float]
    """Verschiedene Neigungen der Dachflächen, aufsteigend (Mansarde, Krüppelwalm: mehrere); Flachdach
    leer."""
    height_m: float
    """Höchster Punkt über Gelände (E-HM-11)."""
    eave_height_m: float
    floor_area_m2: float
    """Summe der Raumflächen."""
    footprint_m2: float
    """Fläche des Fassadenumrisses."""
    width_m: float
    depth_m: float
    facade_local: LocalRing
    projection_local: LocalRing
    facade_roles: dict[str, str]
    """Kante des Fassadenumrisses → Rolle."""
    facade_material: str
    roof_material: str


class HousePriceOut(BaseModel):
    """Richtpreis für den Kunden: brutto, gesamt auf 1.000 € und Aufpreise je Slot auf 100 € gerundet (L1)."""

    currency: Literal["EUR"]
    vat_rate: float
    gross_rounded: float
    deltas_rounded: dict[str, float]
    """Slot → Aufpreis der Wahl gegenüber dem Standard des Slots, brutto."""
    is_estimate: Literal[True] = True


class HouseTemplateFitOut(BaseModel):
    """Haustyp mit Zulässigkeit auf dem Grundstück, geprüft mit den Standards des Templates (Ergänzung 9)."""

    slug: str
    version: int
    catalog_version: int
    name: HouseText
    allowed: bool
    reasons: list[CheckOut]
    """Alle bindenden Verstöße (D12); leer, wenn der Typ wählbar ist."""
    hints: list[CheckOut]
    rotations: list[float]
    status: Status
    """Status der Katalogregeln mit den Standards."""
    price: HousePriceOut
    """Richtpreis mit den Standards („ab“)."""
    facts: HouseFactsOut


class HouseTemplatesOut(BaseModel):
    simulation: bool = True
    mode: Mode
    free_reason: str | None
    notices: list[str]
    site_revision: int
    templates: list[HouseTemplateFitOut]


class HouseTemplateRefOut(BaseModel):
    slug: str
    version: int
    catalog_version: int
    name: HouseText
    retired: bool
    """Die festgehaltene Templateversion ist zurückgezogen; die Konfiguration gilt unverändert (E-HM-7)."""


class HouseSiteResultOut(BaseModel):
    """Ergebnis der PLU-Prüfung mit Ergebnisart (3.7)."""

    outcome: SiteOutcome
    check: CheckOut


class HouseClientPrice(BaseModel):
    """Preis, den der Browser mit dem Kern gerechnet hat; der Server vergleicht ihn mit seinem (L5)."""

    net_amount: float = Field(ge=-1e9, le=1e9)
    domain_version: str = Field(max_length=40)


class HouseConfigurationPatch(BaseModel):
    """Teil-Update (JSON Merge Patch): nur gesendete Felder ändern sich, `null` löscht. Eine unzulässige
    Auswahl oder Lage wird gespeichert und bewertet (E-HM-6). Abgelehnt werden ein gesperrter Haustyp (D12),
    eine Auswahl, die der Kern nicht rechnet, und eine Drehung außer den vier zur Straße."""

    template_slug: str | None = Field(default=None, pattern=SLUG_PATTERN)
    configuration: HouseConfiguration | None = None
    """Vollständige Auswahl; `null` setzt die Standards des Templates."""
    placement: PlacementRequest | None = None
    boundary_options: dict[int, bool] | None = None
    client_price: HouseClientPrice | None = None
    """Wird nicht gespeichert; die Antwort sagt in `price_match`, ob er dem Serverpreis entspricht."""


class HouseConfigurationOut(BaseModel):
    simulation: bool = True
    project_id: uuid.UUID
    revision: int
    """0, solange noch nichts gespeichert ist."""
    mode: Mode
    free_reason: str | None
    notices: list[str]
    template: HouseTemplateRefOut | None
    update_available: bool
    """Es gibt eine neuere Template- oder freigegebene Katalogversion; übernommen wird sie ausdrücklich
    (3.9, HM6)."""
    configuration: HouseConfiguration
    placement: PlacementOut | None
    boundary_options: dict[str, bool]
    rotations: list[float]
    """Erlaubte Drehungen für das Haus mit dieser Auswahl."""
    facts: HouseFactsOut | None
    evaluation: PlacementEvaluationOut | None
    areas: AreasOut | None
    outbuildings: OutbuildingsOut | None
    """Terrasse, Carport und Zufahrten, von Python gesetzt (Ergänzung 7); `null` ohne Haustyp."""
    orientation: OrientationOut | None
    status: Status | None
    """Abgeleitet aus Katalogregeln und PLU-Prüfung, nie gespeichert (3.7)."""
    rule_results: list[HouseRuleResult]
    """Katalogregeln und Prüfungen der Geometrie aus dem Kern."""
    notes: list[HouseResolutionNote]
    site_results: list[HouseSiteResultOut]
    suggestion: PlacementOut | None
    """Nächste zulässige Lage, wenn die Lage Abweichungen hat (Ergänzung 9)."""
    price: HousePriceOut | None
    price_match: bool | None = None
    """Nur in der Antwort auf `PATCH` mit `client_price`: Browser und Server rechnen auf den Cent gleich."""
    domain_version: str | None
    site_changed: bool
    """Grundstück oder Regeln haben sich seit dem Speichern geändert (Prüfstempel, E-HM-7)."""
    updated_at: datetime | None


class HouseConfigurationStaffOut(HouseConfigurationOut):
    """Für das Büro zusätzlich die festgehaltenen Versionen und der Snapshot mit exakten Beträgen (3.8)."""

    template_version_id: uuid.UUID | None
    catalog_version_id: uuid.UUID | None
    snapshot: dict[str, Any] | None


class HouseDocumentsOut(BaseModel):
    """Festgehaltene Dokumente der Konfiguration für den Kern im Browser (Einheitspreise öffentlich,
    E-HM-20)."""

    template_version_id: uuid.UUID
    catalog_version_id: uuid.UUID
    template: HouseTemplate
    catalog: HouseCatalog
