"""Emprise Analyse AN1: Parzelle hochladen, Projekte am Architektenkonto (docs/PLAN_AN1_PARZELLE.md)

Revision ID: 0012
Revises: 0011
Created: 2026-09-20 21:00:00+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen), damit das
vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Nur neue Spalten mit Standardwert und eine
erweiterte Prüfbedingung; bestehende Grundstücke behalten `origin` und gelten als georeferenziert,
soweit sie aus dem Kataster stammen.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_site_origin_known"), "site", type_="check")
    op.create_check_constraint(
        op.f("ck_site_origin_known"), "site", "origin IN ('parcel','manual_sketch','upload')"
    )
    op.add_column(
        "site",
        sa.Column("georeferenced", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "site",
        sa.Column(
            "source_info",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    # Frei gezeichnete Grundstücke haben keine echte Lage (G26); Kataster-Grundstücke behalten `true`
    op.execute("UPDATE site SET georeferenced = false WHERE origin = 'manual_sketch'")

    op.add_column(
        "project",
        sa.Column("owner_staff_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("project", sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_project_owner_staff_user_id_staff_user"),
        "project",
        "staff_user",
        ["owner_staff_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_project_owner_staff_user_id"),
        "project",
        ["owner_staff_user_id"],
        postgresql_where=sa.text("owner_staff_user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_owner_staff_user_id"), table_name="project")
    op.drop_constraint(op.f("fk_project_owner_staff_user_id_staff_user"), "project", type_="foreignkey")
    op.drop_column("project", "organisation_id")
    op.drop_column("project", "owner_staff_user_id")
    op.drop_column("site", "source_info")
    op.drop_column("site", "georeferenced")
    op.drop_constraint(op.f("ck_site_origin_known"), "site", type_="check")
    op.create_check_constraint(op.f("ck_site_origin_known"), "site", "origin IN ('parcel','manual_sketch')")
