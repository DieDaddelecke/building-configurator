"""AN6-Zusätze zurückbauen: API-Schlüssel, Budget und Scan-Kontingent je Organisation, Erscheinungsbild
(REFACTORING_PLAN S8, Entscheidung des Nutzers vom 29.09.2026)

Revision ID: 0023
Revises: 0022
Created: 2026-09-30 08:00:00+00:00

Bleiben: Organisation (Name, Anzeigename, Art, aktiv), Mitglieder, Projekte der Organisation und das
Monatsbudget der Instanz. Entfallen: Tabellen `api_key` und `usage_record`, Grenzen und Schriftfeld an
`organisation`, die zahlende Organisation an Kapitel und Lauf. Kapitel, die an der Grenze ihrer Organisation
stehen geblieben sind, gelten danach als an der Grenze der Instanz gescheitert; `rules_housekeeping` nimmt
sie auf, sobald dort Budget frei ist. Die Bedingung von `audit_log.actor_type` behält `api_key`: Das Protokoll
ist unveränderlich. Logos bleiben als Dateien unter `organisations/` liegen.

Abwärts entstehen Spalten und Tabellen leer wieder; Kapitel und Läufe werden wie in 0020 dem eigenen Büro
zugeordnet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BRANDING = ("address_lines", "phone", "email", "website", "registration", "accent_color", "logo_key")


def upgrade() -> None:
    op.execute(
        "UPDATE regulation_chapter SET error = 'budget_exceeded' WHERE error = 'organisation_budget_exceeded'"
    )

    op.drop_index("ix_rule_extraction_run_organisation", table_name="rule_extraction_run")
    op.drop_constraint(
        op.f("fk_rule_extraction_run_organisation_id_organisation"), "rule_extraction_run", type_="foreignkey"
    )
    op.drop_column("rule_extraction_run", "organisation_id")
    op.drop_constraint(
        op.f("fk_regulation_chapter_billing_organisation_id_organisation"),
        "regulation_chapter",
        type_="foreignkey",
    )
    op.drop_column("regulation_chapter", "billing_organisation_id")

    op.drop_index("ix_usage_record_organisation", table_name="usage_record")
    op.drop_table("usage_record")
    op.drop_index(op.f("ix_api_key_organisation_id"), table_name="api_key")
    op.drop_table("api_key")

    op.drop_constraint(op.f("ck_organisation_accent_color_hex"), "organisation", type_="check")
    for column in ("budget_month_usd", "ocr_pages_month", *BRANDING, "branding_revision"):
        op.drop_column("organisation", column)


def downgrade() -> None:
    op.add_column("organisation", sa.Column("budget_month_usd", sa.Float(), nullable=True))
    op.add_column("organisation", sa.Column("ocr_pages_month", sa.Integer(), nullable=True))
    op.add_column(
        "organisation",
        sa.Column(
            "address_lines",
            postgresql.ARRAY(sa.String(length=120)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column("organisation", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("organisation", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column("organisation", sa.Column("website", sa.String(length=200), nullable=True))
    op.add_column("organisation", sa.Column("registration", sa.String(length=120), nullable=True))
    op.add_column("organisation", sa.Column("accent_color", sa.String(length=7), nullable=True))
    op.add_column("organisation", sa.Column("logo_key", sa.String(length=300), nullable=True))
    op.add_column(
        "organisation",
        sa.Column("branding_revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_organisation_accent_color_hex"),
        "organisation",
        "accent_color IS NULL OR accent_color ~ '^#[0-9a-f]{6}$'",
    )

    op.create_table(
        "api_key",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("organisation_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("prefix", sa.String(length=12), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String(length=10)), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scopes <@ ARRAY['read','write']::varchar[] AND cardinality(scopes) > 0",
            name=op.f("ck_api_key_scopes_known"),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisation.id"],
            name=op.f("fk_api_key_organisation_id_organisation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_key")),
        sa.UniqueConstraint("prefix", name=op.f("uq_api_key_prefix")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_key_token_hash")),
    )
    op.create_index(op.f("ix_api_key_organisation_id"), "api_key", ["organisation_id"])
    op.create_table(
        "usage_record",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("organisation_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.CheckConstraint("kind IN ('ocr_pages')", name=op.f("ck_usage_record_kind_known")),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisation.id"],
            name=op.f("fk_usage_record_organisation_id_organisation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_record")),
    )
    op.create_index("ix_usage_record_organisation", "usage_record", ["organisation_id", "kind", "created_at"])

    op.add_column("regulation_chapter", sa.Column("billing_organisation_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_regulation_chapter_billing_organisation_id_organisation"),
        "regulation_chapter",
        "organisation",
        ["billing_organisation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("rule_extraction_run", sa.Column("organisation_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_rule_extraction_run_organisation_id_organisation"),
        "rule_extraction_run",
        "organisation",
        ["organisation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_rule_extraction_run_organisation",
        "rule_extraction_run",
        ["organisation_id", "created_at"],
        postgresql_where=sa.text("organisation_id IS NOT NULL"),
    )
    # Wie 0020: Ohne andere Organisation hat der Betreiber bezahlt
    for table, column in (
        ("rule_extraction_run", "organisation_id"),
        ("regulation_chapter", "billing_organisation_id"),
    ):
        op.execute(
            f"""
            UPDATE {table} SET {column} = (SELECT id FROM organisation WHERE kind = 'operator')
            WHERE {column} IS NULL
            """  # noqa: S608  Tabellen- und Spaltennamen fest
        )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON api_key, usage_record TO app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                GRANT SELECT ON api_key, usage_record TO readonly;
            END IF;
        END
        $$
        """
    )
