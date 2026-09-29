"""Mandanten (AN6, docs/PLAN_AN6_MANDANTEN.md 6) gegen PostGIS.

Zwei Organisationen: das eigene Büro (`operator`) und ein fremdes Büro (`customer`, im Test freigeschaltet).
Geprüft werden die Trennung über **alle** Routen mit Projekt, die wirksamen Rollen, API-Schlüssel, Budget
und Scan-Kontingent sowie das Erscheinungsbild in Bericht und DXF. Die App läuft als Produkt
„Emprise Analyse“.
"""

import io
import re
import uuid
from collections.abc import Callable
from typing import Any

import ezdxf
import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.analysis import report, service
from app.config import get_settings
from app.platform import organisations
from app.platform.db import utcnow
from app.platform.models import AuditLog, Job, Organisation, Project, StaffUser, UsageRecord
from app.rules import extract
from app.rules.models import RegulationChapter, RuleExtractionRun
from app.rules.service import _restart_reason
from tests.integration import test_analysis as an3
from tests.integration.test_rules_upload import (
    choose,
    new_project,
    read_document,
    request_ocr,
    sessions,
    upload_chapter,
    upload_regulation,
    uploaded,
)
from tests.integration.test_site_upload import LOCAL_RING, dxf_bytes
from tests.rules_support import FakeExtractor, regulation_fixture, uh_output
from tests.scan_support import with_scanned_pages

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


def png(size: tuple[int, int] = (120, 60), color: str = "#1d4ed8") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return out.getvalue()


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


def test_analyse_has_no_anonymous_projects(client: Any) -> None:
    response = client.post("/api/v1/projects")
    assert response.status_code == 401
    assert "emprise_project" not in response.cookies


# ---------------------------------------------------------------------------
# API-Schlüssel (3.6)
# ---------------------------------------------------------------------------


def key_client(application: Any, token: str) -> TestClient:
    return TestClient(application, base_url="http://testserver", headers={"Authorization": f"Bearer {token}"})


def new_key(client: Any, scopes: list[str]) -> dict[str, Any]:
    response = client.post("/api/v1/organisation/api-keys", json={"name": "CAD-Anbindung", "scopes": scopes})
    assert response.status_code == 201, response.json()
    body: dict[str, Any] = response.json()
    return body


def test_api_key_works_like_an_architect_of_its_organisation(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation, db_session: Any
) -> None:
    login_as("architect")
    office = new_project(client)
    login_as("architect", organisation=foreign)
    created = new_key(client, ["read", "write"])
    assert created["token"].startswith(f"emp_{created['prefix']}_")
    assert created["scopes"] == ["read", "write"]
    listed = client.get("/api/v1/organisation/api-keys").json()
    assert [k["id"] for k in listed] == [created["id"]] and "token" not in listed[0]

    api = key_client(client.app, created["token"])
    made = api.post("/api/v1/projects")
    assert made.status_code == 201 and "emprise_project" not in made.cookies
    project = made.json()["id"]
    upload = api.post(
        f"/api/v1/projects/{project}/site/upload",
        files={"file": ("plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")), "application/octet-stream")},
        data={"address_label": "Über die API"},
    )
    assert upload.status_code == 200, upload.json()
    assert [p["id"] for p in api.get("/api/v1/projects").json()] == [project]
    assert api.get(f"/api/v1/projects/{project}/analysis").status_code in (200, 409)
    assert api.get(f"/api/v1/projects/{office}").status_code == 404
    # Nur Projektendpunkte, keine Verwaltung und keine Sitzung
    assert api.get("/api/v1/session").json()["code"] == "api_key_not_allowed"
    assert api.get("/api/v1/flags").json()["code"] == "api_key_not_allowed"
    assert api.get("/api/v1/organisation").status_code == 403
    assert api.get("/api/v1/admin/rule-kinds").status_code == 403
    # Das Projekt gehört der Organisation und bleibt für ihre Architekten sichtbar
    assert project in [p["id"] for p in client.get("/api/v1/projects").json()]
    db_session.expire_all()
    stored = db_session.get(Project, uuid.UUID(project))
    assert stored.organisation_id == foreign.id and stored.owner_staff_user_id is None
    assert stored.created_by == f"api_key:{created['id']}"
    assert api.patch(f"/api/v1/projects/{project}", json={"name": "Über die API"}).status_code == 200
    db_session.expire_all()
    audited = db_session.execute(
        select(AuditLog.actor_type, AuditLog.actor_id).where(
            AuditLog.action == "project.update", AuditLog.entity_id == project
        )
    ).one()
    assert tuple(audited) == ("api_key", f"api_key:{created['id']}")

    # Mit Cookie abgelehnt statt ohne CSRF-Prüfung durchgelassen
    api.cookies.set("emprise_csrf", "x")
    assert api.post("/api/v1/projects").json()["code"] == "api_key_with_cookies"
    api.cookies.clear()

    reader = key_client(client.app, new_key(client, ["read"])["token"])
    assert reader.get(f"/api/v1/projects/{project}/site").status_code == 200
    assert reader.post("/api/v1/projects").json()["code"] == "api_key_read_only"

    assert client.delete(f"/api/v1/organisation/api-keys/{created['id']}").status_code == 204
    assert api.get("/api/v1/projects").json()["code"] == "api_key_invalid"
    assert key_client(client.app, "emp_00000000_falsch").get("/api/v1/projects").status_code == 401


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
    assert (
        client.post("/api/v1/organisation/api-keys", json={"name": "x1", "scopes": ["read"]}).status_code
        == 403
    )
    usage = client.get("/api/v1/organisation/usage").json()
    assert usage["budget_month_usd"] == 20.0 and usage["ocr_pages_month"] == 2000
    assert len(usage["months"]) == 6


