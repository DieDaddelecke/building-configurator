"""Emprise Analyse AN3: Zusatzdokumente und Annahmen der Analyse (docs/PLAN_AN3_ANALYSE.md)

Revision ID: 0014
Revises: 0013
Created: 2026-09-26 12:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Die Rolle `supplement` erweitert nur die erlaubten Werte; das
vorige Image liest Zusatzdokumente nicht (es sucht nur `role = 'plu'`). Eine neue Tabelle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_project_regulation_role_known"), "project_regulation", type_="check")
    op.create_check_constraint(
        op.f("ck_project_regulation_role_known"), "project_regulation", "role IN ('plu','supplement')"
    )

    op.create_table(
        "analysis_parameters",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_analysis_parameters_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_analysis_parameters")),
    )


def downgrade() -> None:
    op.drop_table("analysis_parameters")
    op.execute("DELETE FROM project_regulation WHERE role = 'supplement'")
    op.drop_constraint(op.f("ck_project_regulation_role_known"), "project_regulation", type_="check")
    op.create_check_constraint(
        op.f("ck_project_regulation_role_known"), "project_regulation", "role IN ('plu')"
    )
