"""Referenzlisten in der gemeinsamen Datenbank (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10, VA03).

Eine Liste gehört zu einem Dokument (Prüfsumme der Planunterlage) und einem Sektor, nicht zu einem Büro oder
einer Instanz: Beide Produkte messen ihre Auswertungen desselben Dokuments daran.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.shared import SharedBase

EXPECTED = "('effective','not_regulated','text_only','graphic_reference','not_expressible')"


class ReferenceList(SharedBase):
    __tablename__ = "reference_list"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_sha256: Mapped[str] = mapped_column(String(64))
    document_title: Mapped[str] = mapped_column(String(300))
    sector: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), server_default="draft")
    note: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))
    updated_by_name: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("document_sha256", "sector", name="uq_reference_list_document_sector"),
        CheckConstraint("status IN ('draft','checked')", name="status_known"),
    )


class ReferenceEntry(SharedBase):
    __tablename__ = "reference_entry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_list.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    building_kind: Mapped[str] = mapped_column(String(10))
    expected: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    page: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (CheckConstraint(f"expected IN {EXPECTED}", name="expected_known"),)
