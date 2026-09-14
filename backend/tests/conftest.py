"""Testumgebung: eigene Datenbank je Testlauf mit denselben Rollen wie in Betrieb (app, migrator).

Benötigt TEST_ADMIN_DATABASE_URL (Superuser), z. B. über `docker compose run --rm backend-dev pytest`.
Tests ohne Datenbank laufen auch ohne diese Variable.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL")
TEST_DB = f"emprise_test_{uuid.uuid4().hex[:8]}"

if ADMIN_URL:
    _base = make_url(ADMIN_URL)
    os.environ["EMPRISE_DATABASE_URL"] = _base.set(
        username="app", password="app", database=TEST_DB
    ).render_as_string(hide_password=False)
    os.environ["EMPRISE_MIGRATION_DATABASE_URL"] = _base.set(
        username="migrator", password="migrator", database=TEST_DB
    ).render_as_string(hide_password=False)
os.environ["EMPRISE_ENV"] = "test"
os.environ.setdefault("EMPRISE_OIDC_ISSUER", "http://oidc.test/emprise")
os.environ.setdefault("EMPRISE_OIDC_CLIENT_ID", "emprise-test")

ROLES_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'migrator') THEN
        CREATE ROLE migrator LOGIN PASSWORD 'migrator';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
        CREATE ROLE app LOGIN PASSWORD 'app';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
        CREATE ROLE readonly LOGIN PASSWORD 'readonly';
    END IF;
END
$$
"""

CLEAN_TABLES = [
    "staff_session",
    "staff_user",
    "job",
    "project",
    "periodic_schedule",
    "feature_flag",
    "legal_text",
    "rate_limit_counter",
    "audit_log",
]


@pytest.fixture(scope="session")
def database() -> Iterator[str]:
    if not ADMIN_URL:
        pytest.skip("TEST_ADMIN_DATABASE_URL fehlt: Datenbanktests übersprungen")
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(ROLES_SQL))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}" OWNER migrator'))
    test_admin = create_engine(make_url(ADMIN_URL).set(database=TEST_DB), isolation_level="AUTOCOMMIT")
    with test_admin.connect() as conn:
        conn.execute(text("CREATE EXTENSION postgis"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO app, readonly"))
        conn.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app"
            )
        )
    test_admin.dispose()

    from alembic import command
    from alembic.config import Config

    from app.platform.health import BACKEND_DIR

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        yield TEST_DB
    finally:
        from app.platform.db import get_engine

        get_engine().dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def clean_db(database: str) -> Iterator[None]:
    yield
    assert ADMIN_URL
    engine = create_engine(make_url(ADMIN_URL).set(database=database))
    with engine.begin() as conn:
        # Superuser umgeht die Schutztrigger von audit_log und legal_text nur im Test
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        conn.execute(text(f"TRUNCATE {', '.join(CLEAN_TABLES)} RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture
def app(clean_db: None) -> Any:
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app: Any) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://testserver") as test_client:
        response = test_client.get("/api/v1/session")
        assert response.status_code == 200
        test_client.headers["X-CSRF-Token"] = test_client.cookies["emprise_csrf"]
        yield test_client


@pytest.fixture
def db_session(clean_db: None) -> Iterator[Any]:
    from app.platform.db import get_sessionmaker

    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def login_as(client: Any, db_session: Any) -> Callable[..., Any]:
    """Legt eine freigeschaltete Person mit Sitzung an und setzt das Sitzungscookie im Testclient."""
    from app.config import get_settings
    from app.platform.auth.staff import start_session
    from app.platform.auth.tokens import STAFF_COOKIE
    from app.platform.models import StaffUser

    def _login(*roles: str, email: str | None = None) -> Any:
        user = StaffUser(email=email or f"{uuid.uuid4().hex[:8]}@buero.test", roles=list(roles))
        db_session.add(user)
        db_session.flush()
        token = start_session(db_session, user, ["pwd", "mfa"], get_settings())
        db_session.commit()
        client.cookies.set(STAFF_COOKIE, token)
        return user

    return _login
