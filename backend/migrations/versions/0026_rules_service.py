"""Regeldienst: Umfang `collectif` und Service-Token (docs/PLAN_REGELDIENST.md 3.2, 4.1)

Revision ID: 0026
Revises: 0025
Created: 2026-11-25 17:00:00+00:00

Nur neue Spalten mit Standardwert `house` und neue Tabellen; das vorige Image läuft nach einem Rückrollen
weiter (Plan 6.5), solange es keinen Umfang `collectif` gibt. Die Eindeutigkeit der Regelwerke umfasst jetzt
den Umfang; ein Rückrollen der Migration löscht deshalb vorher die Regelwerke `collectif`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rule_set",
        sa.Column("scope", sa.String(length=20), server_default=sa.text("'house'"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_rule_set_scope_known"), "rule_set", "scope IN ('house','collectif')")
    op.drop_constraint("uq_rule_set_plan_zone", "rule_set", type_="unique")
    op.create_unique_constraint(
        "uq_rule_set_plan_zone_scope", "rule_set", ["land_use_plan_id", "zone_code", "scope"]
    )

    op.add_column(
        "rule_extraction_run",
        sa.Column("scope", sa.String(length=20), server_default=sa.text("'house'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_rule_extraction_run_scope_known"), "rule_extraction_run", "scope IN ('house','collectif')"
    )

    op.create_table(
        "regulation_chapter_scope",
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=20), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("scope IN ('collectif')", name=op.f("ck_regulation_chapter_scope_scope_known")),
        sa.CheckConstraint(
            "status IN ('pending','extracting','succeeded','failed')",
            name=op.f("ck_regulation_chapter_scope_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["regulation_chapter.id"],
            name=op.f("fk_regulation_chapter_scope_chapter_id_regulation_chapter"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chapter_id", "scope", name=op.f("pk_regulation_chapter_scope")),
    )

    op.create_table(
        "service_token",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "scopes <@ ARRAY['rules:read']::varchar[]", name=op.f("ck_service_token_scopes_known")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_token")),
        sa.UniqueConstraint("name", name=op.f("uq_service_token_name")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_service_token_token_hash")),
    )

    # Rechte wie in 0001, falls der Anbieter keine Default Privileges setzt (Plan 6.6)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON regulation_chapter_scope, service_token TO app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                GRANT SELECT ON regulation_chapter_scope TO readonly;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.drop_table("service_token")
    op.drop_table("regulation_chapter_scope")
    op.drop_constraint(op.f("ck_rule_extraction_run_scope_known"), "rule_extraction_run", type_="check")
    op.drop_column("rule_extraction_run", "scope")
    op.execute("DELETE FROM rule_set WHERE scope <> 'house'")
    op.drop_constraint("uq_rule_set_plan_zone_scope", "rule_set", type_="unique")
    op.create_unique_constraint("uq_rule_set_plan_zone", "rule_set", ["land_use_plan_id", "zone_code"])
    op.drop_constraint(op.f("ck_rule_set_scope_known"), "rule_set", type_="check")
    op.drop_column("rule_set", "scope")
