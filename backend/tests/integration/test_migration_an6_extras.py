"""Migration 0023: AN6-Zusätze zurückbauen (REFACTORING_PLAN S8).

Abwärts entstehen Tabellen und Spalten leer wieder, aufwärts verschwinden sie; Organisation, Mitglieder und
alte Protokolleinträge mit `api_key` bleiben.
"""

import uuid
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from tests.integration import test_migration_one_database as one_database

scratch = one_database.scratch
REMOVED = {"budget_month_usd", "ocr_pages_month", "accent_color", "logo_key", "branding_revision"}


def _columns(conn: Any, table: str) -> set[str]:
    return {column["name"] for column in inspect(conn).get_columns(table)}


def test_an6_extras_go_and_come_back_empty(scratch: tuple[Config, Any]) -> None:
    config, engine = scratch
    command.upgrade(config, "0022")
    org = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organisation (id, name, display_name, kind, accent_color, branding_revision) "
                "VALUES (:id, 'eigenes-buero', 'Eigenes Büro', 'operator', '#1d4ed8', 3)"
            ),
            {"id": org},
        )
        conn.execute(
            text(
                "INSERT INTO api_key (id, organisation_id, name, prefix, token_hash, scopes, expires_at) "
                "VALUES (:id, :org, 'CAD', 'abcd1234', '\\x00', ARRAY['read'], now())"
            ),
            {"id": uuid.uuid4(), "org": org},
        )
        conn.execute(
            text(
                "INSERT INTO audit_log (actor_type, actor_id, action, entity_type) "
                "VALUES ('api_key', 'api_key:1', 'project.update', 'project')"
            )
        )

    command.upgrade(config, "head")
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        assert not {"api_key", "usage_record"} & tables
        assert not REMOVED & _columns(conn, "organisation")
        assert "billing_organisation_id" not in _columns(conn, "regulation_chapter")
        assert "organisation_id" not in _columns(conn, "rule_extraction_run")
        assert conn.execute(text("SELECT display_name FROM organisation")).scalar_one() == "Eigenes Büro"
        assert conn.execute(text("SELECT actor_type FROM audit_log")).scalar_one() == "api_key"

    command.downgrade(config, "0022")
    with engine.begin() as conn:
        assert {"api_key", "usage_record"} <= set(inspect(conn).get_table_names())
        assert _columns(conn, "organisation") >= REMOVED
        assert conn.execute(text("SELECT count(*) FROM api_key")).scalar_one() == 0
        assert conn.execute(text("SELECT branding_revision FROM organisation")).scalar_one() == 0
