"""HTTP-Verhalten der Plattform: Gesundheit, Fehlerformat, CSRF, Projekte, Rate-Limit, Migrationen."""

from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import get_settings
from app.platform.health import BACKEND_DIR, expected_migration_head


def test_health_ready_reports_postgis_and_migration(client: Any) -> None:
    response = client.get("/api/health/ready")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["postgis"]
    assert body["migration"] == expected_migration_head()
    assert body["migration_state"] == "current"


def test_readiness_tolerates_newer_database_after_rollback() -> None:
    """Nach dem Rückrollen kennt das alte Image die neueste Revision nicht; es bleibt bereit."""
    from app.platform.health import migration_state

    assert migration_state(expected_migration_head()) == "current"
    assert migration_state("9999_from_newer_release") == "ahead"
    assert migration_state(None) == "pending"


def test_models_match_migrations(database: str) -> None:
    """`alembic check` schlägt fehl, wenn Modelle und Migrationen auseinanderlaufen."""
    command.check(Config(str(BACKEND_DIR / "alembic.ini")))


def test_problem_details_are_localized(client: Any) -> None:
    response = client.get("/api/v1/does-not-exist", headers={"Accept-Language": "de-DE"})
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "not_found"
    assert body["title"] == "Nicht gefunden"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_validation_error_has_stable_code(client: Any, login_as: Any) -> None:
    login_as("ops")
    response = client.post("/api/v1/admin/legal-texts", json={"key": "X"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_write_without_csrf_token_is_rejected(app: Any) -> None:
    with TestClient(app) as fresh:
        response = fresh.post("/api/v1/projects")
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"
        fresh.get("/api/v1/session")
        wrong = fresh.post("/api/v1/projects", headers={"X-CSRF-Token": "falsch"})
        assert wrong.status_code == 403


def test_project_cookie_grants_access_only_to_own_project(client: Any, app: Any) -> None:
    created = client.post("/api/v1/projects")
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 200
    assert client.get("/api/v1/session").json()["project_id"] == project_id

    with TestClient(app) as stranger:
        response = stranger.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 404


def test_project_creation_is_rate_limited(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "project_create_limit_per_hour", 2)
    assert client.post("/api/v1/projects").status_code == 201
    assert client.post("/api/v1/projects").status_code == 201
    limited = client.post("/api/v1/projects")
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1


def test_security_headers(client: Any) -> None:
    response = client.get("/api/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
