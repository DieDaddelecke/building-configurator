"""Baurahmen: Steckbrief je Projekt und Eingabestand

Revision ID: 0005
Revises: 0004
Created: 2026-09-16 09:00:00+00:00

Regel: abwaertskompatibel bleiben (erst erweitern, spaeter aufraeumen), damit das vorige Image nach einem
Rueckrollen weiterlaeuft (Plan 6.5). Hier nur eine neue Tabelle; der Baurahmen selbst wird gerechnet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "envelope_sheet",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("engine_version", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_envelope_sheet_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_envelope_sheet")),
        sa.UniqueConstraint("project_id", "input_hash", name="uq_envelope_sheet_project_hash"),
    )
    op.create_index(op.f("ix_envelope_sheet_project_id"), "envelope_sheet", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_envelope_sheet_project_id"), table_name="envelope_sheet")
    op.drop_table("envelope_sheet")
