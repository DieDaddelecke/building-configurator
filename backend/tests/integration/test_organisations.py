"""Mandanten (AN6, docs/PLAN_AN6_MANDANTEN.md 6) gegen PostGIS.

Zwei Organisationen: das eigene Büro (`operator`) und ein fremdes Büro (`customer`, im Test freigeschaltet).
Geprüft werden die Trennung über **alle** Routen mit Projekt, die wirksamen Rollen und die Verwaltung der
Mitglieder. API-Schlüssel, Budget und Scan-Kontingent je Organisation und das Erscheinungsbild sind seit dem
29.09.2026 zurückgebaut (REFACTORING_PLAN S8).
"""

import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.platform import organisations
from app.platform.models import AuditLog, Organisation, Project, StaffUser
from tests.integration import test_analysis as an3
from tests.integration.test_rules_upload import new_project, sessions, uploaded
from tests.integration.test_site_upload import LOCAL_RING, dxf_bytes

memory_storage = an3.memory_storage
flags = an3.flags
app = an3.app


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("EMPRISE_OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("EMPRISE_EXTERNAL_ORGANISATIONS", "true")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def foreign(db_session: Any, settings: Any) -> Organisation:
    org = organisations.create_organisation(
        db_session, settings, name="atelier-sud", display_name="Atelier Sud", kind="customer", actor="test"
    )
    db_session.commit()
    return org


def site_project(client: Any) -> str:
    """Projekt der angemeldeten Organisation mit einer Parzelle aus einer DXF-Datei."""
    project = new_project(client)
    response = client.post(
        f"/api/v1/projects/{project}/site/upload",
        files={"file": ("plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")), "application/octet-stream")},
        data={"address_label": "Parzelle aus Datei"},
    )
    assert response.status_code == 200, response.json()
    return project


PARAM_VALUES = {"seq": "1", "sequence": "1", "name": "datei.pdf", "slug": "x", "version": "1"}


def _url(path: str, project_id: str) -> str:
    def value(match: re.Match[str]) -> str:
        name = match.group(1).split(":")[0]
        if name == "project_id":
            return project_id
        return PARAM_VALUES.get(name, str(uuid.uuid4()))

    return re.sub(r"\{([^}]+)\}", value, path)


