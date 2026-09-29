"""Migration 0021: Tabellen der früheren gemeinsamen Datenbank in der Hauptkette (REFACTORING_PLAN S4).

Läuft in einer eigenen Datenbank, damit Ab- und Aufwärts die Testdatenbank der übrigen Tests nicht berühren.
Abwärts entsteht der Stand s0001 in derselben Datenbank (vorige Instanz ohne eigene gemeinsame Datenbank);
aufwärts muss er ohne Verlust in `app_setting`, `audit_log` und die Referenzlisten zurückfinden.
"""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.platform.health import BACKEND_DIR
from tests.conftest import ADMIN_URL, create_database


@pytest.fixture
def scratch() -> Iterator[tuple[Config, Any]]:
    if not ADMIN_URL:
        pytest.skip("TEST_ADMIN_DATABASE_URL fehlt: Datenbanktests übersprungen")
    name = f"emprise_mig_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    create_database(admin, name)
    url = make_url(ADMIN_URL)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url.set(
        username="migrator", password="migrator", database=name
    ).render_as_string(hide_password=False)
    engine = create_engine(url.set(database=name))
    try:
        yield config, engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _tables(conn: Any) -> set[str]:
    rows = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    return {row[0] for row in rows}


def test_shared_tables_move_into_the_main_chain_and_back(scratch: tuple[Config, Any]) -> None:
    config, engine = scratch
    command.upgrade(config, "head")
    chosen = {"model": "anthropic/claude-sonnet-5", "price_input_per_mtok": 2.0}
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app_setting (key, value, updated_by, updated_by_name) "
                "VALUES ('rules_model', CAST(:value AS jsonb), 'staff-1', 'Anna')"
            ),
            {"value": json.dumps(chosen)},
        )
        conn.execute(
            text(
                "INSERT INTO reference_list (id, document_sha256, document_title, sector) "
                "VALUES (:id, :sha, 'PLU Test', 'Uh')"
            ),
            {"id": uuid.uuid4(), "sha": "a" * 64},
        )

    # Abwärts: Stand s0001 in derselben Datenbank, die Wahl liegt wieder in `shared_setting`
    command.downgrade(config, "0020")
    with engine.begin() as conn:
        assert {"shared_setting", "shared_audit", "alembic_version_shared", "reference_list"} <= _tables(conn)
        assert conn.execute(text("SELECT version_num FROM alembic_version_shared")).scalar_one() == "s0001"
        assert conn.execute(text("SELECT count(*) FROM app_setting")).scalar_one() == 0
        row = conn.execute(text("SELECT value, updated_by_name FROM shared_setting")).one()
        assert (row.value, row.updated_by_name) == (chosen, "Anna")
        # Eine ältere Wahl der Instanz (PU11) verliert gegen die gemeinsame, wie beim früheren Migrate-Job
        conn.execute(
            text("INSERT INTO app_setting (key, value) VALUES ('rules_model', CAST(:value AS jsonb))"),
            {"value": json.dumps({"model": "x/y"})},
        )
        for minutes, actor_id, action in (
            (2, "analyse:system:reference-import", "reference_list_imported"),
            (1, "configurator:1f0e6a4c-0000-4000-8000-000000000001", "rules_model_changed"),
        ):
            conn.execute(
                text(
                    "INSERT INTO shared_audit (id, created_at, product, actor_id, actor_name, action, "
                    "entity_type, entity_id, after) VALUES (:id, now() - make_interval(mins => :minutes), "
                    "'analyse', :actor, 'Anna', :action, 'reference_list', 'l1', CAST('{\"n\": 1}' AS jsonb))"
                ),
                {"id": uuid.uuid4(), "minutes": minutes, "actor": actor_id, "action": action},
            )

    command.upgrade(config, "head")
    with engine.begin() as conn:
        tables = _tables(conn)
        assert not {"shared_setting", "shared_audit", "alembic_version_shared"} & tables
        row = conn.execute(text("SELECT value, updated_by, updated_by_name FROM app_setting")).one()
        assert (row.value, row.updated_by, row.updated_by_name) == (chosen, "staff-1", "Anna")
        audit = conn.execute(
            text("SELECT actor_type, actor_id, action, after FROM audit_log ORDER BY id")
        ).all()
        assert [(a.actor_type, a.action) for a in audit] == [
            ("system", "reference_list_imported"),
            ("staff", "rules_model_changed"),
        ]
        assert audit[0].actor_id == "analyse:system:reference-import" and audit[0].after == {"n": 1}
        assert conn.execute(text("SELECT document_title FROM reference_list")).scalar_one() == "PLU Test"
