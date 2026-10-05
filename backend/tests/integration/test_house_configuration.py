"""Kundenweg des Hausmodells (docs/PLAN_HAUSMODELL.md 3.7–3.9; HM4) gegen PostGIS auf dem Testgrundstück AD 65
(Zone Uh). `engine` ist ein `MockTransport` mit den Antworten des Kerns aus `evaluations.json`.

Abnahme HM4: Die Konfiguration lädt nach einer Katalogänderung unverändert; Preise gehen gerundet an den
Kunden, exakt nur in den Snapshot; der Preis aus dem Browser wird mit dem des Servers verglichen. Abnahme HM5:
das R+1 mit Satteldach auf AD 65, geprüft wie im heutigen Konfigurator.
"""

import copy
import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx2
import pytest
from sqlalchemy import select

from app.configuration.models import HouseConfigurationRecord
from app.house import service as house_service
from app.house.contract import HouseEvaluateRequest
from app.house.engine import engine_client
from app.house.models import HouseCatalogVersion, HouseTemplateVersion
from app.platform.models import FeatureFlag
from tests.house_support import fixture, publish_template
from tests.integration import test_envelope as _envelope

# Fixtures des Baurahmen-Tests: Grundstück AD 65 mit ausgewerteter Zone Uh (pytest findet sie nach Namen)
memory_storage = _envelope.memory_storage
project = _envelope.project
sessions = _envelope.sessions
settings = _envelope.settings

EVALUATIONS = fixture("evaluations")
STANDARD_NET = EVALUATIONS["standard"]["evaluation"]["price"]["net_amount"]
BRICK_NET = EVALUATIONS["brick"]["evaluation"]["price"]["net_amount"]
BRICK = EVALUATIONS["brick"]["configuration"]
EXACT = ("net_amount", "gross_amount", "vat_amount", "base_amount", "unit_price")


