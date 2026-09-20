"""Schemas des Moduls A (Plan 3.6, docs/PLAN_A_ANFRAGE.md), erweitert um Fassungen, Nachrichten
und Zugangslink (V, docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.3)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.submission.schemas import StaffSubmissionOut, SubmissionFileOut

Lotissement = Literal["yes", "no", "unknown"]
InquiryStatus = Literal["neu", "in_bearbeitung", "rueckfrage", "beantwortet", "geschlossen", "zurueckgezogen"]
OfficeStatus = Literal["neu", "in_bearbeitung", "rueckfrage", "beantwortet", "geschlossen"]
"""Was das Büro setzen darf; `zurueckgezogen` setzt nur der Kunde (V 3.8)."""


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    desired_start: str | None = Field(default=None, max_length=60)
    financing_clarified: bool | None = None
    lotissement: Lotissement = "unknown"


class ContactOut(BaseModel):
    status: Literal["code_sent"] = "code_sent"
    code_expires_in_minutes: int


class ConfirmIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    simulation_confirmation: bool
    transmission_office: bool


class ConfirmOut(BaseModel):
    number: str
    status: Literal["submitted"] = "submitted"


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: uuid.UUID
    author: Literal["customer", "office"]
    body: str
    created_at: datetime


class MySubmissionOut(BaseModel):
    """Fassung aus Sicht des Kunden: ohne Prüfdetails des Büros, mit den PDFs (V 3.7)."""

    sequence: int
    status: Literal["current", "superseded"]
    created_at: datetime
    deviation_count: int
    dossier_status: Literal["pending", "ready", "failed"]
    files: list[SubmissionFileOut]


class MyInquiryOut(BaseModel):
    exists: bool
    number: str | None = None
    status: InquiryStatus | None = None
    submissions: list[MySubmissionOut]
    messages: list[MessageOut]
    can_withdraw: bool


class ConsentOut(BaseModel):
    kind: str
    legal_text_key: str
    legal_text_version: int
    confirmed_at: datetime


class CustomerOut(BaseModel):
    name: str
    email: str
    phone: str | None
    desired_start: str | None
    financing_clarified: bool | None
    lotissement: Lotissement


class ExportSubmissionOut(BaseModel):
    sequence: int
    status: str
    created_at: datetime
    snapshot: dict[str, Any]
    files: list[str]


class ExportOut(BaseModel):
    project_id: uuid.UUID
    project_created_at: datetime
    customer: CustomerOut | None
    consents: list[ConsentOut]
    inquiry_number: str | None
    inquiry_status: InquiryStatus | None
    snapshot: dict[str, Any] | None
    submissions: list[ExportSubmissionOut]
    messages: list[MessageOut]


class InquiryListItem(BaseModel):
    project_id: uuid.UUID
    number: str
    status: InquiryStatus
    customer_name: str
    customer_email: str
    lotissement: Lotissement
    has_envelope: bool
    customer_corrections: int
    submissions: int
    """Zahl der Fassungen aus dem Konfigurator (V)."""
    deviation_count: int | None
    """Abweichungen der aktuellen Fassung; `null` ohne Fassung."""
    dossier_status: Literal["pending", "ready", "failed"] | None
    created_at: datetime
    updated_at: datetime


class InquiryDetailOut(BaseModel):
    project_id: uuid.UUID
    number: str
    status: InquiryStatus
    customer: CustomerOut
    consents: list[ConsentOut]
    snapshot: dict[str, Any]
    snapshot_schema_version: int
    created_at: datetime
    updated_at: datetime
    submissions: list[StaffSubmissionOut]
    """Fassungen, jüngste zuerst."""
    messages: list[MessageOut]
    configuration_revision: int | None
    """Aktuelle Revision der Konfiguration; höher als die der Fassung heißt „seit der Übergabe geändert“."""


class InquiryPatchIn(BaseModel):
    status: OfficeStatus


class AccessRedeemIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class AccessRedeemOut(BaseModel):
    project_id: uuid.UUID


class AccessRequestIn(BaseModel):
    email: EmailStr


class AccessRequestOut(BaseModel):
    status: Literal["accepted"] = "accepted"
    """Immer gleich, ob die Adresse bekannt ist oder nicht (V 3.9)."""
