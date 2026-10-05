"""Hausmodell HM4: Konfiguration des Hausmodells je Projekt (PLAN_HAUSMODELL 3.5, 3.9)

Revision ID: 0025
Revises: 0024
Created: 2026-10-04 08:07:08+00:00

Nur eine neue Tabelle; das vorige Image läuft nach einem Rückrollen weiter (Plan 6.5). Template- und
Katalogversion sind festgehalten (E-HM-7); veröffentlichte Versionen lassen sich nicht löschen (Trigger aus
0024), die Fremdschlüssel bleiben also gültig. Mit dem Projekt verschwindet auch seine Konfiguration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "house_configuration",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("template_version_id", sa.UUID(), nullable=True),
        sa.Column("catalog_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("""'{"selections": {}}'::jsonb"""),
            nullable=False,
        ),
        sa.Column("placement", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column(
            "boundary_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("snapshot", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column("engine_version", sa.String(length=40), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "(template_version_id IS NULL) = (catalog_version_id IS NULL)",
            name=op.f("ck_house_configuration_versions_together"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["house_catalog_version.id"],
            name=op.f("fk_house_configuration_catalog_version_id_house_catalog_version"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_house_configuration_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["house_template_version.id"],
            name="fk_house_configuration_template_version_id_house_templa_df38",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_configuration")),
        sa.UniqueConstraint("project_id", name=op.f("uq_house_configuration_project_id")),
    )

    # Rechte wie in 0001, falls der Anbieter keine Default Privileges setzt (Plan 6.6)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON house_configuration TO app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                GRANT SELECT ON house_configuration TO readonly;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.drop_table("house_configuration")
