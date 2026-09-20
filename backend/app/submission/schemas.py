"""Ein- und Ausgaben der Übergabe (docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.3)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.configuration.schemas import CheckOut, RangeOut

DossierStatus = Literal["pending", "ready", "failed"]


class SubmitIn(BaseModel):
    review_stamp: str = Field(min_length=3, max_length=200)
    """Prüfstempel der angezeigten Auswertung (`ConfigurationOut.review_stamp`, V 3.3)."""
    design_confirmation: bool
    """Bestätigung „unverbindliche Vorentwurfsskizze“ (Spez. 5.10.2 Punkt 4)."""
    transmission_design: bool
    """Einwilligung in die Übermittlung an das Büro (Punkt 5)."""
    deviations_acknowledged: bool = False
    """„Mit Abweichungen zur Prüfung übergeben“ (Punkt 6, V 3.4)."""
    code: str | None = Field(default=None, pattern=r"^\d{6}$")
    """Code aus `POST …/inquiry/contact`, solange die Adresse noch nicht bestätigt ist."""


class SubmitOut(BaseModel):
    number: str
    sequence: int
    status: Literal["submitted"] = "submitted"


class SubmissionFileOut(BaseModel):
    name: str
    kind: Literal["pdf", "dxf"]
    locale: str | None
    """Sprache eines PDFs; `null` bei DXF."""
    variant: str | None
    """`L93` oder `local` bei DXF."""
    size_bytes: int


class SummaryOptionOut(BaseModel):
    slug: str
    label_de: str
    label_fr: str
    included: bool


class SubmissionSummaryOut(BaseModel):
    """Zusammenfassung einer Fassung aus ihrem Snapshot, für die Liste im Büro."""

    type_name: str | None
    type_version: int | None
    type_retired: bool
    package_label_de: str | None
    package_label_fr: str | None
    options: list[SummaryOptionOut]
    costs_display: RangeOut | None
    """Kostenkorridor brutto, gerundet (L1: nur Spanne)."""
    vat_rate: float | None
    catalog_version: int | None
    deviations: list[CheckOut]
    site_origin: Literal["parcel", "manual_sketch"] | None


class StaffSubmissionOut(BaseModel):
    sequence: int
    status: Literal["current", "superseded"]
    created_at: datetime
    configuration_revision: int
    deviations_acknowledged: bool
    deviation_count: int
    open_points: int
    dossier_status: DossierStatus
    dossier_error: str | None
    files: list[SubmissionFileOut]
    summary: SubmissionSummaryOut
