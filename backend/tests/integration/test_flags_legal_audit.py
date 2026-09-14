from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.platform.models import AuditLog


def test_flag_rollout_by_role_then_project(client: Any, login_as: Any, app: Any) -> None:
    from fastapi.testclient import TestClient

    login_as("ops")
    project_id = client.post("/api/v1/projects").json()["id"]

    put = client.put("/api/v1/admin/flags/site_check", json={"description": "R1", "enabled_roles": ["ops"]})
    assert put.status_code == 200
    assert client.get("/api/v1/flags").json() == {"site_check": True}

    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/flags").json() == {}

    client.put("/api/v1/admin/flags/site_check", json={"enabled_project_ids": [project_id]})
    client.post("/api/v1/auth/staff/logout")
    # Ohne Rolle, aber mit dem freigeschalteten Projekt im Cookie
    assert client.get("/api/v1/flags").json() == {"site_check": True}


def test_flag_changes_are_audited(client: Any, login_as: Any, db_session: Any) -> None:
    login_as("ops")
    client.put("/api/v1/admin/flags/beta_x", json={"enabled_for_all": True})
    entry = db_session.execute(select(AuditLog).where(AuditLog.action == "feature_flag.put")).scalar_one()
    assert entry.entity_id == "beta_x"
    assert entry.before is None and entry.after["enabled_for_all"] is True


def test_invalid_flag_key(client: Any, login_as: Any) -> None:
    login_as("ops")
    assert client.put("/api/v1/admin/flags/Bad-Key", json={}).status_code == 422


def test_legal_texts_are_versioned_with_french_fallback(client: Any, login_as: Any) -> None:
    login_as("ops")
    for title in ("v1", "v2"):
        response = client.post(
            "/api/v1/admin/legal-texts",
            json={"key": "notice.cadastre", "locale": "fr", "title": title, "body": "Limites cadastrales…"},
        )
        assert response.status_code == 201
    client.post(
        "/api/v1/admin/legal-texts",
        json={"key": "notice.rules", "locale": "de", "title": "Regeln", "body": "Keine Bauauskunft."},
    )
    client.post(
        "/api/v1/admin/legal-texts",
        json={"key": "notice.rules", "locale": "fr", "title": "Règles", "body": "Pas un avis officiel."},
    )

    german = client.get("/api/v1/legal/notices", headers={"Accept-Language": "de"}).json()
    assert [(t["key"], t["locale"], t["version"]) for t in german] == [
        ("notice.cadastre", "fr", 2),  # keine deutsche Fassung: Französisch
        ("notice.rules", "de", 1),
    ]
    only = client.get("/api/v1/legal/notices?key=notice.rules").json()
    assert [(t["key"], t["locale"]) for t in only] == [("notice.rules", "fr")]


@pytest.mark.parametrize("table", ["audit_log", "legal_text"])
def test_append_only_tables_reject_update_and_delete(
    client: Any, login_as: Any, db_session: Any, table: str
) -> None:
    login_as("ops")
    client.post(
        "/api/v1/admin/legal-texts", json={"key": "notice.x", "locale": "fr", "title": "t", "body": "b"}
    )
    for statement in (
        f"UPDATE {table} SET created_by = 'x'"
        if table == "legal_text"
        else "UPDATE audit_log SET action = 'x'",
        f"DELETE FROM {table}",
    ):
        with pytest.raises(DBAPIError):
            db_session.execute(text(statement))
        db_session.rollback()


def test_cli_flag_set_for_role_with_audit(db_session: Any) -> None:
    """Freischaltung ohne Büro-Anmeldung, z. B. auf Unraid (Plan 4.2, BETRIEB.md 8)."""
    import argparse

    from app.cli import cmd_flag_set
    from app.platform.models import AuditLog, FeatureFlag

    cmd_flag_set(
        argparse.Namespace(key="site_selection", role=["architect"], all=False, off=False, description="G1")
    )
    db_session.expire_all()
    flag = db_session.get(FeatureFlag, "site_selection")
    assert (flag.enabled_for_all, flag.enabled_roles, flag.description) == (False, ["architect"], "G1")
    cmd_flag_set(argparse.Namespace(key="site_selection", role=None, all=False, off=True, description=None))
    db_session.expire_all()
    flag = db_session.get(FeatureFlag, "site_selection")
    assert (flag.enabled_for_all, flag.enabled_roles) == (False, [])
    actions = [a.action for a in db_session.query(AuditLog).filter(AuditLog.entity_id == "site_selection")]
    assert actions == ["feature_flag.put", "feature_flag.put"]