# ---------------------------------------------------------------------------
# Budget und Scan-Kontingent (3.4)
# ---------------------------------------------------------------------------


def set_limits(org: Organisation, budget: float | None = None, pages: int | None = None) -> None:
    with sessions() as session:
        stored = session.get(Organisation, org.id)
        assert stored is not None
        stored.budget_month_usd, stored.ocr_pages_month = budget, pages
        session.commit()


def test_organisation_budget_stops_before_and_during_an_evaluation(
    client: Any,
    flags: None,
    login_as: Callable[..., Any],
    foreign: Organisation,
    db_session: Any,
    settings: Any,
) -> None:
    login_as("architect", organisation=foreign)
    project = site_project(client)
    document = uploaded(client, project)["document"]["id"]

    set_limits(foreign, budget=0.0)
    refused = choose(client, project, document, zone_code="Uh", chapter_code="Uh")
    assert refused.status_code == 409 and refused.json()["code"] == "organisation_budget_exceeded"
    db_session.expire_all()
    assert (
        db_session.execute(
            select(func.count()).select_from(Job).where(Job.kind == "rules_extract")
        ).scalar_one()
        == 0
    )

    set_limits(foreign, budget=10.0)
    assert choose(client, project, document, zone_code="Uh", chapter_code="Uh").status_code == 200
    chapter_id = upload_chapter(db_session)
    outcome = extract.extract_chapter(sessions, settings, chapter_id, FakeExtractor([uh_output()]).factory())
    assert outcome.status == "succeeded"
    db_session.expire_all()
    payers = set(db_session.execute(select(RuleExtractionRun.organisation_id)).scalars())
    assert payers == {foreign.id}
    spent = client.get("/api/v1/organisation/usage").json()["months"][0]["cost_usd"]
    assert spent > 0

    # Während der Auswertung hält die Grenze der Organisation den nächsten Aufruf an, nicht die der Instanz
    set_limits(foreign, budget=spent / 2)
    stopped = extract.extract_chapter(
        sessions, settings, chapter_id, FakeExtractor([uh_output()]).factory(), force=True
    )
    assert stopped.status == "budget_exceeded"
    db_session.expire_all()
    chapter = db_session.get(RegulationChapter, chapter_id)
    assert chapter.error == "organisation_budget_exceeded"
    assert _restart_reason(db_session, settings, chapter, utcnow(), True) is None
    set_limits(foreign, budget=100.0)
    db_session.expire_all()
    assert _restart_reason(db_session, settings, chapter, utcnow(), True) == "budget"


