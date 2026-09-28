"""Korrigieren und begründen (AN4, docs/PLAN_AN4_KORREKTUR.md) gegen PostGIS.

Grundlage wie AN3: Parzelle 20 × 30 m aus einer DXF-Datei, das Test-Reglement mit Zone Uh und die
aufgezeichnete Modellantwort (GRZ 25 %, Traufe 7 m, First 10 m), dazu das règlement de lotissement mit einer
Tabelle je Lot.
Die App läuft als Produkt „Emprise Analyse“.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.platform.models import AuditLog
from tests.integration import test_rules_upload as an2
from tests.integration.test_analysis import (
    choose_lot,
    evaluate_lots,
    lot_output,
    upload_lot_document,
    with_plu,
)
from tests.integration.test_rules_upload import new_project
from tests.rules_support import FakeExtractor

memory_storage = an2.memory_storage
settings = an2.settings
flags = an2.flags
architect = an2.architect
upload_project = an2.upload_project


@pytest.fixture
def app(clean_db: None) -> Any:
    from app.main import create_app

    return create_app(get_settings().model_copy(update={"product": "analyse"}))


def url(project: str, suffix: str = "") -> str:
    return f"/api/v1/projects/{project}/rule-overrides{suffix}"


def plu_rules(client: Any, project: str) -> dict[str, Any]:
    return client.get(f"/api/v1/admin/projects/{project}/rules").json()


def rule_of(rules: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(r for r in rules["zones"][0]["rules"] if r["kind"] == kind)


def analysis(client: Any, project: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects/{project}/analysis")
    assert response.status_code == 200, response.json()
    return response.json()


def ratio_correction(rules: dict[str, Any], **extra: Any) -> dict[str, Any]:
    ratio = rule_of(rules, "max_footprint_ratio")
    body = {
        "zone_code": "Uh",
        "kind": "max_footprint_ratio",
        "building_kind": ratio["building_kind"],
        "status": "effective",
        "params": {"ratio": 0.2},
        "note": "Modification simplifiée n° 2 : 20 % au lieu de 25 %",
        "source": {"document_id": rules["plan"]["id"], "page": ratio["page"], "quote": ratio["quote"]},
    }
    return {**body, **extra}


def test_rule_kinds_describe_the_form(client: Any, architect: Any) -> None:
    kinds = {k["kind"]: k for k in client.get("/api/v1/admin/rule-kinds").json()}
    assert len(kinds) == 15
    ratio = next(p for p in kinds["max_footprint_ratio"]["params"] if p["name"] == "ratio")
    assert (ratio["type"], ratio["required"], ratio["unit"], ratio["min"], ratio["max"]) == (
        "number",
        True,
        "share",
        0.0,
        1.0,
    )
    mode = next(p for p in kinds["setback_street"]["params"] if p["name"] == "mode")
    assert (mode["type"], mode["default"]) == ("choice", "min")


def test_correction_with_source_changes_the_analysis_and_can_be_withdrawn(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    rules = plu_rules(client, upload_project)
    before = analysis(client, upload_project)
    assert before["footprint"]["strict"]["value_m2"] == 150.0

    saved = client.put(url(upload_project), json=ratio_correction(rules))
    assert saved.status_code == 200, saved.json()
    [item] = saved.json()
    source = item["source"]
    page = rule_of(rules, "max_footprint_ratio")["page"]
    assert (source["page"], source["quote_verified"], source["attached"]) == (page, True, True)
    assert source["document_title"] == "PLUi Erdre et Gesvres"
    assert source["source_url"].endswith(f"#page={page}")
    assert item["active"] is True and item["note"].startswith("Modification")
    assert item["created_by"] is not None

    # Regeln: Herkunft Projekt mit Seite, die Begründung bleibt draußen (7.1 Nr. 8)
    corrected = rule_of(plu_rules(client, upload_project), "max_footprint_ratio")
    assert (corrected["origin"], corrected["page"], corrected["notes"]) == ("project", page, None)
    assert corrected["source_document_id"] == rules["plan"]["id"]
    envelope = client.get(f"/api/v1/admin/projects/{upload_project}/envelope").json()
    limit = next(x for x in envelope["parts"][0]["limits"] if x["key"] == "max_footprint_ratio")
    assert (limit["citation"]["origin"], limit["citation"]["page"]) == ("project", page)

    # Analyse: 20 % von 600 m² = 120 m²; Nutzfläche 120 × 2 × 0,85 = 204 bis 120 × 2,75 × 0,92 = 304 m²
    after = analysis(client, upload_project)
    assert after["footprint"]["strict"]["value_m2"] == 120.0
    assert (after["floor_area"]["low_m2"], after["floor_area"]["high_m2"]) == (204, 304)
    assert after["input_hash"] != before["input_hash"]

    # Vergleich „Korrekturen“ (3.5)
    comparison = client.get(f"/api/v1/projects/{upload_project}/analysis/comparison").json()
    assert (comparison["kind"], comparison["left"]["corrections"], comparison["right"]["corrections"]) == (
        "corrections",
        False,
        True,
    )
    figures = {f["key"]: f for f in comparison["figures"]}
    assert (figures["footprint_strict"]["left"], figures["footprint_strict"]["right"]) == (150.0, 120.0)
    assert (figures["floor_area_low"]["left"], figures["floor_area_low"]["right"]) == (255, 204)
    assert figures["height_top"]["changed"] is False
    changed = [r for r in comparison["rules"] if r["changed"]]
    assert [(r["kind"], r["left"]["params"]["ratio"], r["right"]["params"]["ratio"]) for r in changed] == [
        ("max_footprint_ratio", 0.25, 0.2)
    ]
    assert [b["kind"] for b in comparison["bases"]] == ["corrections"]

    removed = client.delete(url(upload_project, f"/{item['id']}"))
    assert removed.status_code == 200 and removed.json() == []
    assert analysis(client, upload_project)["footprint"]["strict"]["value_m2"] == 150.0
    assert client.get(f"/api/v1/projects/{upload_project}/analysis/comparison").json()["bases"] == []
    actions = set(db_session.execute(select(AuditLog.action)).scalars())
    assert {"project_rule_override.put", "project_rule_override.delete"} <= actions


def test_corrections_are_checked(client: Any, upload_project: str, db_session: Any, settings: Any) -> None:
    with_plu(client, upload_project, db_session, settings)
    rules = plu_rules(client, upload_project)

    def put(**extra: Any) -> Any:
        return client.put(url(upload_project), json=ratio_correction(rules, **extra))

    assert put(zone_code="Lot-12").json()["code"] == "zone_unknown"
    unknown = put(source={"document_id": str(uuid.uuid4()), "page": 1})
    assert (unknown.status_code, unknown.json()["code"]) == (422, "source_document_unknown")
    too_far = put(source={"document_id": rules["plan"]["id"], "page": 9999})
    assert (too_far.status_code, too_far.json()["code"]) == (422, "source_page_invalid")
    invalid = put(params={"ratio": 2})
    assert (invalid.status_code, invalid.json()["code"]) == (422, "rule_params_invalid")
    assert put(note="").status_code == 422
    assert put(status="text_only").status_code == 422

    # Zitat nicht auf der Seite: gespeichert, aber unbestätigt
    page = rule_of(rules, "max_footprint_ratio")["page"]
    elsewhere = put(source={"document_id": rules["plan"]["id"], "page": page, "quote": "ein Satz, der fehlt"})
    assert elsewhere.status_code == 200 and elsewhere.json()[0]["source"]["quote_verified"] is False

    # Ergänzen: Stellplätze fehlten; „nicht ermittelt“ nimmt einen Wert aus der Rechnung
    added = client.put(
        url(upload_project),
        json={
            "zone_code": "Uh",
            "kind": "parking",
            "building_kind": "any",
            "status": "effective",
            "params": {"spaces_per_dwelling": 2},
            "note": "Article 12 – oublié par la lecture automatique",
        },
    )
    assert added.status_code == 200, added.json()
    unknown_height = client.put(
        url(upload_project),
        json={
            "zone_code": "Uh",
            "kind": "max_height",
            "status": "unknown",
            "note": "Hauteur à vérifier en mairie",
        },
    )
    assert unknown_height.status_code == 200
    zone = plu_rules(client, upload_project)["zones"][0]
    parking = next(r for r in zone["rules"] if r["kind"] == "parking")
    assert (parking["origin"], parking["params"], parking["page"]) == (
        "project",
        {"spaces_per_dwelling": 2},
        None,
    )
    height = next(r for r in zone["rules"] if r["kind"] == "max_height")
    assert (height["status"], height["reason"]) == ("unknown", "correction")
    assert analysis(client, upload_project)["floor_area"]["low_m2"] is None


def test_corrections_need_an_owned_project(client: Any, db_session: Any, flags: None, login_as: Any) -> None:
    customer = new_project(client)
    assert client.get(url(customer)).status_code == 404
    login_as("architect")
    assert client.get(url(customer)).status_code == 404
    assert client.get(f"/api/v1/projects/{customer}/analysis/comparison").status_code == 404


def test_customer_view_of_rules_has_no_office_reasoning(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    """7.1 Nr. 8: Die Begründung erscheint nur in der Liste der Korrekturen."""
    with_plu(client, upload_project, db_session, settings)
    rules = plu_rules(client, upload_project)
    client.put(url(upload_project), json=ratio_correction(rules, source=None))
    corrected = rule_of(plu_rules(client, upload_project), "max_footprint_ratio")
    assert (corrected["notes"], corrected["page"], corrected["source_url"]) == (None, None, None)
    [item] = client.get(url(upload_project)).json()
    assert item["note"].startswith("Modification") and item["source"] is None


def test_adopting_values_from_the_lotissement(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    document_id = upload_lot_document(client, upload_project)
    assert choose_lot(client, upload_project, document_id, lot="12").status_code == 200
    evaluate_lots(db_session, settings, document_id, FakeExtractor([lot_output()]))

    first = analysis(client, upload_project)
    comparisons = {c["kind"]: c for c in first["supplements"][0]["comparisons"]}
    height, area = comparisons["max_height"], comparisons["max_area"]
    assert height["verdict"] == "stricter"
    # 7.1 Nr. 1: die Traufe des PLU bleibt, der First des Lotissement bindet
    assert (height["proposal"]["eave_m"], height["proposal"]["ridge_m"]) == (7.0, 8.0)
    assert (area["verdict"], area["proposal"]) == (
        "only_supplement",
        {"sdp_m2": 180.0, "footprint_m2": 120.0},
    )
    assert comparisons["setback_side"]["proposal"] is None
    assert first["supplement_stricter"] == ["max_area", "max_height"]

    for comparison in (height, area):
        citation = comparison["supplement"]["citation"]
        response = client.put(
            url(upload_project),
            json={
                "zone_code": "Uh",
                "kind": comparison["kind"],
                "building_kind": comparison["building_kind"],
                "status": "effective",
                "params": comparison["proposal"],
                "note": "Lotissement autorisé en 2021, règles applicables (L.442-9)",
                "source": {"document_id": document_id, "page": citation["page"], "quote": citation["quote"]},
            },
        )
        assert response.status_code == 200, response.json()
    assert all(item["source"]["quote_verified"] for item in response.json())

    after = analysis(client, upload_project)
    verdicts = {c["kind"]: c["verdict"] for c in after["supplements"][0]["comparisons"]}
    assert (verdicts["max_height"], verdicts["max_area"], verdicts["setback_side"]) == (
        "adopted",
        "adopted",
        "no_own_rule",
    )
    assert after["supplement_stricter"] == [] and "supplement_stricter" not in after["warnings"]
    strict = after["parts"][0]["footprint"]["strict"]
    assert (strict["value_m2"], strict["binding"]) == (120.0, "absolute")
    assert (after["floor_area"]["low_m2"], after["floor_area"]["high_m2"], after["floor_area"]["capped"]) == (
        180,
        180,
        True,
    )
    assert after["gabarit"]["top_m"] == 8.0


def test_comparing_two_evaluations(client: Any, upload_project: str, db_session: Any, settings: Any) -> None:
    """Zweite Version des Regelwerks (hier eine Büro-Version mit GRZ 30 %): beide Seiten ohne Korrekturen."""
    with_plu(client, upload_project, db_session, settings)
    zone = plu_rules(client, upload_project)["zones"][0]
    detail = client.get(f"/api/v1/admin/rule-sets/{zone['rule_set_id']}").json()
    rules = [
        {
            "kind": r["kind"],
            "building_kind": r["building_kind"],
            "status": r["status"],
            "params": {"ratio": 0.3} if r["kind"] == "max_footprint_ratio" else r["params"],
            "page": r["page"],
            "quote": r["quote"],
        }
        for r in detail["rules"]
    ]
    created = client.post(
        f"/api/v1/admin/rule-sets/{zone['rule_set_id']}/versions", json={"rules": rules, "note": "Relecture"}
    )
    assert created.status_code == 201, created.json()
    # Eine Korrektur wirkt nur rechts im Vergleich „Korrekturen“, nicht im Versionsvergleich
    client.put(url(upload_project), json=ratio_correction(plu_rules(client, upload_project)))

    offer = client.get(f"/api/v1/projects/{upload_project}/analysis/comparison").json()["bases"]
    assert [b["kind"] for b in offer] == ["corrections", "versions"]
    earlier = offer[1]
    assert (earlier["zone_code"], earlier["version"]["version"]) == ("Uh", 1)
    comparison = client.get(
        f"/api/v1/projects/{upload_project}/analysis/comparison", params={"base": earlier["base"]}
    ).json()
    assert comparison["kind"] == "versions"
    assert (comparison["left"]["version"]["version"], comparison["right"]["version"]["version"]) == (1, 2)
    assert comparison["left"]["corrections"] is False and comparison["right"]["corrections"] is False
    figures = {f["key"]: f for f in comparison["figures"]}
    assert (figures["footprint_strict"]["left"], figures["footprint_strict"]["right"]) == (150.0, 180.0)
    rows = {r["kind"]: r for r in comparison["rules"] if r["building_kind"] == "main"}
    ratio = rows["max_footprint_ratio"]
    assert ratio["changed"] and (ratio["left"]["params"], ratio["right"]["params"]) == (
        {"ratio": 0.25},
        {"ratio": 0.3},
    )
    assert rows["max_height"]["changed"] is False
    # Die Büro-Version kennt keinen Grund für „nicht ermittelt“; ohne Grund gilt `missing` – keine Änderung
    assert rows["roof"]["right"]["reason"] is None and rows["roof"]["changed"] is False
    assert [r["kind"] for r in comparison["rules"] if r["changed"]] == ["max_footprint_ratio"]
    assert comparison["left"]["status"] == "ok"

    missing = client.get(
        f"/api/v1/projects/{upload_project}/analysis/comparison", params={"base": str(uuid.uuid4())}
    )
    assert (missing.status_code, missing.json()["code"]) == (404, "version_not_found")
