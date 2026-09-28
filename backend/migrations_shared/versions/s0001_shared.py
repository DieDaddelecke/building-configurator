"""Gemeinsame Datenbank: Einstellungen, Audit, Referenzlisten (PLAN_G2_VOLLSTAENDIGKEIT 3.9–3.10)

Revision ID: s0001
Revises:
Created: 2026-09-28 22:00:00+00:00

Regel: nur erweitern. Beide Produkte fahren diese Migrationen; ein älteres Image muss ein neueres Schema
vertragen (PLAN_G2_VOLLSTAENDIGKEIT 3.9).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shared_setting",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("updated_by_name", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_shared_setting")),
    )
    op.create_table(
        "shared_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("product", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("actor_name", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_audit")),
    )
    op.create_table(
        "reference_list",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_title", sa.String(length=300), nullable=False),
        sa.Column("sector", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="draft", nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("updated_by_name", sa.String(length=200), nullable=True),
        sa.CheckConstraint("status IN ('draft','checked')", name=op.f("ck_reference_list_status_known")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_list")),
        sa.UniqueConstraint("document_sha256", "sector", name="uq_reference_list_document_sector"),
    )
    op.create_table(
        "reference_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("list_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("building_kind", sa.String(length=10), nullable=False),
        sa.Column("expected", sa.String(length=20), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "expected IN ('effective','not_regulated','text_only','graphic_reference','not_expressible')",
            name=op.f("ck_reference_entry_expected_known"),
        ),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["reference_list.id"],
            name=op.f("fk_reference_entry_list_id_reference_list"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_entry")),
    )
    op.create_index(op.f("ix_reference_entry_list_id"), "reference_entry", ["list_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reference_entry_list_id"), table_name="reference_entry")
    op.drop_table("reference_entry")
    op.drop_table("reference_list")
    op.drop_table("shared_audit")
    op.drop_table("shared_setting")
