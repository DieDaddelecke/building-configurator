"""Endpunkte des Moduls H1 gegen eine echte Datenbank (Plan H1 6)."""

import io
from typing import Any

import ezdxf
import pytest
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.catalog.domain.tolerances import FOOTPRINT_LAYER_FACADE, FOOTPRINT_LAYER_PROJECTION

LIGNE_KENNWERTE = {
    "name": "Ligne",
    "geschosse": "R+1",
    "dachform": "gable",
    "neigung_deg": "40",
    "firstrichtung": "laengs",
    "firsthoehe_m": "8.4",
    "traufhoehe_m": "5.6",
    "wohnflaeche_m2": "158",
    "zimmer_text": "4 Zimmer, 1 Bad + 1 Gäste-WC",
    "basispreis_min_eur": "328000",
    "basispreis_max_eur": "362000",
}
ROOMS = [("Wohnen", "living", "R", 42.0), ("Bad", "bathroom", "R", 6.0)]
FACADE_10x8 = [(0, 0), (12, 0), (12, 8), (0, 8)]
PROJECTION_11x9 = [(-0.5, -0.5), (12.5, -0.5), (12.5, 8.5), (-0.5, 8.5)]


def _xlsx(kennwerte: dict[str, str], rooms: list[tuple[Any, ...]], prices: list[tuple[Any, ...]]) -> bytes:
    wb = Workbook()
    k = wb.active
    k.title = "Kennwerte"
    for key, value in kennwerte.items():
        k.append([key, value])
    r = wb.create_sheet("Räume")
    r.append(["name", "kategorie", "geschoss", "flaeche_m2"])
    for row in rooms:
        r.append(list(row))
    p = wb.create_sheet("Preise")
    p.append(["art", "referenz", "aufpreis_eur"])
    for row in prices:
        p.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dxf(facade: list[tuple[float, float]], projection: list[tuple[float, float]]) -> bytes:
    doc = ezdxf.new()
    doc.layers.add(FOOTPRINT_LAYER_FACADE)
    doc.layers.add(FOOTPRINT_LAYER_PROJECTION)
    msp = doc.modelspace()
    msp.add_lwpolyline(facade, close=True, dxfattribs={"layer": FOOTPRINT_LAYER_FACADE})
    msp.add_lwpolyline(projection, close=True, dxfattribs={"layer": FOOTPRINT_LAYER_PROJECTION})
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def _upload(client: Any, slug: str, kennwerte: dict[str, str], prices: list[tuple[Any, ...]]) -> Any:
    return client.post(
        f"/api/v1/admin/catalog/types/{slug}/versions",
        files={
            "xlsx": ("typ.xlsx", _xlsx(kennwerte, ROOMS, prices), "application/octet-stream"),
            "dxf": ("typ.dxf", _dxf(FACADE_10x8, PROJECTION_11x9), "application/octet-stream"),
        },
    )


def test_list_types_needs_a_session(client: Any) -> None:
    response = client.get("/api/v1/admin/catalog/types")
    assert response.status_code == 401


def test_ops_can_read_but_not_import(client: Any, login_as: Any) -> None:
    login_as("ops")
    assert client.get("/api/v1/admin/catalog/types").status_code == 200
    response = _upload(client, "ligne", LIGNE_KENNWERTE, [])
    assert response.status_code == 403


