"""Grundstück: Weg E – freies Zeichnen ohne Kataster (Plan 3.3)

Revision ID: 0006
Revises: 0005
Created: 2026-09-17 09:00:00+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen),
damit das vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Nur neue Spalten mit Standardwert;
bestehende Grundstücke sind alle `origin = 'parcel'`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site", sa.Column("origin", sa.String(length=20), server_default=sa.text("'parcel'"), nullable=False)
    )
    op.add_column("site", sa.Column("address_label", sa.String(length=200), nullable=True))
    op.create_check_constraint(op.f("ck_site_origin_known"), "site", "origin IN ('parcel','manual_sketch')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_site_origin_known"), "site", type_="check")
    op.drop_column("site", "address_label")
    op.drop_column("site", "origin")
