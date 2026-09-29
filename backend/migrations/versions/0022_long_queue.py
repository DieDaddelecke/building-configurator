"""Lange Jobs in der Warteschlange `long` (REFACTORING_PLAN S5, Befund B-10)

Revision ID: 0022
Revises: 0021
Created: 2026-09-29 21:00:00+00:00

Ab diesem Image legt `enqueue` die Jobarten unten in `long` an. Wartende Jobs dieser Arten ziehen mit um;
laufende bleiben, wo sie sind, und enden dort. Abwärts ziehen wartende Jobs zurück nach `default`, damit das
vorige Image mit einem Worker für `default` sie findet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LONG_KINDS = ("rules_extract", "rules_document_read", "rules_document_ocr", "plu_import", "cadastre_import")


def _move(source: str, target: str) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE job SET queue = :target WHERE status = 'queued' AND queue = :source AND kind IN :kinds"
        ).bindparams(sa.bindparam("kinds", expanding=True)),
        {"target": target, "source": source, "kinds": list(LONG_KINDS)},
    )


def upgrade() -> None:
    _move("default", "long")


def downgrade() -> None:
    _move("long", "default")