@pytest.fixture
def house_model(db_session: Any) -> None:
    db_session.add(FeatureFlag(key="house_model", enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def catalog(db_session: Any) -> HouseCatalogVersion:
    version, _ = house_service.import_catalog(
        db_session, fixture("catalog"), source="test", publish=True, actor="test"
    )
    return version


@pytest.fixture
def offered(db_session: Any, catalog: HouseCatalogVersion) -> HouseTemplateVersion:
    """Demohaus, veröffentlicht und mit dem Katalog freigegeben."""
    version: HouseTemplateVersion = publish_template(db_session, catalog, fixture("template"))
    return version


def _scaled(facts: dict[str, Any], factor: float) -> None:
    for key in ("facade_outline", "projection_outline"):
        facts[key] = [{"x": p["x"] * factor, "y": p["y"] * factor} for p in facts[key]]


@pytest.fixture
def engine_calls(app: Any) -> Iterator[list[dict[str, Any]]]:
    """Kern als `MockTransport`: Antworten aus `evaluations.json` nach Haustyp und Auswahl; jede Anfrage wird
    mit dem Vertrag geprüft und festgehalten. Haustyp `gross_haus` ist das Demohaus in dreifacher Größe."""
    calls: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        HouseEvaluateRequest.model_validate(body)
        calls.append(body)
        slug = "demo_house" if body["template"]["slug"] == "gross_haus" else body["template"]["slug"]
        found = next(
            (
                c
                for c in EVALUATIONS.values()
                if c["template"] == slug and c["configuration"] == body["configuration"]
            ),
            None,
        )
        if found is None:
            return httpx2.Response(422, json={"code": "option_unknown", "detail": {"slot": "wall_profile"}})
        evaluation = copy.deepcopy(found["evaluation"])
        if body["template"]["slug"] == "gross_haus":
            _scaled(evaluation["facts"], 3.0)
        return httpx2.Response(200, json=evaluation)

    _engine(app, handler)
    yield calls
    app.dependency_overrides.pop(engine_client, None)


def _engine(app: Any, handler: Callable[[httpx2.Request], httpx2.Response]) -> None:
    app.dependency_overrides[engine_client] = lambda: httpx2.Client(
        base_url="http://engine.test", transport=httpx2.MockTransport(handler)
    )


def url(project_id: str, path: str = "configuration") -> str:
    return f"/api/v1/projects/{project_id}/house/{path}"


def patch(client: Any, project_id: str, body: dict[str, Any], revision: int | None = None) -> Any:
    headers = {"If-Match": str(revision)} if revision is not None else {}
    return client.patch(url(project_id), json=body, headers=headers)


def choose(client: Any, project_id: str) -> dict[str, Any]:
    response = patch(client, project_id, {"template_slug": "demo_house"}, revision=0)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def exact_keys(value: Any) -> set[str]:
    """Schlüssel exakter Beträge irgendwo in der Antwort (L1: der Kunde sieht nur gerundete)."""
    if isinstance(value, dict):
        found = {k for k in value if k in EXACT}
        for item in value.values():
            found |= exact_keys(item)
        return found
    if isinstance(value, list):
        return set().union(*(exact_keys(v) for v in value)) if value else set()
    return set()


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------


def test_house_model_is_off_without_the_flag(client: Any, project: str, offered: Any) -> None:
    for path in ("templates", "configuration", "configuration/documents"):
        response = client.get(url(project, path))
        assert response.status_code == 403 and response.json()["code"] == "feature_disabled"


def test_configuration_is_private_to_the_project(
    client: Any, app: Any, project: str, house_model: None
) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as stranger:
        assert stranger.get(url(project)).status_code == 404
        assert stranger.get(url(project, "templates")).status_code == 404


def test_office_reads_the_configuration_by_role(client: Any, project: str, login_as: Any) -> None:
    office = f"/api/v1/admin/projects/{project}/house/configuration"
    assert client.get(office).status_code in (401, 403)
    login_as("architect")
    body = client.get(office).json()
    assert body["revision"] == 0 and body["template"] is None and body["snapshot"] is None
    assert body["simulation"] is True


# ---------------------------------------------------------------------------
# Angebot
# ---------------------------------------------------------------------------


def test_templates_show_admissibility_and_a_rounded_price_from(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: list[dict[str, Any]]
) -> None:
    response = client.get(url(project, "templates"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["simulation"] is True and body["mode"] == "rules"
    [demo] = body["templates"]
    assert demo["slug"] == "demo_house" and demo["version"] == 1 and demo["catalog_version"] == 1
    assert demo["name"] == {"fr": "Maison de démonstration", "de": "Demohaus"}
    assert demo["allowed"] is True and demo["reasons"] == [] and demo["rotations"]
    # 515.194,21 € brutto auf 1.000 € gerundet (3.8)
    assert demo["price"]["gross_rounded"] == 515_000 and demo["price"]["deltas_rounded"] == {}
    facts = demo["facts"]
    assert facts["footprint_m2"] == pytest.approx(110.92) and facts["storeys"] == "R"
    assert (facts["width_m"], facts["depth_m"]) == (12.72, 8.72)
    assert facts["facade_material"] == "render" and facts["roof_form"] == "flat"
    assert exact_keys(body) == set()
    assert [call["configuration"] for call in engine_calls] == [{"selections": {}}]


def test_two_storey_type_on_ad65_is_checked_like_today(
    client: Any, project: str, house_model: None, catalog: Any, db_session: Any, engine_calls: Any
) -> None:
    """Abnahme HM5: das R+1 (Satteldach 35°) auf AD 65, Zone Uh, mit denselben Prüfungen wie im heutigen
    Konfigurator: Lage, Bauband und Grundfläche eingehalten; Höhen ohne Gelände nicht prüfbar, Dach und
    unversiegelte Fläche ohne Regel (Warnungen). Traufe und First mit Gelände: `test_house_site_check.py`."""
    publish_template(db_session, catalog, fixture("template-r1"))
    [offer] = client.get(url(project, "templates")).json()["templates"]
    assert (offer["slug"], offer["allowed"]) == ("demo_house_r1", True)
    facts = offer["facts"]
    assert (facts["storeys"], facts["roof_form"], facts["pitch_deg"]) == ("R+1", "gable", 35.0)
    assert facts["height_m"] == pytest.approx(9.143, abs=1e-3)
    assert facts["eave_height_m"] == pytest.approx(5.74, abs=1e-3)

    response = patch(client, project, {"template_slug": "demo_house_r1"}, revision=0)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["placement"] is not None and body["evaluation"]["valid"] is True
    checks = {c["code"]: (c["status"], c["binding"], c["reason"]) for c in body["evaluation"]["checks"]}
    assert {"band_building", "footprint", "setback_street", "setback_side", "setback_rear"} <= set(checks)
    assert all(status == "pass" for status, binding, _ in checks.values() if binding)
    assert checks["height_unverifiable"] == ("unknown", False, "terrain_unavailable")
    assert checks["roof_unknown"] == ("unknown", False, "missing")
    outcomes = {r["check"]["code"]: r["outcome"] for r in body["site_results"]}
    assert outcomes == {
        "height_unverifiable": "warning",
        "roof_unknown": "warning",
        "unsealed_min_unknown": "warning",
        "parking_not_shown": "info",
    }
    assert body["status"] == "valid_with_warnings"
    assert [call["template"]["slug"] for call in engine_calls] == ["demo_house_r1", "demo_house_r1"]


def test_only_approved_pairs_are_offered(
    client: Any, project: str, house_model: None, catalog: Any, db_session: Any, engine_calls: Any
) -> None:
    publish_template(db_session, catalog, fixture("template"), approved=False)
    assert client.get(url(project, "templates")).json()["templates"] == []
    response = patch(client, project, {"template_slug": "demo_house"})
    assert response.status_code == 404 and response.json()["code"] == "house_template_not_found"


def test_template_without_a_valid_position_is_blocked_with_all_reasons(
    client: Any, project: str, house_model: None, catalog: Any, db_session: Any, engine_calls: Any
) -> None:
    """D12: Das Demohaus in dreifacher Größe (38 × 26 m) passt nicht auf AD 65."""
    publish_template(db_session, catalog, {**fixture("template"), "slug": "gross_haus"})
    [gross] = client.get(url(project, "templates")).json()["templates"]
    assert gross["allowed"] is False and gross["reasons"]
    assert all(r["binding"] and r["status"] == "fail" for r in gross["reasons"])
    response = patch(client, project, {"template_slug": "gross_haus"})
    assert response.status_code == 422
    assert response.json()["code"] == "type_blocked" and response.json()["reasons"]
    assert client.get(url(project)).json()["revision"] == 0


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------


def test_choosing_a_template_pins_its_versions_and_places_it_near_the_street(
    client: Any,
    project: str,
    house_model: None,
    offered: Any,
    catalog: Any,
    engine_calls: list[dict[str, Any]],
    login_as: Any,
) -> None:
    empty = client.get(url(project)).json()
    assert empty["revision"] == 0 and empty["template"] is None and empty["placement"] is None

    body = choose(client, project)
    assert body["revision"] == 1
    assert body["template"] == {
        "slug": "demo_house",
        "version": 1,
        "catalog_version": 1,
        "name": {"fr": "Maison de démonstration", "de": "Demohaus"},
        "retired": False,
    }
    assert body["update_available"] is False and body["configuration"] == {"selections": {}}
    # Schnellstellung „straßennah“ (Spez. 5.3.5): zulässig, ohne Abweichung
    assert body["placement"] is not None and body["evaluation"]["valid"] is True
    assert body["status"] in ("valid", "valid_with_warnings")
    assert all(r["outcome"] != "deviation" for r in body["site_results"])
    assert body["suggestion"] is None and body["areas"]["house_m2"] == pytest.approx(110.92)
    assert body["price"]["gross_rounded"] == 515_000 and body["domain_version"] == "0.4.0"
    assert body["facts"]["facade_local"] and body["rotations"]
    assert exact_keys(body) == set()
    # Ein Aufruf des Kerns: Die Standards rechnet die Wahl des Haustyps schon (D12)
    assert len(engine_calls) == 1

    # Lesen braucht den Kern nicht: Hausbeschreibung aus dem Snapshot
    again = client.get(url(project)).json()
    assert len(engine_calls) == 1
    assert {k: v for k, v in again.items() if k != "price_match"} == {
        k: v for k, v in body.items() if k != "price_match"
    }

    login_as("architect")
    office = client.get(f"/api/v1/admin/projects/{project}/house/configuration").json()
    assert office["template_version_id"] == str(offered.id)
    assert office["catalog_version_id"] == str(catalog.id)
    snapshot = office["snapshot"]
    assert snapshot["evaluation"]["price"]["net_amount"] == STANDARD_NET
    assert snapshot["domain_version"] == "0.4.0" and snapshot["price_check"] is None
    assert snapshot["site"]["status"] == body["status"] and snapshot["site"]["input_parts"]


def test_selection_with_deviation_is_saved_with_its_price_check(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any, db_session: Any
) -> None:
    """E-HM-6: Eine Lage außerhalb des Grundstücks wird gespeichert und bewertet, mit Vorschlag."""
    chosen = choose(client, project)
    rotation = chosen["placement"]["rotation_deg"]
    body = {
        "configuration": BRICK,
        "placement": {"origin": {"e": 500.0, "n": 500.0}, "rotation_deg": rotation},
        "client_price": {"net_amount": BRICK_NET, "domain_version": "0.4.0"},
    }
    response = patch(client, project, body, revision=1)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] == 2 and saved["price_match"] is True
    # 523.547,56 € → 524.000 €; Aufpreis 6.961,12 € netto → 8.353,34 € brutto → 8.400 €
    assert saved["price"]["gross_rounded"] == 524_000
    assert saved["price"]["deltas_rounded"] == {"wall_profile": 8_400}
    assert saved["facts"]["facade_material"] == "brick" and saved["facts"]["width_m"] == 12.96
    assert saved["status"] == "with_deviations"
    deviations = {r["check"]["code"] for r in saved["site_results"] if r["outcome"] == "deviation"}
    assert "outside_site" in deviations
    assert saved["site_results"][0]["outcome"] == "deviation"
    assert saved["suggestion"] is not None and saved["suggestion"]["rotation_deg"] == rotation
    assert saved["placement"]["origin"] == {"e": 500.0, "n": 500.0}

    row = db_session.scalar(select(HouseConfigurationRecord))
    assert row.snapshot["price_check"] == {"client_net": BRICK_NET, "match": True}
    assert row.snapshot["evaluation"]["price"]["net_amount"] == BRICK_NET
    assert row.engine_version == "0.4.0"

    # Der Vorschlag ist eine zulässige Lage
    moved = patch(client, project, {"placement": saved["suggestion"]}, revision=2).json()
    assert moved["evaluation"]["valid"] is True and moved["suggestion"] is None
    assert moved["status"] != "with_deviations"


def test_terrace_and_carport_are_placed_on_the_site(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    """Ergänzung 7 (HM5): Terrasse und Carport aus den Slots `site`; Lage, Zufahrt und Flächen rechnet Python
    wie im heutigen Konfigurator."""
    choose(client, project)
    body = {"configuration": EVALUATIONS["outbuildings"]["configuration"]}
    response = patch(client, project, body, revision=1)
    assert response.status_code == 200, response.text
    saved = response.json()
    terrace, carport = saved["outbuildings"]["terrace"], saved["outbuildings"]["carport"]
    assert (terrace["slug"], terrace["placed"], terrace["area_m2"]) == ("terrace.wood", True, 38.16)
    assert (carport["slug"], carport["placed"], carport["spaces"]) == ("carport.single", True, 1)
    assert terrace["polygon_local"] and carport["polygon_local"]
    assert [d["source"] for d in saved["outbuildings"]["driveways"]] == ["carport"]
    areas = saved["areas"]
    assert (areas["terrace_m2"], areas["carport_m2"], areas["emprise_m2"]) == (38.16, 15.0, 125.92)
    # 9.500 € netto → 11.400 € brutto; 6.868,80 € → 8.242,56 € → 8.200 €
    assert saved["price"]["deltas_rounded"] == {"carport": 11_400, "terrace": 8_200}
    outcomes = {r["check"]["code"]: r["outcome"] for r in saved["site_results"]}
    assert outcomes["carport_setback_relaxed"] == "info" and "deviation" not in outcomes.values()
    assert client.get(url(project)).json()["outbuildings"] == saved["outbuildings"]


def test_differing_browser_price_is_reported_but_saved(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    choose(client, project)
    body = {
        "configuration": BRICK,
        "client_price": {"net_amount": BRICK_NET + 0.01, "domain_version": "0.2.9"},
    }
    response = patch(client, project, body)
    assert response.status_code == 200 and response.json()["price_match"] is False
    assert response.json()["revision"] == 2


def test_configuration_loads_unchanged_after_catalog_and_template_change(
    client: Any,
    project: str,
    house_model: None,
    offered: Any,
    catalog: Any,
    engine_calls: list[dict[str, Any]],
    db_session: Any,
    login_as: Any,
) -> None:
    """Abnahme HM4 (E-HM-7): Template- und Katalogversion bleiben festgehalten; die neuere wird angezeigt."""
    choose(client, project)
    saved = patch(client, project, {"configuration": BRICK}).json()

    changed = fixture("catalog")
    for entry in changed["price_entries"]:
        entry["value"] = round(entry["value"] * 1.1, 2)
    new_catalog, _ = house_service.import_catalog(
        db_session, changed, source="test", publish=True, actor="test"
    )
    assert new_catalog.version == 2
    template_v2 = publish_template(db_session, new_catalog, fixture("template"))
    offered.status = "retired"
    db_session.commit()

    calls = len(engine_calls)
    loaded = client.get(url(project)).json()
    assert len(engine_calls) == calls
    assert loaded["template"]["version"] == 1 and loaded["template"]["catalog_version"] == 1
    assert loaded["template"]["retired"] is True and loaded["update_available"] is True
    assert loaded["price"] == saved["price"] and loaded["configuration"] == BRICK
    assert loaded["facts"] == saved["facts"] and loaded["status"] == saved["status"]

    # Weiterarbeiten rechnet mit den festgehaltenen Dokumenten
    documents = client.get(url(project, "configuration/documents")).json()
    assert documents["template_version_id"] == str(offered.id)
    assert documents["catalog_version_id"] == str(catalog.id)
    assert documents["catalog"]["price_entries"] == fixture("catalog")["price_entries"]
    moved = patch(client, project, {"boundary_options": {}}).json()
    assert moved["template"]["version"] == 1 and moved["template"]["catalog_version"] == 1
    assert engine_calls[-1]["catalog"]["price_entries"] == fixture("catalog")["price_entries"]

    # Ein neues Projekt bekommt die neuen Versionen
    other = str(client.post("/api/v1/projects").json()["id"])
    assert (
        client.put(f"/api/v1/projects/{other}/site", json={"parcel_idus": [_envelope.REGULAR]}).status_code
        == 200
    )
    fresh = choose(client, other)
    assert fresh["template"]["version"] == 2 and fresh["template"]["catalog_version"] == 2
    assert fresh["update_available"] is False
    login_as("architect")
    office = client.get(f"/api/v1/admin/projects/{other}/house/configuration").json()
    assert office["template_version_id"] == str(template_v2.id)


def test_stale_revision_is_a_conflict(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    choose(client, project)
    stale = patch(client, project, {"configuration": BRICK}, revision=0)
    assert stale.status_code == 409
    assert stale.json()["code"] == "revision_conflict" and stale.json()["current_revision"] == 1
    assert patch(client, project, {"configuration": BRICK}, revision=1).status_code == 200


def test_rejections_change_nothing(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    assert patch(client, project, {"configuration": BRICK}).json()["code"] == "no_house_template_selected"
    assert client.get(url(project, "configuration/documents")).json()["code"] == "no_house_template_selected"
    assert client.get(url(project, "configuration/placement-area")).status_code == 409
    chosen = choose(client, project)
    origin = chosen["placement"]["origin"]

    rotation = patch(client, project, {"placement": {"origin": origin, "rotation_deg": 45.0}})
    assert rotation.status_code == 422
    assert rotation.json()["code"] == "rotation_not_allowed" and len(rotation.json()["allowed"]) == 4

    boundary = patch(client, project, {"boundary_options": {"99": True}})
    assert boundary.status_code == 422
    assert boundary.json()["code"] == "boundary_not_allowed" and boundary.json()["edges"] == [99]

    gold = {"type": "option", "option_value_id": "wall.gold"}
    unknown = {"selections": {"wall_profile": {**BRICK["selections"]["wall_profile"], "value": gold}}}
    invalid = patch(client, project, {"configuration": unknown})
    assert invalid.status_code == 422
    assert (
        invalid.json()["code"] == "house_selection_invalid" and invalid.json()["reason"] == "option_unknown"
    )

    after = client.get(url(project)).json()
    assert after["revision"] == 1 and after["placement"] == chosen["placement"]


def test_engine_failure_is_503_and_saves_nothing(
    client: Any, app: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    choose(client, project)

    def down(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("engine down")

    _engine(app, down)
    response = patch(client, project, {"configuration": BRICK})
    assert response.status_code == 503 and response.json()["code"] == "engine_unavailable"
    # Lesen geht weiter ohne den Kern
    body = client.get(url(project)).json()
    assert body["revision"] == 1 and body["configuration"] == {"selections": {}}


def test_placement_area_presets_and_documents_for_the_saved_selection(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    chosen = choose(client, project)
    area = client.get(url(project, "configuration/placement-area")).json()
    assert area["type_slug"] == "demo_house"
    entry = next(r for r in area["rotations"] if r["rotation_deg"] == chosen["placement"]["rotation_deg"])
    assert entry["area_m2"] > 0 and entry["rings_local"]
    presets = client.post(url(project, "configuration/placement-presets")).json()
    assert set(presets["presets"]) == {"street_near", "set_back", "garden_max"}
    assert presets["presets"]["street_near"] == chosen["placement"]
    documents = client.get(url(project, "configuration/documents")).json()
    assert documents["template"]["slug"] == "demo_house" and documents["catalog"]["price_entries"]


def test_clearing_the_template_empties_the_configuration(
    client: Any, project: str, house_model: None, offered: Any, engine_calls: Any
) -> None:
    choose(client, project)
    response = patch(client, project, {"template_slug": None}, revision=1)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2 and body["template"] is None and body["placement"] is None
    assert body["price"] is None and body["status"] is None
    assert client.get(url(project, "configuration/documents")).status_code == 409
