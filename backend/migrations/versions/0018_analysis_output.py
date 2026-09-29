"""AN5 Ausgabe und Projektakte: Name, Notiz und Archiv am Projekt, Bericht der Analyse
(docs/PLAN_AN5_AUSGABE.md 3.1, 3.6)

Revision ID: 0018
Revises: 0017
Created: 2026-09-28 23:30:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Drei nullable Spalten und eine neue Tabelle; das vorige Image
kennt sie nicht und liest und schreibt Projekte ohne sie.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project", sa.Column("name", sa.String(length=120), nullable=True))
    op.add_column("project", sa.Column("note", sa.String(length=2000), nullable=True))
    op.add_column("project", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "analysis_report",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("engine_version", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_analysis_report_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_report")),
        sa.UniqueConstraint(
            "project_id", "input_hash", "locale", name="uq_analysis_report_project_hash_locale"
        ),
    )
    op.create_index(op.f("ix_analysis_report_project_id"), "analysis_report", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_report_project_id"), table_name="analysis_report")
    op.drop_table("analysis_report")
    op.drop_column("project", "archived_at")
    op.drop_column("project", "note")
    op.drop_column("project", "name")
