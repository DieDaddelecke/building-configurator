"""Emprise Analyse AN4: Fundstelle an der Projektkorrektur (docs/PLAN_AN4_KORREKTUR.md 3.2)

Revision ID: 0015
Revises: 0014
Created: 2026-09-28 12:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Nur neue, leere Spalten; das vorige Image liest und schreibt
Korrekturen weiter ohne Fundstelle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_rule_override", sa.Column("source_file_id", sa.UUID(), nullable=True))
    op.add_column("project_rule_override", sa.Column("page", sa.Integer(), nullable=True))
    op.add_column("project_rule_override", sa.Column("quote", sa.Text(), nullable=True))
    op.add_column(
        "project_rule_override",
        sa.Column("quote_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_project_rule_override_source_file_id_source_file"),
        "project_rule_override",
        "source_file",
        ["source_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_project_rule_override_page_valid"), "project_rule_override", "page IS NULL OR page >= 1"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_project_rule_override_page_valid"), "project_rule_override", type_="check")
    op.drop_constraint(
        op.f("fk_project_rule_override_source_file_id_source_file"),
        "project_rule_override",
        type_="foreignkey",
    )
    op.drop_column("project_rule_override", "quote_verified")
    op.drop_column("project_rule_override", "quote")
    op.drop_column("project_rule_override", "page")
    op.drop_column("project_rule_override", "source_file_id")