def test_import_creates_a_draft_with_pitch_mismatch_warning(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    response = _upload(client, "ligne", LIGNE_KENNWERTE, [])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["footprint_facade_area_m2"] == pytest.approx(96.0)
    codes = [w["code"] for w in body["consistency_warnings"]]
    assert "pitch_mismatch" in codes  # Spez. 5.4.5: 40° angegeben, 35,0° aus den Höhen berechnet


def test_second_import_of_the_same_type_bumps_the_version(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    _upload(client, "ligne", LIGNE_KENNWERTE, [])
    response = _upload(client, "ligne", {**LIGNE_KENNWERTE, "neigung_deg": "35"}, [])
    assert response.status_code == 201
    assert response.json()["version"] == 2


def test_list_types_shows_drafts_in_the_version_list(client: Any, login_as: Any) -> None:
    """Entwürfe stehen nur in der Versionsliste; `current_version` kennt nur Veröffentlichtes."""
    login_as("catalog_admin")
    _upload(client, "ligne", LIGNE_KENNWERTE, [])
    _upload(client, "ligne", {**LIGNE_KENNWERTE, "neigung_deg": "35"}, [])
    entry = next(t for t in client.get("/api/v1/admin/catalog/types").json() if t["slug"] == "ligne")
    assert entry["current_version"] is None
    assert [(v["version"], v["status"]) for v in entry["versions"]] == [(2, "draft"), (1, "draft")]


def test_publish_is_blocked_while_a_consistency_error_remains(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    _upload(client, "ligne", LIGNE_KENNWERTE, [])
    response = client.post("/api/v1/admin/catalog/types/ligne/versions/1/publish")
    assert response.status_code == 409
    assert response.json()["code"] == "publish_blocked"


def test_publish_succeeds_without_findings_and_then_locks_the_version(
    client: Any, login_as: Any, db_session: Any
) -> None:
    login_as("catalog_admin")
    consistent = {**LIGNE_KENNWERTE, "neigung_deg": "35.0"}
    _upload(client, "ligne", consistent, [])
    publish = client.post("/api/v1/admin/catalog/types/ligne/versions/1/publish")
    assert publish.status_code == 200
    assert publish.json()["status"] == "published"

    # Nach der Veröffentlichung blockt der Dienst weitere Änderungen …
    roles = client.put(
        "/api/v1/admin/catalog/types/ligne/versions/1/facade-roles", json={"roles": {"0": "street"}}
    )
    assert roles.status_code == 409
    assert roles.json()["code"] == "version_published"

    # … und der Datenbank-Trigger blockt sie unabhängig vom Dienst (L4).
    with pytest.raises(DBAPIError):
        db_session.execute(text("UPDATE building_type_version SET name = 'geändert' WHERE version = 1"))
        db_session.flush()
    db_session.rollback()


def test_lines_and_options_list_drafts_and_published_versions(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    line = {"label_de": "Confort", "label_fr": "Confort"}
    client.post("/api/v1/admin/catalog/lines/confort/versions", json=line)
    client.post("/api/v1/admin/catalog/options/pv/versions", json={**line, "excludes_slugs": []})
    lines = client.get("/api/v1/admin/catalog/lines").json()
    options = client.get("/api/v1/admin/catalog/options").json()
    assert [(row["slug"], row["version"], row["status"]) for row in lines] == [("confort", 1, "draft")]
    assert [(row["slug"], row["version"], row["status"]) for row in options] == [("pv", 1, "draft")]

    client.post("/api/v1/admin/catalog/lines/confort/versions/1/publish")
    client.post("/api/v1/admin/catalog/lines/confort/versions", json=line)
    lines = client.get("/api/v1/admin/catalog/lines").json()
    assert [(row["version"], row["status"]) for row in lines] == [(2, "draft"), (1, "published")]


def test_line_lists_the_options_it_includes_and_rejects_unknown_ones(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    label = {"label_de": "Signature", "label_fr": "Signature"}
    client.post("/api/v1/admin/catalog/options/pv/versions", json={**label, "excludes_slugs": []})

    unknown = client.post(
        "/api/v1/admin/catalog/lines/signature/versions",
        json={**label, "included_option_slugs": ["gibt_es_nicht"]},
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "catalog_reference_unknown"

    created = client.post(
        "/api/v1/admin/catalog/lines/signature/versions", json={**label, "included_option_slugs": ["pv"]}
    )
    assert created.status_code == 201
    assert created.json()["included_option_slugs"] == ["pv"]
    listed = client.get("/api/v1/admin/catalog/lines").json()
    assert listed[0]["included_option_slugs"] == ["pv"]


def test_facade_roles_rejects_an_edge_index_outside_the_outline(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    _upload(client, "ligne", LIGNE_KENNWERTE, [])
    response = client.put(
        "/api/v1/admin/catalog/types/ligne/versions/1/facade-roles", json={"roles": {"9": "street"}}
    )
    assert response.status_code == 422


def test_import_with_unknown_price_reference_is_rejected(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    response = _upload(client, "ligne", LIGNE_KENNWERTE, [("linie", "confort", "34000")])
    assert response.status_code == 422
    assert response.json()["code"] == "catalog_reference_unknown"


def test_prices_from_the_import_land_in_the_draft_price_catalog(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    client.post(
        "/api/v1/admin/catalog/lines/confort/versions", json={"label_de": "Confort", "label_fr": "Confort"}
    )
    client.post(
        "/api/v1/admin/catalog/options/pv/versions",
        json={"label_de": "Photovoltaik", "label_fr": "Photovoltaïque"},
    )

    response = _upload(
        client, "ligne", LIGNE_KENNWERTE, [("linie", "confort", "34000"), ("option", "pv", "11200")]
    )
    assert response.status_code == 201

    draft = client.get("/api/v1/admin/catalog/price-catalog/draft")
    assert draft.status_code == 200
    body = draft.json()
    assert body["status"] == "draft"
    assert any(
        p["package_slug"] == "confort" and p["surcharge_cents"] == 3_400_000 for p in body["package_prices"]
    )
    assert any(m["module_slug"] == "pv" and m["surcharge_cents"] == 1_120_000 for m in body["module_prices"])
    assert any(b["building_type_slug"] == "ligne" for b in body["base_prices"])


def test_energy_assessment_appears_in_the_price_catalog(client: Any, login_as: Any) -> None:
    login_as("catalog_admin")
    client.post("/api/v1/admin/catalog/lines/base/versions", json={"label_de": "Base", "label_fr": "Base"})
    _upload(client, "ligne", LIGNE_KENNWERTE, [])
    response = client.put(
        "/api/v1/admin/catalog/types/ligne/energy-assessment/base",
        json={
            "climate_zone": "H2b",
            "verdict": "Verfehlt den Bbio-Schwellenwert knapp",
            "compliant": False,
            "compliance_surcharge_cents": 950_000,
            "measures": "verstärkte Dämmung und kontrollierte Lüftung",
        },
    )
    assert response.status_code == 200
    draft = client.get("/api/v1/admin/catalog/price-catalog/draft").json()
    assert any(
        a["building_type_slug"] == "ligne" and a["package_slug"] == "base" and not a["compliant"]
        for a in draft["energy_assessments"]
    )
