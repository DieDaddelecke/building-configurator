"""H2 Zulässigkeit und Implantation (docs/PLAN_H2_ZULAESSIGKEIT_IMPLANTATION.md 4.2)

Revision ID: 0009
Revises: 0008
Created: 2026-09-19 08:00:00.000000+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen),
damit das vorige Image nach einem Rückrollen weiterläuft (Plan 6.5).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configuration",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("building_type_version_id", sa.UUID(), nullable=True),
        sa.Column("placement", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "boundary_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["building_type_version_id"],
            ["building_type_version.id"],
            name=op.f("fk_configuration_building_type_version_id_building_type_version"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_configuration_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration")),
        sa.UniqueConstraint("project_id", name=op.f("uq_configuration_project_id")),
    )


def downgrade() -> None:
    op.drop_table("configuration")
