"""Emprise Analyse: Einstellungen einer Instanz, zuerst das KI-Modell der Auswertung (PLAN_AN2_PLU 8)

Revision ID: 0016
Revises: 0015
Created: 2026-09-28 18:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Eine neue, leere Tabelle; das vorige Image kennt sie nicht und
rechnet weiter mit dem Modell aus der Umgebung.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_setting")),
    )


def downgrade() -> None:
    op.drop_table("app_setting")
