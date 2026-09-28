"""G2 Vollständigkeit: offene und nicht einschlägige Textstellen an der Regelwerksversion
(docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.7)

Revision ID: 0017
Revises: 0016
Created: 2026-09-28 21:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Zwei Spalten mit leerer Liste als Vorgabe; das vorige Image
kennt sie nicht und schreibt Versionen ohne sie.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("open_passages", "out_of_scope_passages"):
        op.add_column(
            "rule_set_version",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for column in ("out_of_scope_passages", "open_passages"):
        op.drop_column("rule_set_version", column)
