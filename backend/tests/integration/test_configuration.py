"""Modul H2 gegen PostGIS: Zulässigkeit, Lage und Konfiguration des Testgrundstücks AD 65 (Zone Uh) und
eines frei gezeichneten Grundstücks (Weg E, D13).
"""

import uuid
from typing import Any

import pytest

from app.catalog import service as catalog_service
from app.catalog.schemas import FacadeRolesIn
from app.platform.models import FeatureFlag
from tests.integration import test_envelope as _envelope
from tests.integration.test_catalog import LIGNE_KENNWERTE, ROOMS, _dxf, _xlsx

# Fixtures des Baurahmen-Tests: Grundstück AD 65 mit ausgewerteter Zone Uh (pytest findet sie nach Namen)
memory_storage = _envelope.memory_storage
project = _envelope.project
sessions = _envelope.sessions
settings = _envelope.settings

ROLES = {"0": "garden", "1": "side_right", "2": "street", "3": "side_left"}
FLAT = {k: v for k, v in LIGNE_KENNWERTE.items() if k not in ("neigung_deg", "firstrichtung")}


def publish_type(
    db: Any,
    slug: str,
    *,
    facade: list[tuple[float, float]],
    projection: list[tuple[float, float]],
    kennwerte: dict[str, str],
    roles: dict[str, str] | None = ROLES,
) -> None:
    catalog_service.import_type_version(
        db, slug, _xlsx(kennwerte, ROOMS, []), _dxf(facade, projection), "test"
    )
    if roles:
        catalog_service.set_facade_roles(db, slug, 1, FacadeRolesIn(roles=roles), "test")  # type: ignore[arg-type]
    catalog_service.publish_type_version(db, slug, 1, "test")


def rect(width: float, depth: float, margin: float = 0.0) -> list[tuple[float, float]]:
    return [
        (-margin, -margin),
        (width + margin, -margin),
        (width + margin, depth + margin),
        (-margin, depth + margin),
    ]


@pytest.fixture
def catalog(db_session: Any) -> None:
    """`klein` 12 × 8 m (Satteldach 35°) und `gross` 30 × 20 m (Flachdach)."""
    klein = {**LIGNE_KENNWERTE, "name": "Klein", "neigung_deg": "35.0", "familie": "klein"}
    publish_type(db_session, "klein", facade=rect(12, 8), projection=rect(12, 8, 0.5), kennwerte=klein)
    gross = {**FLAT, "name": "Gross", "dachform": "flat", "firsthoehe_m": "6.8", "traufhoehe_m": "6.8"}
    publish_type(db_session, "gross", facade=rect(30, 20), projection=rect(30, 20, 0.5), kennwerte=gross)


@pytest.fixture
def configurator(db_session: Any) -> None:
    db_session.add(FeatureFlag(key="configurator", enabled_for_all=True))
    db_session.commit()


def url(project_id: str, path: str) -> str:
    return f"/api/v1/projects/{project_id}/{path}"


def types(client: Any, project_id: str) -> dict[str, Any]:
    response = client.get(url(project_id, "catalog/types"))
    assert response.status_code == 200, response.text
    return {t["slug"]: t for t in response.json()["types"]}


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------


def test_configurator_is_off_without_the_flag(client: Any, project: str, catalog: None) -> None:
    for path in ("catalog/types", "configuration"):
        response = client.get(url(project, path))
        assert response.status_code == 403 and response.json()["code"] == "feature_disabled"


def test_configuration_is_private_to_the_project(
    client: Any, app: Any, project: str, configurator: None
) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as stranger:
        assert stranger.get(url(project, "configuration")).status_code == 404
        assert stranger.get(url(project, "catalog/types")).status_code == 404


def test_office_reads_the_configuration_by_role(client: Any, project: str, login_as: Any) -> None:
    assert client.get(f"/api/v1/admin/projects/{project}/configuration").status_code in (401, 403)
    login_as("architect")
    body = client.get(f"/api/v1/admin/projects/{project}/configuration").json()
    assert body["revision"] == 0 and body["type"] is None and body["simulation"] is True


# ---------------------------------------------------------------------------
# Zulässigkeit
# ---------------------------------------------------------------------------


