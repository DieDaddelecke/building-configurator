"""Hausmodell HM3: Haustyp und Katalog mit Versionen, Prüfbefund der Kompatibilität (PLAN_HAUSMODELL 3.5)

Revision ID: 0024
Revises: 0023
Created: 2026-10-04 09:00:00+00:00

Nur neue Tabellen; das vorige Image läuft nach einem Rückrollen weiter (Plan 6.5). Veröffentlichte Versionen
sind unveränderlich (L4): `house_version_guard` lässt nur `published` → `retired` mit Zeitpunkt und Person
zu und verbietet das Löschen; `house_compatibility_guard` hält einen freigegebenen Befund fest.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "house_catalog",
    "house_catalog_version",
    "house_template",
    "house_template_version",
    "house_catalog_compatibility",
)
_VERSION_TABLES = ("house_catalog_version", "house_template_version")


def _identity() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
    ]


def _at_by(*steps: str) -> list[sa.Column]:  # type: ignore[type-arg]
    columns = []
    for step in steps:
        columns.append(sa.Column(f"{step}_at", sa.DateTime(timezone=True), nullable=True))
        columns.append(sa.Column(f"{step}_by", sa.String(length=200), nullable=True))
    return columns


def upgrade() -> None:
    op.create_table(
        "house_catalog",
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        *_identity(),
        sa.CheckConstraint("market IN ('FR')", name=op.f("ck_house_catalog_market_known")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_catalog")),
        sa.UniqueConstraint("market", name=op.f("uq_house_catalog_market")),
    )
    op.create_table(
        "house_catalog_version",
        sa.Column("catalog_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=False),
        *_at_by("published", "retired"),
        *_identity(),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name=op.f("ck_house_catalog_version_status_known")
        ),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["house_catalog.id"],
            name=op.f("fk_house_catalog_version_catalog_id_house_catalog"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_catalog_version")),
        sa.UniqueConstraint("catalog_id", "version", name="uq_house_catalog_version_catalog_version"),
    )
    op.create_index(
        op.f("ix_house_catalog_version_catalog_id"), "house_catalog_version", ["catalog_id"], unique=False
    )
    op.create_table(
        "house_template",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        *_identity(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_template")),
        sa.UniqueConstraint("slug", name=op.f("uq_house_template_slug")),
    )
    op.create_table(
        "house_template_version",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("ifc_file_name", sa.String(length=255), nullable=False),
        sa.Column("ifc_sha256", sa.String(length=64), nullable=False),
        sa.Column("ifc_key", sa.String(length=300), nullable=False),
        sa.Column("ifc_size_bytes", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_at_by("reviewed", "published", "rejected", "retired"),
        *_identity(),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'published', 'rejected', 'retired')",
            name=op.f("ck_house_template_version_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["house_template.id"],
            name=op.f("fk_house_template_version_template_id_house_template"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["house_catalog_version.id"],
            name="fk_house_template_version_catalog_version_id_house_cata_1779",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_template_version")),
        sa.UniqueConstraint("template_id", "version", name="uq_house_template_version_template_version"),
    )
    op.create_index(
        op.f("ix_house_template_version_template_id"), "house_template_version", ["template_id"], unique=False
    )
    op.create_table(
        "house_catalog_compatibility",
        sa.Column("template_version_id", sa.UUID(), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("domain_version", sa.String(length=40), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_at_by("approved"),
        *_identity(),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["house_template_version.id"],
            name="fk_house_catalog_compatibility_template_version_id_hous_d0ca",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["house_catalog_version.id"],
            name="fk_house_catalog_compatibility_catalog_version_id_house_2e27",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_catalog_compatibility")),
        sa.UniqueConstraint(
            "template_version_id", "catalog_version_id", name="uq_house_catalog_compatibility_pair"
        ),
    )
    op.create_index(
        op.f("ix_house_catalog_compatibility_template_version_id"),
        "house_catalog_compatibility",
        ["template_version_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION house_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status IN ('published', 'retired') THEN
                IF TG_OP = 'DELETE' OR NOT (
                    OLD.status = 'published' AND NEW.status = 'retired'
                    AND to_jsonb(NEW) - ARRAY['status', 'retired_at', 'retired_by']
                        = to_jsonb(OLD) - ARRAY['status', 'retired_at', 'retired_by']
                ) THEN
                    RAISE EXCEPTION 'published % is immutable (L4)', TG_TABLE_NAME
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION house_compatibility_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.approved_at IS NOT NULL THEN
                RAISE EXCEPTION 'approved % is immutable (L4)', TG_TABLE_NAME
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    for table in _VERSION_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_guard BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION house_version_guard()"
        )
    op.execute(
        "CREATE TRIGGER house_catalog_compatibility_guard BEFORE UPDATE OR DELETE "
        "ON house_catalog_compatibility FOR EACH ROW EXECUTE FUNCTION house_compatibility_guard()"
    )

    # Rechte wie in 0001, falls der Anbieter keine Default Privileges setzt (Plan 6.6)
    tables = ", ".join(_TABLES)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                GRANT SELECT ON {tables} TO readonly;
            END IF;
        END
        $$
        """  # noqa: S608  Tabellennamen fest
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS house_catalog_compatibility_guard ON house_catalog_compatibility")
    for table in _VERSION_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_guard ON {table}")
    op.execute("DROP FUNCTION IF EXISTS house_compatibility_guard()")
    op.execute("DROP FUNCTION IF EXISTS house_version_guard()")
    op.drop_index(
        op.f("ix_house_catalog_compatibility_template_version_id"), table_name="house_catalog_compatibility"
    )
    op.drop_table("house_catalog_compatibility")
    op.drop_index(op.f("ix_house_template_version_template_id"), table_name="house_template_version")
    op.drop_table("house_template_version")
    op.drop_table("house_template")
    op.drop_index(op.f("ix_house_catalog_version_catalog_id"), table_name="house_catalog_version")
    op.drop_table("house_catalog_version")
    op.drop_table("house_catalog")
