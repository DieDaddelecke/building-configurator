"""Regelwerk: Rückfall auf den vorigen Planstand, Neubewertung ohne Modellaufruf, Aufrufe in Teilen

Revision ID: 0004
Revises: 0003
Created: 2026-09-14 20:00:00+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen),
damit das vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Nur neue Spalten mit Standardwert.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rules_commune", sa.Column("fallback_land_use_plan_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_rules_commune_fallback_land_use_plan_id_land_use_plan"),
        "rules_commune",
        "land_use_plan",
        ["fallback_land_use_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Neuer Status `multiple_regulations`; das vorige Image schreibt ihn nie und liest den Status als Text
    op.drop_constraint(op.f("ck_rules_commune_status_known"), "rules_commune", type_="check")
    op.create_check_constraint(
        op.f("ck_rules_commune_status_known"),
        "rules_commune",
        "status IN ('ok','rnu','no_document','no_regulation','multiple_regulations','no_chapters','failed')",
    )
    op.add_column("regulation_chapter", sa.Column("engine_version", sa.String(length=20), nullable=True))
    op.add_column(
        "rule_extraction_run",
        sa.Column("part", sa.String(length=200), server_default=sa.text("''"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("rule_extraction_run", "part")
    op.drop_column("regulation_chapter", "engine_version")
    op.execute("UPDATE rules_commune SET status = 'no_regulation' WHERE status = 'multiple_regulations'")
    op.drop_constraint(op.f("ck_rules_commune_status_known"), "rules_commune", type_="check")
    op.create_check_constraint(
        op.f("ck_rules_commune_status_known"),
        "rules_commune",
        "status IN ('ok','rnu','no_document','no_regulation','no_chapters','failed')",
    )
    op.drop_constraint(
        op.f("fk_rules_commune_fallback_land_use_plan_id_land_use_plan"), "rules_commune", type_="foreignkey"
    )
    op.drop_column("rules_commune", "fallback_land_use_plan_id")