def test_types_list_shows_admissibility_with_reasons(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    result = types(client, project)
    assert set(result) == {"klein", "gross"}
    klein, gross = result["klein"], result["gross"]
    assert klein["allowed"] is True and klein["reasons"] == [] and klein["rotations"]
    assert klein["facts"]["footprint_m2"] == pytest.approx(96.0)
    assert klein["facts"]["width_m"] == pytest.approx(12.0)
    assert gross["allowed"] is False
    assert {"footprint", "no_valid_position"} & {r["code"] for r in gross["reasons"]}
    assert all(r["binding"] and r["status"] == "fail" for r in gross["reasons"])


def test_only_published_types_are_listed(
    client: Any, project: str, catalog: None, configurator: None, db_session: Any
) -> None:
    draft = {**LIGNE_KENNWERTE, "name": "Entwurf", "neigung_deg": "35.0"}
    catalog_service.import_type_version(
        db_session, "entwurf", _xlsx(draft, ROOMS, []), _dxf(rect(12, 8), rect(12, 8)), "test"
    )
    assert "entwurf" not in types(client, project)


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------


def patch(client: Any, project: str, body: dict[str, Any], revision: int | None = None) -> Any:
    headers = {"If-Match": str(revision)} if revision is not None else {}
    return client.patch(url(project, "configuration"), json=body, headers=headers)


def test_selecting_a_type_places_the_house_and_checks_it(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    empty = client.get(url(project, "configuration")).json()
    assert empty["revision"] == 0 and empty["type"] is None and empty["placement"] is None

    response = patch(client, project, {"type_slug": "klein"}, revision=0)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1 and body["type"]["slug"] == "klein" and body["type"]["version"] == 1
    assert body["placement"] is not None and body["evaluation"]["valid"] is True
    assert body["rotations"] and body["fit"]["allowed"] is True
    assert {e["kind"] for e in body["evaluation"]["edges"]} >= {"street"}
    assert body["evaluation"]["projection_local"] and body["evaluation"]["facade_local"]
    assert all(not c["binding"] or c["status"] != "fail" for c in body["evaluation"]["checks"])


def test_blocked_type_is_rejected_with_all_reasons(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    response = patch(client, project, {"type_slug": "gross"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "type_blocked" and body["reasons"]
    assert client.get(url(project, "configuration")).json()["revision"] == 0


def test_unknown_type_is_not_found(client: Any, project: str, catalog: None, configurator: None) -> None:
    response = patch(client, project, {"type_slug": "gibtsnicht"})
    assert response.status_code == 404 and response.json()["code"] == "type_not_found"


def test_stale_revision_is_a_conflict(client: Any, project: str, catalog: None, configurator: None) -> None:
    assert patch(client, project, {"type_slug": "klein"}, revision=0).status_code == 200
    stale = patch(client, project, {"boundary_options": {}}, revision=0)
    assert stale.status_code == 409
    assert stale.json()["code"] == "revision_conflict" and stale.json()["current_revision"] == 1
    assert patch(client, project, {"boundary_options": {}}, revision=1).status_code == 200


def test_placement_outside_the_site_is_a_violation_and_not_saved(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    saved = patch(client, project, {"type_slug": "klein"}).json()
    rotation = saved["placement"]["rotation_deg"]
    far = {"placement": {"origin": {"e": 500.0, "n": 500.0}, "rotation_deg": rotation}}
    response = patch(client, project, far, revision=saved["revision"])
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "placement_violation"
    assert "outside_site" in [c["code"] for c in body["checks"] if c["status"] == "fail"]
    after = client.get(url(project, "configuration")).json()
    assert after["placement"] == saved["placement"] and after["revision"] == saved["revision"]


def test_rotation_must_be_one_of_the_offered_ones(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    saved = patch(client, project, {"type_slug": "klein"}).json()
    body = {"placement": {"origin": saved["placement"]["origin"], "rotation_deg": 45.0}}
    response = patch(client, project, body)
    assert response.status_code == 422
    assert response.json()["code"] == "rotation_not_allowed" and response.json()["allowed"]


def test_valid_move_is_saved_and_exact_placement_round_trips(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    saved = patch(client, project, {"type_slug": "klein"}).json()
    area = client.get(url(project, "configuration/placement-area")).json()
    rotation = saved["placement"]["rotation_deg"]
    entry = next(r for r in area["rotations"] if r["rotation_deg"] == rotation)
    assert entry["area_m2"] > 0 and entry["rings_local"]
    ring = entry["rings_local"][0]
    inside = [sum(p[0] for p in ring[:-1]) / (len(ring) - 1), sum(p[1] for p in ring[:-1]) / (len(ring) - 1)]
    body = {"placement": {"origin": {"e": inside[0], "n": inside[1]}, "rotation_deg": rotation}}
    response = patch(client, project, body, revision=saved["revision"])
    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["placement"]["origin"]["e"] == pytest.approx(inside[0], abs=0.001)
    assert moved["evaluation"]["valid"] is True and moved["revision"] == saved["revision"] + 1


def test_placement_area_and_presets_need_a_type(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    assert client.get(url(project, "configuration/placement-area")).status_code == 409
    response = client.post(url(project, "configuration/placement-presets") + "?type=klein")
    assert response.status_code == 200
    presets = response.json()["presets"]
    assert set(presets) == {"street_near", "set_back", "garden_max"}
    assert all(p is not None for p in presets.values())
    area = client.get(url(project, "configuration/placement-area") + "?type=klein").json()
    assert area["type_slug"] == "klein" and any(r["area_m2"] > 0 for r in area["rotations"])


def test_presets_are_valid_placements(client: Any, project: str, catalog: None, configurator: None) -> None:
    presets = client.post(url(project, "configuration/placement-presets") + "?type=klein").json()["presets"]
    revision = 0
    for name in ("street_near", "set_back", "garden_max"):
        body = {"type_slug": "klein", "placement": presets[name]}
        response = patch(client, project, body, revision=revision)
        assert response.status_code == 200, (name, response.text)
        assert response.json()["evaluation"]["valid"] is True
        revision = response.json()["revision"]


def test_type_change_drops_the_old_placement(
    client: Any, project: str, catalog: None, configurator: None, db_session: Any
) -> None:
    saved = patch(client, project, {"type_slug": "klein"}).json()
    assert saved["placement"] is not None
    cleared = patch(client, project, {"type_slug": None}).json()
    assert cleared["type"] is None and cleared["placement"] is None and cleared["evaluation"] is None
    assert (
        patch(client, project, {"placement": {"origin": {"e": 0, "n": 0}, "rotation_deg": 0}}).status_code
        == 409
    )


def test_boundary_option_is_limited_to_edges_that_allow_it(
    client: Any, project: str, catalog: None, configurator: None
) -> None:
    saved = patch(client, project, {"type_slug": "klein"}).json()
    edges = {e["seq"]: e for e in saved["evaluation"]["edges"]}
    allowed = [seq for seq, e in edges.items() if e["on_boundary_allowed"]]
    forbidden = [seq for seq, e in edges.items() if not e["on_boundary_allowed"]]
    assert allowed, "Zone Uh erlaubt Bauen auf der Grenze (seitlich und hinten)"
    street = next(seq for seq, e in edges.items() if e["kind"] == "street")
    assert street in forbidden
    response = patch(client, project, {"boundary_options": {street: True}})
    assert response.status_code == 422 and response.json()["code"] == "boundary_not_allowed"
    ok = patch(client, project, {"boundary_options": {allowed[0]: True}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["boundary_options"] == {str(allowed[0]): True}


def test_saved_configuration_is_checked_again_with_the_site(
    client: Any, project: str, catalog: None, configurator: None, db_session: Any
) -> None:
    """Regeln und Grundstück ändern sich nach dem Speichern: die Prüfung entsteht bei jedem Abruf neu."""

    from app.rules import overrides as rules_overrides
    from app.rules.schemas import ProjectOverrideIn

    saved = patch(client, project, {"type_slug": "klein"}).json()
    assert saved["evaluation"]["valid"] is True
    rules_overrides.set_override(
        db_session,
        uuid.UUID(project),
        ProjectOverrideIn(
            zone_code="Uh",
            kind="max_footprint_ratio",
            status="effective",
            params={"ratio": 0.001},
            note="Regeln des Lotissement",
        ),
        "tester",
    )
    db_session.commit()
    again = client.get(url(project, "configuration")).json()
    assert again["type"]["slug"] == "klein" and again["placement"] == saved["placement"]
    assert again["fit"]["allowed"] is False
    assert again["evaluation"]["valid"] is False
    assert [c["code"] for c in again["evaluation"]["checks"] if c["status"] == "fail"] == ["footprint"]


# ---------------------------------------------------------------------------
# Weg E: freies Zeichnen (D13)
# ---------------------------------------------------------------------------

SKETCH = {
    "edges": [
        {"length_m": 10, "angle_deg": 90},
        {"length_m": 20, "angle_deg": 180},
        {"length_m": 10, "angle_deg": 270},
    ],
    "address_label": "12 rue imaginaire",
}


@pytest.fixture
def sketch(client: Any, db_session: Any, catalog: None, configurator: None) -> str:
    db_session.add(FeatureFlag(key="site_selection", enabled_for_all=True))
    db_session.commit()
    project_id = str(client.post("/api/v1/projects").json()["id"])
    assert client.put(url(project_id, "site"), json=SKETCH).status_code == 200
    return project_id


def test_manual_sketch_has_free_placement_inside_the_outline(client: Any, sketch: str) -> None:
    listing = client.get(url(sketch, "catalog/types")).json()
    assert listing["mode"] == "free" and listing["free_reason"] == "manual_sketch"
    assert "notice.manual_sketch" in listing["notices"]
    by_slug = {t["slug"]: t for t in listing["types"]}
    assert by_slug["klein"]["allowed"] is True  # 12 × 8 m passt gedreht in 10 × 20 m
    assert by_slug["gross"]["allowed"] is False
    assert [r["code"] for r in by_slug["gross"]["reasons"]] == ["no_valid_position"]

    saved = patch(client, sketch, {"type_slug": "klein"})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["mode"] == "free" and body["evaluation"]["valid"] is True
    assert body["evaluation"]["edges"] == []  # keine Abstandsprüfung
    outside = {
        "placement": {"origin": {"e": 100.0, "n": 100.0}, "rotation_deg": body["placement"]["rotation_deg"]}
    }
    response = patch(client, sketch, outside)
    assert response.status_code == 422
    assert [c["code"] for c in response.json()["checks"] if c["status"] == "fail"] == ["outside_outline"]


def test_a_type_that_does_not_fit_the_sketch_is_blocked(client: Any, sketch: str) -> None:
    response = patch(client, sketch, {"type_slug": "gross"})
    assert response.status_code == 422 and response.json()["code"] == "type_blocked"
