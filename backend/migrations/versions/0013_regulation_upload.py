"""Emprise Analyse AN2: règlement écrit hochladen (docs/PLAN_AN2_PLU.md)

Revision ID: 0013
Revises: 0012
Created: 2026-09-25 12:00:00+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen), damit das
vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Neue Spalten mit Standardwert, eine neue
Tabelle; `gpu_doc_id` wird nur für hochgeladene Dokumente leer, die das vorige Image nie liest (es
erreicht Planstände nur über `rules_commune`).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "land_use_plan",
        sa.Column("origin", sa.String(length=10), server_default=sa.text("'gpu'"), nullable=False),
    )
    op.add_column("land_use_plan", sa.Column("document_sha256", sa.String(length=64), nullable=True))
    op.alter_column("land_use_plan", "gpu_doc_id", existing_type=sa.String(length=64), nullable=True)
    op.create_unique_constraint(
        op.f("uq_land_use_plan_document_sha256"), "land_use_plan", ["document_sha256"]
    )
    op.create_check_constraint(
        op.f("ck_land_use_plan_origin_known"),
        "land_use_plan",
        "(origin = 'gpu' AND gpu_doc_id IS NOT NULL) OR (origin = 'upload' AND document_sha256 IS NOT NULL)",
    )

    op.add_column(
        "regulation_chapter",
        sa.Column(
            "suggested_sectors",
            postgresql.ARRAY(sa.String(length=20)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )

    op.create_table(
        "project_regulation",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("land_use_plan_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'plu'"), nullable=False),
        sa.Column("zone_code", sa.String(length=20), nullable=True),
        sa.Column("chapter_code", sa.String(length=20), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint("role IN ('plu')", name=op.f("ck_project_regulation_role_known")),
        sa.ForeignKeyConstraint(
            ["land_use_plan_id"],
            ["land_use_plan.id"],
            name=op.f("fk_project_regulation_land_use_plan_id_land_use_plan"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_project_regulation_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_regulation")),
        sa.UniqueConstraint("project_id", "land_use_plan_id", name="uq_project_regulation_project_document"),
    )
    op.create_index(
        "uq_project_regulation_plu",
        "project_regulation",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("role = 'plu'"),
    )
    op.create_index(
        op.f("ix_project_regulation_land_use_plan_id"),
        "project_regulation",
        ["land_use_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_regulation_land_use_plan_id"), table_name="project_regulation")
    op.drop_index("uq_project_regulation_plu", table_name="project_regulation")
    op.drop_table("project_regulation")
    op.drop_column("regulation_chapter", "suggested_sectors")
    op.execute("DELETE FROM land_use_plan WHERE origin = 'upload'")
    op.drop_constraint(op.f("ck_land_use_plan_origin_known"), "land_use_plan", type_="check")
    op.drop_constraint(op.f("uq_land_use_plan_document_sha256"), "land_use_plan", type_="unique")
    op.alter_column("land_use_plan", "gpu_doc_id", existing_type=sa.String(length=64), nullable=False)
    op.drop_column("land_use_plan", "document_sha256")
    op.drop_column("land_use_plan", "origin")