def test_ocr_quota_counts_confirmed_pages(
    client: Any, flags: None, login_as: Callable[..., Any], foreign: Organisation, db_session: Any
) -> None:
    login_as("architect", organisation=foreign)
    project = site_project(client)
    pdf, _pages = regulation_fixture()
    document = upload_regulation(client, project, with_scanned_pages(pdf, [10, 11])).json()["document"]["id"]
    read_document(document)

    set_limits(foreign, pages=1)
    refused = request_ocr(client, project, document)
    assert refused.status_code == 409
    assert refused.json()["code"] == "ocr_quota_exceeded" and refused.json()["remaining"] == 1

    set_limits(foreign, pages=5)
    assert request_ocr(client, project, document).status_code == 202
    db_session.expire_all()
    booked = db_session.execute(select(UsageRecord.quantity).where(UsageRecord.organisation_id == foreign.id))
    assert list(booked.scalars()) == [2]
    assert client.get("/api/v1/organisation/usage").json()["months"][0]["ocr_pages"] == 2


# ---------------------------------------------------------------------------
# Erscheinungsbild (3.5)
# ---------------------------------------------------------------------------


def test_branding_goes_into_report_and_dxf(
    client: Any,
    flags: None,
    login_as: Callable[..., Any],
    foreign: Organisation,
    db_session: Any,
    settings: Any,
) -> None:
    login_as("architect", organisation=foreign)
    project = site_project(client)
    an3.with_plu(client, project, db_session, settings)
    db_session.expire_all()
    plain = service.report_data(db_session, uuid.UUID(project))
    assert plain.branding is None
    plain_hash = report.report_hash(plain)

    too_light = client.patch("/api/v1/organisation", json={"accent_color": "#ffff00"})
    assert too_light.json()["code"] == "color_contrast_too_low"
    body = {
        "display_name": "Atelier Sud Architectes",
        "address_lines": ["12 rue de la Paix", "44000 Nantes"],
        "phone": "02 40 00 00 00",
        "registration": "Ordre des architectes S12345",
        "accent_color": "#1D4ED8",
    }
    updated = client.patch("/api/v1/organisation", json=body).json()
    assert updated["accent_color"] == "#1d4ed8" and updated["branding_revision"] == 1

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="http://example.org/x.png"/></svg>'
    rejected = client.put("/api/v1/organisation/logo", files={"file": ("logo.svg", svg, "image/svg+xml")})
    assert rejected.json()["code"] == "logo_format"
    big = client.put("/api/v1/organisation/logo", files={"file": ("logo.png", png((2400, 100)), "image/png")})
    assert big.json()["code"] == "logo_too_large"
    logo = client.put(
        "/api/v1/organisation/logo", files={"file": ("logo.png", png((1600, 800)), "image/png")}
    )
    assert logo.status_code == 200 and logo.json()["has_logo"] and logo.json()["branding_revision"] == 2
    stored = client.get("/api/v1/organisation/logo")
    with Image.open(io.BytesIO(stored.content)) as image:
        assert image.format == "PNG" and max(image.size) == organisations.LOGO_TARGET_PIXELS

    db_session.expire_all()
    data = service.report_data(db_session, uuid.UUID(project), with_logo=True)
    assert data.branding is not None and data.branding.logo_png
    assert report.report_hash(data) != plain_hash
    html_text = report.render_html(data, locale="fr", generated_at=utcnow(), report="sha256:x")
    assert "Atelier Sud Architectes" in html_text and "data:image/png;base64," in html_text
    assert "Ordre des architectes S12345" in html_text and "#1d4ed8" in html_text
    # Das Büro sieht davon nichts: sein Bericht bleibt wie vor AN6
    assert "Atelier Sud" not in report.render_html(
        plain, locale="fr", generated_at=utcnow(), report="sha256:x"
    )

    dxf = client.get(f"/api/v1/projects/{project}/analysis/export/dxf", params={"variant": "local"})
    assert dxf.status_code == 200, dxf.text[:200]
    doc = ezdxf.read(io.StringIO(dxf.content.decode()))
    texts = [e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == "CARTOUCHE"]
    assert texts[0] == "Atelier Sud Architectes" and "44000 Nantes" in texts
    assert any(t.startswith("Projet : ") and t.endswith(" - local") for t in texts)
