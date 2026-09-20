"""Tabelle des Moduls V (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.1, 4.1).

Eine Fassung des Vorentwurfs je Übergabe. Der Vorgang (`inquiry`, Modul A) trägt Nummer und Status der
Bearbeitung; jede Fassung ihren eigenen, unveränderlichen Snapshot und ihr Dossier. Genau eine Fassung je
Vorgang ist `current` (Teilindex), die früheren sind `superseded`. Kein Endpunkt schreibt nach der Anlage auf
`snapshot`; nur `status` und die Felder des Dossiers ändern sich.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base, Created, UuidPk


class Submission(UuidPk, Created, Base):
    __tablename__ = "submission"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inquiry.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    """Laufende Nummer der Fassung im Vorgang, ab 1."""
    status: Mapped[str] = mapped_column(String(12), server_default=text("'current'"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_schema_version: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    configuration_revision: Mapped[int] = mapped_column(Integer)
    review_stamp: Mapped[str] = mapped_column(String(200))
    deviations_acknowledged: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    deviation_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    open_points: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    dossier_status: Mapped[str] = mapped_column(String(10), server_default=text("'pending'"))
    dossier_files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    """`[{name, kind, content_type, size_bytes, sha256, storage_key}]`, gesetzt vom Job `dossier_generate`."""
    dossier_error: Mapped[str | None] = mapped_column(Text)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("submission.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("inquiry_id", "sequence", name="uq_submission_inquiry_sequence"),
        Index(
            "uq_submission_current",
            "inquiry_id",
            unique=True,
            postgresql_where=text("status = 'current'"),
        ),
        CheckConstraint("status IN ('current','superseded')", name="status_known"),
        CheckConstraint("dossier_status IN ('pending','ready','failed')", name="dossier_status_known"),
    )
