"""Schemas des Moduls A (Plan 3.6, docs/PLAN_A_ANFRAGE.md)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

Lotissement = Literal["yes", "no", "unknown"]
InquiryStatus = Literal["neu", "in_bearbeitung", "beantwortet", "geschlossen"]


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


class MyInquiryOut(BaseModel):
    exists: bool
    number: str | None = None
    status: InquiryStatus | None = None


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


class ExportOut(BaseModel):
    project_id: uuid.UUID
    project_created_at: datetime
    customer: CustomerOut | None
    consents: list[ConsentOut]
    inquiry_number: str | None
    inquiry_status: InquiryStatus | None
    snapshot: dict[str, Any] | None


class InquiryListItem(BaseModel):
    project_id: uuid.UUID
    number: str
    status: InquiryStatus
    customer_name: str
    customer_email: str
    lotissement: Lotissement
    has_envelope: bool
    customer_corrections: int
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


class InquiryPatchIn(BaseModel):
    status: InquiryStatus
