"""AN7 Gescannte PDFs: Status `scan` am Dokument, Zustand der Texterkennung an der Datei, Sicherheit je
erkannter Seite (docs/PLAN_AN7_SCAN.md 4.1)

Revision ID: 0019
Revises: 0018
Created: 2026-09-29 10:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Neue Spalten mit Vorgabe bzw. nullable; die erweiterte
Prüfbedingung lässt alle bisherigen Werte zu. Das vorige Image kennt `scan` nicht und zeigt ein solches
Dokument als gescheitert (`_document_out`), schreibt aber nichts Falsches.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_land_use_plan_status_known"), "land_use_plan", type_="check")
    op.create_check_constraint(
        op.f("ck_land_use_plan_status_known"),
        "land_use_plan",
        "status IN ('importing','active','superseded','failed','scan')",
    )
    op.add_column(
        "source_file",
        sa.Column("ocr_state", sa.String(length=10), server_default=sa.text("'none'"), nullable=False),
    )
    op.add_column("source_file", sa.Column("ocr_error", sa.Text(), nullable=True))
    op.add_column("source_file", sa.Column("ocr_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_file", sa.Column("ocr_finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_source_file_ocr_state_known"),
        "source_file",
        "ocr_state IN ('none','offered','running','done','failed')",
    )
    op.add_column("source_page", sa.Column("ocr_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_page", "ocr_confidence")
    op.drop_constraint(op.f("ck_source_file_ocr_state_known"), "source_file", type_="check")
    op.drop_column("source_file", "ocr_finished_at")
    op.drop_column("source_file", "ocr_started_at")
    op.drop_column("source_file", "ocr_error")
    op.drop_column("source_file", "ocr_state")
    op.execute("UPDATE land_use_plan SET status = 'failed', error = 'document_no_text' WHERE status = 'scan'")
    op.drop_constraint(op.f("ck_land_use_plan_status_known"), "land_use_plan", type_="check")
    op.create_check_constraint(
        op.f("ck_land_use_plan_status_known"),
        "land_use_plan",
        "status IN ('importing','active','superseded','failed')",
    )
