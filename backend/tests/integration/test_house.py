"""IFC-Import des Hausmodells über die API (docs/PLAN_HAUSMODELL.md 3.5, 3.6; HM3) gegen eine echte Datenbank.

Upload → Job im Kindprozess → Entwurf und Bericht → Angaben des Büros → Prüfung über `engine` (hier ein
`MockTransport`) → Freigabe. Das Demohaus aus `tests/house_support.py` steht für die Referenz-IFC; über die
API entsteht daraus dasselbe Template wie in den Testdaten.
"""

import json
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import cli
from app.config import get_settings
from app.house import service
from app.house.contract import HouseCompatibilityRequest
from app.house.engine import engine_client
from app.house.jobs import house_ifc_import
from app.house.models import HouseCatalogVersion, HouseTemplateVersion
from app.platform.jobs import JobContext
from app.platform.jobs.worker import run_one
from app.platform.models import AuditLog
from tests.house_support import DemoHouse, canonical, fixture, write_ifc

BASE = "/api/v1/admin/house"
ROLES = ["street", "side_right", "garden", "side_left"]
NAME = {"fr": "Maison de démonstration", "de": "Demohaus"}

Engine = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture(scope="module")
def demo_ifc(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return write_ifc(DemoHouse(), tmp_path_factory.mktemp("demo") / "demohaus.ifc").read_bytes()


@pytest.fixture
def catalog(db_session: Any) -> HouseCatalogVersion:
    version, _ = service.import_catalog(
        db_session, fixture("catalog"), source="test", publish=True, actor="test"
    )
    return version


@pytest.fixture
def engine_calls(app: Any) -> Iterator[list[dict[str, Any]]]:
    """Rechendienst als `MockTransport`: Jede Anfrage wird mit dem Vertrag geprüft und festgehalten."""
    calls: list[dict[str, Any]] = []
    answer: dict[str, Any] = {"domain_version": "0.3.0", "supported": True, "issues": []}

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        HouseCompatibilityRequest.model_validate(body)
        calls.append(body)
        return httpx2.Response(200, json=answer)

    app.dependency_overrides[engine_client] = lambda: httpx2.Client(
        base_url="http://engine.test", transport=httpx2.MockTransport(handler)
    )
    yield calls
    app.dependency_overrides.pop(engine_client, None)


def _engine(app: Any, handler: Engine) -> None:
    app.dependency_overrides[engine_client] = lambda: httpx2.Client(
        base_url="http://engine.test", transport=httpx2.MockTransport(handler)
    )


def _upload(client: Any, data: bytes, slug: str = "demo", name: str = "demohaus.ifc") -> Any:
    return client.post(
        f"{BASE}/templates/{slug}/versions", files={"file": (name, data, "application/x-step")}
    )


def _run_jobs() -> None:
    while run_one("test", ["long"]):
        pass


def _version(client: Any, number: int = 1, slug: str = "demo") -> dict[str, Any]:
    response = client.get(f"{BASE}/templates/{slug}/versions/{number}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _decide(client: Any, body: dict[str, Any], number: int = 1, **changes: Any) -> Any:
    return client.put(
        f"{BASE}/templates/demo/versions/{number}/decisions", json={**body["decisions"], **changes}
    )


def _with_roles(client: Any, number: int = 1, **changes: Any) -> dict[str, Any]:
    """Fassadenrollen zu den Segmenten des Entwurfs, wie das Büro sie in der Vorschau setzt."""
    body = _version(client, number)
    segments = [s["id"] for s in body["template"]["envelope"][0]["segments"]]
    response = _decide(client, body, number, facade_roles=dict(zip(segments, ROLES, strict=True)), **changes)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def _codes(body: dict[str, Any], *severities: str) -> list[str]:
    return [f["code"] for f in body["report"]["findings"] if not severities or f["severity"] in severities]


# --- Rechte und Eingaben -----------------------------------------------------------------------------------


def test_architect_and_ops_read_but_only_catalog_admin_uploads(
    client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes
) -> None:
    for role in ("architect", "ops"):
        login_as(role)
        assert client.get(f"{BASE}/templates").status_code == 200
        assert client.get(f"{BASE}/catalogs").status_code == 200
        assert _upload(client, demo_ifc).status_code == 403


def test_upload_needs_a_published_catalog(client: Any, login_as: Any, demo_ifc: bytes) -> None:
    login_as("catalog_admin")
    response = _upload(client, demo_ifc)
    assert response.status_code == 409
    assert response.json()["code"] == "house_catalog_missing"


@pytest.mark.parametrize(
    ("name", "data"),
    [("plan.pdf", b"ISO-10303-21;\nHEADER;"), ("haus.ifc", b"%PDF-1.7\n"), ("haus.ifczip", b"PK\x03\x04")],
)
def test_upload_accepts_only_ifc_files(
    client: Any, login_as: Any, catalog: HouseCatalogVersion, name: str, data: bytes
) -> None:
    login_as("catalog_admin")
    response = _upload(client, data, name=name)
    assert response.status_code == 422
    assert response.json()["code"] == "ifc_file_invalid"


def test_upload_stops_at_the_size_limit(
    client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_as("catalog_admin")
    monkeypatch.setenv("EMPRISE_HOUSE_IFC_MAX_BYTES", str(len(demo_ifc) - 1))
    get_settings.cache_clear()
    try:
        response = _upload(client, demo_ifc)
    finally:
        monkeypatch.delenv("EMPRISE_HOUSE_IFC_MAX_BYTES")
        get_settings.cache_clear()
    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


@pytest.mark.parametrize("slug", ["Demo", "demo-haus", "1demo", "_demo", "d", "x" * 61])
def test_slug_follows_catalog_convention(
    client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes, slug: str
) -> None:
    login_as("catalog_admin")
    assert _upload(client, demo_ifc, slug=slug).status_code == 422


# --- Ganzer Weg --------------------------------------------------------------------------------------------


def test_reference_ifc_through_the_api_gives_the_fixture_template(
    client: Any,
    login_as: Any,
    catalog: HouseCatalogVersion,
    demo_ifc: bytes,
    engine_calls: list[dict[str, Any]],
    db_session: Any,
) -> None:
    """Abnahme HM3 über den ganzen Weg: Upload, Job im Kindprozess, Entwurf, Prüfung, Freigabe."""
    user = login_as("catalog_admin", email="katalog@buero.test")
    uploaded = _upload(client, demo_ifc)
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert (body["status"], body["version"], body["report"], body["template"]) == ("draft", 1, None, None)
    assert body["job"]["status"] == "queued"
    assert body["catalog"]["version"] == catalog.version and body["catalog"]["current"]
    assert {t["id"] for t in body["catalog"]["room_types"]} >= {"living", "bedroom", "corridor"}
    assert _upload(client, demo_ifc).status_code == 200, "dieselbe Datei ergibt keine neue Version"
    listed = client.get(f"{BASE}/templates").json()
    assert [(v["version"], v["importing"]) for v in listed[0]["versions"]] == [(1, True)]

    _run_jobs()
    body = _version(client)
    assert body["job"]["status"] == "succeeded"
    assert _codes(body) == ["facade_roles_missing"]
    assert body["report"]["publishable"]

    body = _with_roles(client, name=NAME)
    assert body["report"]["findings"] == []
    assert canonical(body["template"]) == canonical(fixture("template"))
    assert body["template"]["source_ifc"]["file_name"] == "demohaus.ifc"

    checked = client.post(f"{BASE}/templates/demo/versions/1/check")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["status"] == "reviewed" and body["reviewed_by"]
    assert body["compatibility"]["supported"] and body["compatibility"]["approved_at"] is None
    assert canonical(engine_calls[0]["template"]) == canonical(fixture("template"))

    published = client.post(f"{BASE}/templates/demo/versions/1/publish")
    assert published.status_code == 200, published.text
    body = published.json()
    assert (body["status"], body["current"]) == ("published", True)
    assert body["compatibility"]["approved_by"] == body["published_by"] == str(user.id)
    assert body["people"] == {str(user.id): "katalog@buero.test"}, "Namen statt Konto-IDs in der Oberfläche"
    listed = client.get(f"{BASE}/templates").json()
    assert (listed[0]["current_version"], listed[0]["name"]) == (1, NAME)

    changed = _decide(client, body, ground_floor_offset=0.5)
    assert changed.status_code == 409
    assert changed.json()["code"] == "house_version_not_editable"
    actions = db_session.scalars(
        select(AuditLog.action).where(AuditLog.entity_type == "house_template_version").order_by(AuditLog.id)
    ).all()
    assert actions == [
        "house_template.upload",
        "house_template.decisions",
        "house_template.check",
        "house_template.publish",
    ]

    retired = client.post(f"{BASE}/templates/demo/versions/1/retire")
    assert retired.status_code == 200, retired.text
    assert (retired.json()["status"], retired.json()["current"]) == ("retired", False)


def test_published_version_and_its_approval_are_immutable(
    client: Any,
    login_as: Any,
    catalog: HouseCatalogVersion,
    demo_ifc: bytes,
    engine_calls: list[dict[str, Any]],
    db_session: Any,
) -> None:
    """Der Trigger hält Veröffentlichtes unabhängig vom Dienst fest (L4); nur `retired` mit Zeitpunkt geht."""
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    assert client.post(f"{BASE}/templates/demo/versions/1/check").status_code == 200
    assert client.post(f"{BASE}/templates/demo/versions/1/publish").status_code == 200
    forbidden = [
        "UPDATE house_template_version SET decisions = '{}'::jsonb WHERE version = 1",
        "UPDATE house_template_version SET status = 'retired', retired_at = now(), ifc_file_name = 'x.ifc'",
        "UPDATE house_template_version SET status = 'draft'",
        "DELETE FROM house_template_version",
        "UPDATE house_catalog_compatibility SET supported = false",
        "DELETE FROM house_catalog_compatibility",
        "UPDATE house_catalog_version SET document = '{}'::jsonb",
        "DELETE FROM house_catalog_version",
    ]
    for statement in forbidden:
        with pytest.raises(DBAPIError, match="immutable"):
            db_session.execute(text(statement))
        db_session.rollback()
    db_session.execute(
        text("UPDATE house_template_version SET status = 'retired', retired_at = now(), retired_by = 'test'")
    )
    db_session.commit()
    with pytest.raises(DBAPIError, match="immutable"):
        db_session.execute(text("UPDATE house_template_version SET status = 'published'"))
    db_session.rollback()


# --- Entwurf und Prüfung ----------------------------------------------------------------------------------


def test_open_points_block_the_check_until_the_office_decides(
    client: Any,
    login_as: Any,
    catalog: HouseCatalogVersion,
    engine_calls: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    house = DemoHouse()
    zones = {**house.zones, "bath": ("BUANDERIE", house.zones["bath"][1])}
    login_as("catalog_admin")
    _upload(client, write_ifc(replace(house, zones=zones), tmp_path / "haus.ifc").read_bytes())
    _run_jobs()
    body = _version(client)
    assert _codes(body, "error", "open") == ["zone_unrecognized"]
    assert not body["report"]["publishable"]

    blocked = client.post(f"{BASE}/templates/demo/versions/1/check")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "house_draft_open"
    assert engine_calls == []

    zone = next(z for z in body["report"]["zones"] if z["result"] == "unrecognized")
    decided = _decide(client, body, zone_types={zone["ifc_guid"]: "bathroom"})
    assert decided.status_code == 200, decided.text
    assert _codes(decided.json(), "error", "open") == []
    assert client.post(f"{BASE}/templates/demo/versions/1/check").json()["status"] == "reviewed"


def test_changed_decisions_send_a_reviewed_version_back_to_draft(
    client: Any,
    login_as: Any,
    catalog: HouseCatalogVersion,
    demo_ifc: bytes,
    engine_calls: list[dict[str, Any]],
) -> None:
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    reviewed = client.post(f"{BASE}/templates/demo/versions/1/check").json()
    assert reviewed["status"] == "reviewed"
    unchanged = _decide(client, reviewed)
    assert unchanged.json()["status"] == "reviewed", "dieselben Angaben ändern nichts"
    changed = _decide(client, reviewed, ground_floor_offset=0.35).json()
    assert (changed["status"], changed["compatibility"], changed["reviewed_at"]) == ("draft", None, None)
    assert changed["template"]["ground_floor_offset"] == 0.35
    assert (
        client.post(f"{BASE}/templates/demo/versions/1/publish").json()["code"]
        == "house_version_not_reviewed"
    )


def test_incompatible_template_stays_a_draft(
    app: Any, client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes
) -> None:
    issue = {"code": "type_slot_missing", "slot_id": None, "element_id": "roof", "ref_id": None}
    _engine(
        app,
        lambda request: httpx2.Response(
            200, json={"domain_version": "0.3.0", "supported": False, "issues": [issue]}
        ),
    )
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    body = client.post(f"{BASE}/templates/demo/versions/1/check").json()
    assert body["status"] == "draft"
    assert body["compatibility"]["issues"] == [issue]
    assert (
        client.post(f"{BASE}/templates/demo/versions/1/publish").json()["code"]
        == "house_version_not_reviewed"
    )


def test_rejection_of_the_core_becomes_an_issue(
    app: Any, client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes
) -> None:
    """422 des Kerns ist ein Befund der Dokumente, kein Ausfall (E-HM-36)."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/health":
            return httpx2.Response(200, json={"status": "ok", "domain": "0.3.0", "release": "test"})
        return httpx2.Response(422, json={"code": "mixed_wall_profiles", "detail": {"level": "level-x"}})

    _engine(app, handler)
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    body = client.post(f"{BASE}/templates/demo/versions/1/check").json()
    assert body["status"] == "draft"
    assert body["compatibility"]["domain_version"] == "0.3.0"
    assert body["compatibility"]["issues"] == [
        {"code": "mixed_wall_profiles", "slot_id": None, "element_id": None, "ref_id": "level=level-x"}
    ]


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx2.Response(500, json={"code": "internal_error", "detail": {}}),
        lambda request: httpx2.Response(200, json={"domain_version": "0.3.0"}),
        lambda request: (_ for _ in ()).throw(httpx2.ConnectError("engine down")),
    ],
    ids=["5xx", "contract", "down"],
)
def test_engine_failure_is_503_and_keeps_the_draft(
    app: Any, client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes, handler: Engine
) -> None:
    _engine(app, handler)
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    response = client.post(f"{BASE}/templates/demo/versions/1/check")
    assert response.status_code == 503
    assert response.json()["code"] == "engine_unavailable"
    assert _version(client)["status"] == "draft"


def test_new_catalog_version_needs_a_new_check(
    client: Any,
    login_as: Any,
    db_session: Any,
    catalog: HouseCatalogVersion,
    demo_ifc: bytes,
    engine_calls: list[dict[str, Any]],
) -> None:
    """Der Entwurf folgt der zuletzt veröffentlichten Katalogversion; geprüft wird gegen sie (3.6 Nr. 3)."""
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    _run_jobs()
    assert client.post(f"{BASE}/templates/demo/versions/1/check").json()["status"] == "reviewed"

    document = fixture("catalog")
    for room_type in document["room_types"]:
        if room_type["id"] == "bathroom":
            room_type["aliases"].append("BUANDERIE")
    newer, done = service.import_catalog(db_session, document, source="test", publish=True, actor="test")
    assert (newer.version, done) == (2, ["created", "published"])

    stale = client.post(f"{BASE}/templates/demo/versions/1/publish")
    assert stale.status_code == 409
    assert stale.json()["code"] == "house_catalog_changed"
    body = client.post(f"{BASE}/templates/demo/versions/1/check").json()
    assert (body["status"], body["catalog"]["version"], body["compatibility"]["catalog_version"]) == (
        "reviewed",
        2,
        2,
    )
    assert client.post(f"{BASE}/templates/demo/versions/1/publish").json()["status"] == "published"


def test_rejected_draft_is_not_imported(
    client: Any, login_as: Any, catalog: HouseCatalogVersion, demo_ifc: bytes
) -> None:
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    rejected = client.post(f"{BASE}/templates/demo/versions/1/reject")
    assert rejected.json()["status"] == "rejected"
    _run_jobs()
    body = _version(client)
    assert (body["report"], body["job"]["status"]) == (None, "succeeded")
    assert _upload(client, demo_ifc).json()["version"] == 2, "nach dem Verwerfen ist dieselbe Datei neu"
    assert (
        client.post(f"{BASE}/templates/demo/versions/1/check").json()["code"] == "house_version_not_editable"
    )


# --- Fehlerhafte Dateien und Job --------------------------------------------------------------------------


def test_unreadable_file_gives_a_report_and_is_read_again_on_upload(
    client: Any, login_as: Any, catalog: HouseCatalogVersion
) -> None:
    data = b"ISO-10303-21;\nkein IFC\n"
    login_as("catalog_admin")
    _upload(client, data)
    _run_jobs()
    body = _version(client)
    assert body["template"] is None and not body["report"]["publishable"]
    assert [(f["severity"], f["code"]) for f in body["report"]["findings"]] == [("error", "file_unreadable")]
    blocked = client.post(f"{BASE}/templates/demo/versions/1/check")
    assert blocked.json()["code"] == "house_import_incomplete"

    again = _upload(client, data)
    assert again.status_code == 200
    assert (again.json()["version"], again.json()["report"], again.json()["job"]["status"]) == (
        1,
        None,
        "queued",
    )


def test_last_failed_attempt_ends_the_import_with_a_finding(
    client: Any,
    login_as: Any,
    catalog: HouseCatalogVersion,
    demo_ifc: bytes,
    db_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_as("catalog_admin")
    _upload(client, demo_ifc)
    version_id = db_session.scalar(select(HouseTemplateVersion.id))

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Speicher weg")

    monkeypatch.setattr(service, "read_ifc", broken)
    for attempt in (1, 3):
        with pytest.raises(RuntimeError):
            house_ifc_import(
                JobContext(job_id=uuid.uuid4(), attempt=attempt, project_id=None),
                {"version_id": str(version_id)},
            )
        report = _version(client)["report"]
        assert (report is None) == (attempt == 1)
    assert [(f["code"], f["params"]) for f in report["findings"]] == [
        ("import_failed", {"detail": "RuntimeError: Speicher weg"})
    ]


# --- Katalog über die CLI ---------------------------------------------------------------------------------


def test_catalog_import_by_cli_from_file_and_stdin(
    client: Any,
    login_as: Any,
    db_session: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(fixture("catalog")), encoding="utf-8")

    def run(*args: str, stdin: str = "") -> str:
        monkeypatch.setattr(sys, "argv", ["app.cli", "house-catalog-import", *args])
        monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin))
        cli.main()
        return capsys.readouterr().out

    assert "Katalog 1 (draft, created)" in run(str(path))
    assert "Katalog 1 (draft, unverändert)" in run(str(path))
    assert "Katalog 1 (published, published)" in run("-", "--publish", stdin=path.read_text(encoding="utf-8"))
    login_as("ops")
    listed = client.get(f"{BASE}/catalogs").json()
    assert [(c["version"], c["status"], c["current"], c["source"]) for c in listed] == [
        (1, "published", True, "catalog.json")
    ]
    assert (listed[0]["room_types"], listed[0]["slots"]) == (5, 5)

    with pytest.raises(SystemExit):
        run("-", stdin=json.dumps({**fixture("catalog"), "market": "DE"}))
    assert "Katalog ungültig" in capsys.readouterr().err


def test_catalog_document_is_validated_and_deduplicated(db_session: Any) -> None:
    with pytest.raises(ValidationError):
        service.import_catalog(
            db_session, {**fixture("catalog"), "currency": "USD"}, source="x", publish=False
        )
    first, _ = service.import_catalog(db_session, fixture("catalog"), source="a", publish=False)
    # Dieselben Inhalte in anderer Schlüsselreihenfolge sind dasselbe Dokument
    reordered = dict(reversed(list(fixture("catalog").items())))
    second, done = service.import_catalog(db_session, reordered, source="b", publish=False)
    assert (second.id, done) == (first.id, [])
