"""AN6 Mandanten: Organisationen, Mitglieder, API-Schlüssel, Verbrauch; Projekte, Kapitel und Läufe mit
Organisation (docs/PLAN_AN6_MANDANTEN.md 4.1)

Revision ID: 0020
Revises: 0019
Created: 2026-09-29 18:00:00+00:00

Regel: abwärtskompatibel bleiben (Plan 6.5). Neue Tabellen und nullable Spalten; das vorige Image kennt sie
nicht und liest und schreibt ohne sie. Bestand: Gibt es Konten oder Projekte mit Eigentümer, entsteht die
Organisation „Eigenes Büro“ (Art `operator`); alle Konten werden ihre Mitglieder (`admin`), alle Projekte
mit Eigentümer ihre Projekte (3.1). So sieht das eigene Büro nach dem Einspielen dasselbe wie vorher.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organisation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("budget_month_usd", sa.Float(), nullable=True),
        sa.Column("ocr_pages_month", sa.Integer(), nullable=True),
        sa.Column(
            "address_lines",
            postgresql.ARRAY(sa.String(length=120)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("registration", sa.String(length=120), nullable=True),
        sa.Column("accent_color", sa.String(length=7), nullable=True),
        sa.Column("logo_key", sa.String(length=300), nullable=True),
        sa.Column("branding_revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('operator','customer')", name=op.f("ck_organisation_kind_known")),
        sa.CheckConstraint(
            "accent_color IS NULL OR accent_color ~ '^#[0-9a-f]{6}$'",
            name=op.f("ck_organisation_accent_color_hex"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organisation")),
        sa.UniqueConstraint("name", name=op.f("uq_organisation_name")),
    )
    op.create_index(
        "uq_organisation_operator",
        "organisation",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("kind = 'operator'"),
    )
    op.create_table(
        "organisation_member",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("staff_user_id", sa.UUID(), nullable=False),
        sa.Column("organisation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.CheckConstraint("role IN ('admin','member')", name=op.f("ck_organisation_member_role_known")),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisation.id"],
            name=op.f("fk_organisation_member_organisation_id_organisation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_user.id"],
            name=op.f("fk_organisation_member_staff_user_id_staff_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("staff_user_id", name=op.f("pk_organisation_member")),
    )
    op.create_index(
        op.f("ix_organisation_member_organisation_id"), "organisation_member", ["organisation_id"]
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

    op.create_foreign_key(
        op.f("fk_project_organisation_id_organisation"),
        "project",
        "organisation",
        ["organisation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_project_organisation_id",
        "project",
        ["organisation_id", "last_activity_at"],
        postgresql_where=sa.text("organisation_id IS NOT NULL"),
    )
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
    op.drop_constraint(op.f("ck_audit_log_actor_type_known"), "audit_log", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_log_actor_type_known"),
        "audit_log",
        "actor_type IN ('staff','customer','system','api_key')",
    )

    # Bestand dem eigenen Büro zuordnen (3.1)
    op.execute(
        """
        INSERT INTO organisation (id, name, display_name, kind, created_by)
        SELECT gen_random_uuid(), 'eigenes-buero', 'Eigenes Büro', 'operator', 'migration:0020'
        WHERE EXISTS (SELECT 1 FROM staff_user)
           OR EXISTS (SELECT 1 FROM project WHERE owner_staff_user_id IS NOT NULL)
        """
    )
    op.execute(
        """
        INSERT INTO organisation_member (staff_user_id, organisation_id, role, created_by)
        SELECT s.id, o.id, 'admin', 'migration:0020'
        FROM staff_user s CROSS JOIN organisation o
        WHERE o.kind = 'operator'
        """
    )
    op.execute(
        """
        UPDATE project SET organisation_id = (SELECT id FROM organisation WHERE kind = 'operator')
        WHERE owner_staff_user_id IS NOT NULL
        """
    )
    # Bisherige Auswertungen hat der Betreiber bezahlt – vor AN6 gab es keine andere Organisation. So zeigt
    # der Verbrauch des laufenden Monats auch die Läufe vor dem Update; eine Grenze hat `operator` nicht
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

    # Rechte wie in 0001, falls der Anbieter keine Default Privileges setzt (Plan 6.6)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
                GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    # Die erweiterte Bedingung von `audit_log` bleibt: Das Protokoll ist unveränderlich, Einträge mit
    # `api_key` dürfen nicht verschwinden
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
    op.drop_index("ix_project_organisation_id", table_name="project")
    op.drop_constraint(op.f("fk_project_organisation_id_organisation"), "project", type_="foreignkey")
    op.execute("UPDATE project SET organisation_id = NULL")
    op.drop_index("ix_usage_record_organisation", table_name="usage_record")
    op.drop_table("usage_record")
    op.drop_index(op.f("ix_api_key_organisation_id"), table_name="api_key")
    op.drop_table("api_key")
    op.drop_index(op.f("ix_organisation_member_organisation_id"), table_name="organisation_member")
    op.drop_table("organisation_member")
    op.drop_index("uq_organisation_operator", table_name="organisation")
    op.drop_table("organisation")
