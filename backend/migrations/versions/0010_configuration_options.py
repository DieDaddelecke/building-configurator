"""H3 Konfiguration und Kosten (docs/PLAN_H3_KONFIGURATION_KOSTEN.md 4.2)

Revision ID: 0010
Revises: 0009
Created: 2026-09-19 12:00:00.000000+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen),
damit das vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Alle neuen Spalten haben einen
Standardwert; der Trigger `forbid_published_modification` feuert nur bei UPDATE, nicht bei ADD COLUMN.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("configuration", sa.Column("package_version_id", sa.UUID(), nullable=True))
    op.add_column(
        "configuration",
        sa.Column(
            "modules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_configuration_package_version_id_package_version"),
        "configuration",
        "package_version",
        ["package_version_id"],
        ["id"],
    )
    op.add_column(
        "module_version",
        sa.Column("kind", sa.String(length=20), server_default=sa.text("'plain'"), nullable=False),
    )
    op.add_column(
        "module_version",
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "module_version",
        sa.Column(
            "regulatory",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_module_version_kind_known"), "module_version", "kind IN ('plain','terrace','carport')"
    )
    op.add_column(
        "package_version",
        sa.Column(
            "regulatory",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("package_version", "regulatory")
    op.drop_constraint(op.f("ck_module_version_kind_known"), "module_version", type_="check")
    op.drop_column("module_version", "regulatory")
    op.drop_column("module_version", "params")
    op.drop_column("module_version", "kind")
    op.drop_constraint(
        op.f("fk_configuration_package_version_id_package_version"), "configuration", type_="foreignkey"
    )
    op.drop_column("configuration", "modules")
    op.drop_column("configuration", "package_version_id")