def project_routes(application: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for ctx in iter_route_contexts(application.routes):
        if isinstance(ctx.original_route, APIRoute) and "{project_id}" in str(ctx.path):
            found += [(method, str(ctx.path)) for method in sorted(ctx.methods or ()) if method != "HEAD"]
    return found


# ---------------------------------------------------------------------------
# Trennung (3.2)
# ---------------------------------------------------------------------------


def test_foreign_organisation_sees_nothing_on_any_project_route(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation, settings: Any
) -> None:
    """Jede Route mit Projekt antwortet einer fremden Organisation `404` (oder `403` vor der Prüfung), für
    Projekte einer anderen Organisation wie für Kundenprojekte ohne Organisation (Abnahme 2,
    7.1 Nr. 1, 15)."""
    login_as("architect", "rules_admin", "ops")
    own = site_project(client)
    state = uploaded(client, own)
    file_url = state["document"]["file_url"]
    assert client.get(file_url).status_code == 200
    customer = str(uuid.uuid4())
    with sessions() as session:
        session.add(Project(id=uuid.UUID(customer), access_token_hash=uuid.uuid4().bytes))
        session.commit()

    login_as("architect", organisation=foreign)
    routes = project_routes(client.app)
    assert len(routes) > 40
    leaks: list[str] = []
    for project in (own, customer):
        for method, path in routes:
            response = client.request(method, _url(path, project), json={})
            if response.status_code not in (403, 404):
                leaks.append(
                    f"{method} {path} ({'Büro' if project == own else 'Kunde'}): {response.status_code}"
                )
    assert not leaks, leaks

    # Dateien, Liste und Verwaltung ohne Projekt
    assert client.get(file_url).status_code == 404
    assert client.get("/api/v1/projects").json() == []
    assert client.get("/api/v1/admin/rules/coverage").status_code == 403
    assert client.get("/api/v1/admin/rules/model").status_code == 403
    assert client.get("/api/v1/admin/reference-lists").status_code == 403
    assert client.get("/api/v1/admin/rule-kinds").status_code == 200
    assert client.get(f"/api/v1/admin/rule-sets/{uuid.uuid4()}").status_code == 403

    # Das eigene Projekt der fremden Organisation geht, das des Büros sieht sie nicht
    theirs = site_project(client)
    assert [p["id"] for p in client.get("/api/v1/projects").json()] == [theirs]
    login_as("architect")
    assert theirs not in [p["id"] for p in client.get("/api/v1/projects").json()]
    assert client.get(f"/api/v1/projects/{theirs}/site").status_code == 404
    assert client.get(f"/api/v1/admin/projects/{theirs}/rules").status_code == 404


def test_operator_roles_work_only_in_the_operator_organisation(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation, db_session: Any
) -> None:
    """Eine gespeicherte Betriebsrolle wirkt in einer fremden Organisation nicht; ohne Organisation keine
    Rolle (3.2, 7.1 Nr. 11)."""
    login_as("architect", "ops", organisation=foreign)
    session = client.get("/api/v1/session").json()
    assert session["staff"]["roles"] == ["architect"]
    assert session["staff"]["organisation"] == {
        "id": str(foreign.id),
        "display_name": "Atelier Sud",
        "kind": "customer",
        "role": "admin",
    }
    assert client.get("/api/v1/admin/flags").status_code == 403

    login_as("architect", "ops", organisation=False)
    assert client.get("/api/v1/session").json()["staff"]["roles"] == []
    assert client.get("/api/v1/projects").status_code == 403

    # Beim Zuordnen: Rollen des Betriebs passen nicht in ein fremdes Büro
    user = StaffUser(email="betrieb@buero.test", roles=["architect", "ops"])
    db_session.add(user)
    db_session.flush()
    with pytest.raises(organisations.OrganisationError, match="operator_roles_outside_operator"):
        organisations.set_membership(db_session, foreign, user, "member", "test")


def test_external_organisations_need_the_switch(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fremde Büros erst nach der juristischen Prüfung (E-A5, E-AN6-8)."""
    monkeypatch.delenv("EMPRISE_EXTERNAL_ORGANISATIONS", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(organisations.OrganisationError, match="external_organisations_disabled"):
            organisations.create_organisation(
                db_session, get_settings(), name="fremd", display_name="Fremd", kind="customer", actor="cli"
            )
    finally:
        get_settings.cache_clear()


def test_anonymous_project_does_not_open_the_analysis(client: Any) -> None:
    """Seit Konfigurator und Analyse eine Anwendung sind, entsteht ohne Anmeldung ein Kundenprojekt mit
    Cookie; Analyse und Reglement-Upload verlangen weiter einen Architekten der Organisation (REFACTORING_PLAN
    S1)."""
    response = client.post("/api/v1/projects")
    assert response.status_code == 201
    assert "emprise_project" in response.cookies
    project = response.json()["id"]
    assert client.get(f"/api/v1/projects/{project}/analysis").status_code == 404
    upload = client.post(
        f"/api/v1/projects/{project}/regulations",
        files={"file": ("plu.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert upload.status_code == 404


def test_former_api_keys_open_nothing(client: Any, flags: None) -> None:
    """Ein früherer Schlüssel (`Bearer emp_…`) ist nur noch ein fremder Kopf: kein Zugang, keine Ausnahme von
    der CSRF-Prüfung (REFACTORING_PLAN S8)."""
    api = TestClient(client.app, base_url="http://testserver", headers={"Authorization": "Bearer emp_x_y"})
    assert api.get("/api/v1/projects").json()["code"] == "authentication_required"
    assert api.post("/api/v1/projects").json()["code"] == "csrf_failed"


def test_members_manage_nothing_and_admins_keep_one_admin(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation
) -> None:
    admin = login_as("architect", organisation=foreign)
    added = client.post("/api/v1/organisation/members", json={"email": "Neu@Atelier-Sud.fr"})
    assert added.status_code == 201
    emails = {m["email"]: m for m in added.json()}
    assert emails["neu@atelier-sud.fr"]["role"] == "member" and not emails["neu@atelier-sud.fr"]["signed_in"]
    assert client.patch(f"/api/v1/organisation/members/{admin.id}", json={"role": "member"}).json()[
        "code"
    ] == ("last_admin")
    assert client.delete(f"/api/v1/organisation/members/{admin.id}").json()["code"] == "cannot_remove_self"
    login_as("architect")
    taken = client.post("/api/v1/organisation/members", json={"email": "neu@atelier-sud.fr"})
    assert taken.json()["code"] == "member_of_other_organisation"

    login_as("architect", organisation=foreign, org_role="member")
    assert client.get("/api/v1/organisation/members").status_code == 403
    assert client.patch("/api/v1/organisation", json={"display_name": "Atelier Nord"}).status_code == 403
    assert client.get("/api/v1/organisation").json() == {
        "id": str(foreign.id),
        "name": "atelier-sud",
        "display_name": "Atelier Sud",
        "kind": "customer",
    }


def test_admin_renames_the_organisation(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation, db_session: Any
) -> None:
    login_as("architect", organisation=foreign)
    renamed = client.patch("/api/v1/organisation", json={"display_name": " Atelier Sud Architectes "})
    assert renamed.status_code == 200 and renamed.json()["display_name"] == "Atelier Sud Architectes"
    assert client.get("/api/v1/session").json()["staff"]["organisation"]["display_name"] == (
        "Atelier Sud Architectes"
    )
    db_session.expire_all()
    changed = db_session.execute(
        select(AuditLog.before, AuditLog.after).where(AuditLog.action == "organisation.update")
    ).one()
    assert tuple(changed) == ({"display_name": "Atelier Sud"}, {"display_name": "Atelier Sud Architectes"})
