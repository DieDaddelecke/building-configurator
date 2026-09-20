"""V Vorentwurf-Übergabe (docs/PLAN_V_VORENTWURF_UEBERGABE.md 4.1)

Revision ID: 0011
Revises: 0010
Created: 2026-09-19 18:00:00.000000+00:00

Regel: abwärtskompatibel bleiben (erst erweitern, später in eigenem Release aufräumen),
damit das vorige Image nach einem Rückrollen weiterläuft (Plan 6.5). Neue Tabellen, Spalten mit
Standardwert, erweiterte Prüfungen; die Eindeutigkeit der Einwilligungen aus A wird zum Teilindex. Der
Trigger `consent_append_only` feuert nur bei UPDATE/DELETE, nicht bei ADD COLUMN.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_STATUSES = "status IN ('neu','in_bearbeitung','beantwortet','geschlossen')"
NEW_STATUSES = "status IN ('neu','in_bearbeitung','rueckfrage','beantwortet','geschlossen','zurueckgezogen')"
OLD_KINDS = "kind IN ('simulation_confirmation','transmission_office')"
NEW_KINDS = (
    "kind IN ('simulation_confirmation','transmission_office','design_confirmation','transmission_design')"
)


def upgrade() -> None:
    op.create_table(
        "submission",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("inquiry_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'current'"), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_schema_version", sa.Integer(), server_default=sa.text("2"), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("review_stamp", sa.String(length=200), nullable=False),
        sa.Column("deviations_acknowledged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deviation_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("open_points", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "dossier_status", sa.String(length=10), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "dossier_files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("dossier_error", sa.Text(), nullable=True),
        sa.Column("supersedes_id", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint("status IN ('current','superseded')", name=op.f("ck_submission_status_known")),
        sa.CheckConstraint(
            "dossier_status IN ('pending','ready','failed')", name=op.f("ck_submission_dossier_status_known")
        ),
        sa.ForeignKeyConstraint(
            ["inquiry_id"], ["inquiry.id"], name=op.f("fk_submission_inquiry_id_inquiry"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_submission_project_id_project"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["submission.id"], name=op.f("fk_submission_supersedes_id_submission")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission")),
        sa.UniqueConstraint("inquiry_id", "sequence", name="uq_submission_inquiry_sequence"),
    )
    op.create_index(op.f("ix_submission_project_id"), "submission", ["project_id"], unique=False)
    op.create_index(
        "uq_submission_current",
        "submission",
        ["inquiry_id"],
        unique=True,
        postgresql_where=sa.text("status = 'current'"),
    )

    op.create_table(
        "inquiry_message",
        sa.Column("inquiry_id", sa.UUID(), nullable=False),
        sa.Column("author", sa.String(length=10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint("author IN ('customer','office')", name=op.f("ck_inquiry_message_author_known")),
        sa.ForeignKeyConstraint(
            ["inquiry_id"],
            ["inquiry.id"],
            name=op.f("fk_inquiry_message_inquiry_id_inquiry"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiry_message")),
    )
    op.create_index(op.f("ix_inquiry_message_inquiry_id"), "inquiry_message", ["inquiry_id"], unique=False)

    # Einwilligungen je Fassung (V 3.5); die Eindeutigkeit aus A gilt nur noch ohne Fassung
    op.add_column("consent", sa.Column("submission_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_consent_submission_id_submission"),
        "consent",
        "submission",
        ["submission_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_consent_submission_id"), "consent", ["submission_id"], unique=False)
    op.drop_constraint("uq_consent_project_kind", "consent", type_="unique")
    op.create_index(
        "uq_consent_project_kind",
        "consent",
        ["project_id", "kind"],
        unique=True,
        postgresql_where=sa.text("submission_id IS NULL"),
    )
    op.create_index(
        "uq_consent_submission_kind",
        "consent",
        ["submission_id", "kind"],
        unique=True,
        postgresql_where=sa.text("submission_id IS NOT NULL"),
    )
    op.drop_constraint(op.f("ck_consent_kind_known"), "consent", type_="check")
    op.create_check_constraint(op.f("ck_consent_kind_known"), "consent", NEW_KINDS)

    op.drop_constraint(op.f("ck_inquiry_status_known"), "inquiry", type_="check")
    op.create_check_constraint(op.f("ck_inquiry_status_known"), "inquiry", NEW_STATUSES)

    op.add_column(
        "customer",
        sa.Column("locale", sa.String(length=5), server_default=sa.text("'fr'"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_customer_locale_known"), "customer", "locale IN ('fr','de')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_customer_locale_known"), "customer", type_="check")
    op.drop_column("customer", "locale")
    op.drop_constraint(op.f("ck_inquiry_status_known"), "inquiry", type_="check")
    op.create_check_constraint(op.f("ck_inquiry_status_known"), "inquiry", OLD_STATUSES)
    op.drop_constraint(op.f("ck_consent_kind_known"), "consent", type_="check")
    op.create_check_constraint(op.f("ck_consent_kind_known"), "consent", OLD_KINDS)
    op.drop_index("uq_consent_submission_kind", table_name="consent")
    op.drop_index("uq_consent_project_kind", table_name="consent")
    op.create_unique_constraint("uq_consent_project_kind", "consent", ["project_id", "kind"])
    op.drop_index(op.f("ix_consent_submission_id"), table_name="consent")
    op.drop_constraint(op.f("fk_consent_submission_id_submission"), "consent", type_="foreignkey")
    op.drop_column("consent", "submission_id")
    op.drop_index(op.f("ix_inquiry_message_inquiry_id"), table_name="inquiry_message")
    op.drop_table("inquiry_message")
    op.drop_index("uq_submission_current", table_name="submission")
    op.drop_index(op.f("ix_submission_project_id"), table_name="submission")
    op.drop_table("submission")
