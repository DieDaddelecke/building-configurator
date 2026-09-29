"""Eine Datenbank: Referenzlisten, Modellwahl und ihr Audit aus der früheren gemeinsamen Datenbank
(REFACTORING_PLAN S4)

Revision ID: 0021
Revises: 0020
Created: 2026-09-29 20:00:00+00:00

Konfigurator und Analyse sind eine Anwendung mit einer Datenbank. Die Tabellen der früheren Kette
`migrations_shared` (Stand s0001) gehören jetzt zur Hauptkette:

- `reference_list` und `reference_entry` entstehen, falls sie fehlen. Lagen sie schon in dieser Datenbank
  (Instanz ohne eigene gemeinsame Datenbank), bleiben sie mit ihren Zeilen.
- `shared_setting` geht in `app_setting` auf (neue Spalte `updated_by_name`); die gemeinsame Wahl hat Vorrang
  vor einer der Instanz, wie bisher beim Migrate-Job (VA09).
- `shared_audit` geht in `audit_log` auf. Die Kennungen behalten das Präfix des früheren Produkts; der
  Anzeigename entfällt, weil das Audit-Log keine personenbezogenen Daten hält.
- `alembic_version_shared` entfällt.

Zeilen aus einer eigenen gemeinsamen Datenbank (`EMPRISE_SHARED_DATABASE_URL`) übernimmt die Migration nicht;
die Schritte stehen in docs/BETRIEB.md 15.

Abwärts: `shared_setting`, `shared_audit` und `alembic_version_shared` (s0001) entstehen wieder in dieser
Datenbank, die Modellwahl zieht zurück. So läuft das vorige Image ohne eigene gemeinsame Datenbank. Die
übernommenen Audit-Zeilen bleiben in `audit_log`, das nur anfügt.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_reference_tables() -> None:
    op.create_table(
        "reference_list",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_title", sa.String(length=300), nullable=False),
        sa.Column("sector", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="draft", nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("updated_by_name", sa.String(length=200), nullable=True),
        sa.CheckConstraint("status IN ('draft','checked')", name=op.f("ck_reference_list_status_known")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_list")),
        sa.UniqueConstraint("document_sha256", "sector", name="uq_reference_list_document_sector"),
    )
    op.create_table(
        "reference_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("list_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("building_kind", sa.String(length=10), nullable=False),
        sa.Column("expected", sa.String(length=20), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "expected IN ('effective','not_regulated','text_only','graphic_reference','not_expressible')",
            name=op.f("ck_reference_entry_expected_known"),
        ),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["reference_list.id"],
            name=op.f("fk_reference_entry_list_id_reference_list"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_entry")),
    )
    op.create_index(op.f("ix_reference_entry_list_id"), "reference_entry", ["list_id"], unique=False)


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    op.add_column("app_setting", sa.Column("updated_by_name", sa.String(length=200), nullable=True))
    if "reference_list" not in tables:
        _create_reference_tables()
    if "shared_setting" in tables:
        op.execute(
            """
            INSERT INTO app_setting (key, value, updated_at, updated_by, updated_by_name)
            SELECT key, value, updated_at, updated_by, updated_by_name FROM shared_setting
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by, updated_by_name = EXCLUDED.updated_by_name
            """
        )
        op.drop_table("shared_setting")
    if "shared_audit" in tables:
        op.execute(
            """
            INSERT INTO audit_log (occurred_at, actor_type, actor_id, action, entity_type, entity_id, before, after)
            SELECT created_at,
                CASE WHEN actor_id LIKE '%:system:%' THEN 'system'
                     WHEN actor_id LIKE '%:api_key:%' THEN 'api_key'
                     ELSE 'staff' END,
                left(actor_id, 100), action, entity_type, entity_id, before, after
            FROM shared_audit ORDER BY created_at, id
            """
        )
        op.drop_table("shared_audit")
    op.execute("DROP TABLE IF EXISTS alembic_version_shared")


def downgrade() -> None:
    op.create_table(
        "shared_setting",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.Column("updated_by_name", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_shared_setting")),
    )
    op.execute(
        """
        INSERT INTO shared_setting (key, value, updated_at, updated_by, updated_by_name)
        SELECT key, value, updated_at, updated_by, updated_by_name FROM app_setting
        """
    )
    op.execute("DELETE FROM app_setting")
    op.drop_column("app_setting", "updated_by_name")
    op.create_table(
        "shared_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("product", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("actor_name", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_audit")),
    )
    op.create_table(
        "alembic_version_shared",
        sa.Column("version_num", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name="alembic_version_shared_pkc"),
    )
    op.execute("INSERT INTO alembic_version_shared (version_num) VALUES ('s0001')")
