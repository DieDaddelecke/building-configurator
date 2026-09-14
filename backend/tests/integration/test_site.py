"""Modul G1 gegen PostGIS mit echten Katasterdaten aus Treillières (Ausschnitt um 8 rue des Chênes).

Erwartungen an den Kantenarten sind am Lageplan der Fixture geprüft (Lotissement mit Straßenparzelle AD0071).
"""

import gzip
import json
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.platform.jobs.worker import run_one
from app.platform.models import AuditLog, FeatureFlag, Job, Project
from app.site import jobs as site_jobs
from app.site.cadastre_import import import_commune
from app.site.models import RefImport, RefParcel, Site, SiteEdge, SiteRisk, Terrain

FIXTURES = Path(__file__).parents[1] / "fixtures" / "site"
RELEASE = "2026-06-01"
ADDRESS = {"lon": -1.596965, "lat": 47.281826}  # 8 Rue des chênes, 44119 Treillières
CORNER = "44209000AD0042"  # Kreuzung: Straßen W, S, O; Nachbar AD0043 im NO
REGULAR = "44209000AD0065"  # Straße im NNO, Nachbarn seitlich, hinten AD0072/AD0062
FAR = "44209000AD0054"


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def imported(db_session: Any) -> Any:
    result = import_commune(
        db_session,
        DirectoryCadastre(FIXTURES, RELEASE),
        get_settings(),
        "44209",
        roads=DirectoryRoads(FIXTURES),
    )
    assert result.status == "succeeded", result
    return result


@pytest.fixture
def enabled(db_session: Any) -> None:
    db_session.add(FeatureFlag(key="site_selection", enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def project(client: Any, imported: Any, enabled: None) -> str:
    return str(client.post("/api/v1/projects").json()["id"])


def edge_facing(body: dict[str, Any], azimuth: float) -> dict[str, Any]:
    return min(
        (e for e in body["edges"] if e["ring"] == 0),
        key=lambda e: abs((e["normal_azimuth_deg"] - azimuth + 180) % 360 - 180),
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_counts_idempotency_and_force(db_session: Any, imported: Any) -> None:
    assert imported.counts["parcels"] == 103
    assert imported.counts["buildings"] == 128
    assert imported.counts["roads"] > 50
    source = DirectoryCadastre(FIXTURES, RELEASE)
    roads = DirectoryRoads(FIXTURES)
    assert import_commune(db_session, source, get_settings(), "44209", roads=roads).status == "skipped"
    assert (
        import_commune(db_session, source, get_settings(), "44209", roads=roads, force=True).status
        == "succeeded"
    )
    assert db_session.execute(select(func.count()).select_from(RefParcel)).scalar_one() == 103
    record = db_session.execute(select(RefImport).order_by(RefImport.created_at.desc())).scalars().first()
    assert set(record.sha256) == {"parcelles", "batiments", "communes"}


def _write_subset(directory: Path, keep: int) -> None:
    for dataset in ("parcelles", "batiments", "communes"):
        data = json.loads(gzip.decompress((FIXTURES / f"cadastre-44209-{dataset}.json.gz").read_bytes()))
        if dataset == "parcelles":
            data["features"] = data["features"][:keep]
        (directory / f"cadastre-44209-{dataset}.json.gz").write_bytes(
            gzip.compress(json.dumps(data).encode())
        )


def test_implausible_count_change_keeps_previous_data(db_session: Any, imported: Any, tmp_path: Path) -> None:
    _write_subset(tmp_path, keep=10)
    result = import_commune(db_session, DirectoryCadastre(tmp_path, "2026-09-01"), get_settings(), "44209")
    assert result.status == "failed"
    assert result.error is not None and result.error.startswith("parcel_count_change:103->10")
    assert db_session.execute(select(func.count()).select_from(RefParcel)).scalar_one() == 103
    staging = db_session.execute(text("SELECT count(*) FROM ref_parcel_staging")).scalar_one()
    assert staging == 0


def test_missing_roads_do_not_block_import_and_are_retried(db_session: Any, tmp_path: Path) -> None:
    source = DirectoryCadastre(FIXTURES, RELEASE)
    first = import_commune(db_session, source, get_settings(), "44209", roads=DirectoryRoads(tmp_path))
    assert first.status == "succeeded" and first.counts["roads"] == -1
    second = import_commune(db_session, source, get_settings(), "44209", roads=DirectoryRoads(FIXTURES))
    assert second.status == "succeeded" and second.counts["roads"] > 0


# ---------------------------------------------------------------------------
# Öffentliche Endpunkte
# ---------------------------------------------------------------------------


def test_customer_endpoints_require_feature_flag(client: Any, imported: Any) -> None:
    response = client.get("/api/v1/cadastre/service-area")
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


def test_service_area_and_parcels_in_bbox(client: Any, imported: Any, enabled: None) -> None:
    area = client.get("/api/v1/cadastre/service-area").json()
    assert [c["insee"] for c in area] == ["44209"]
    x0, y0, x1, y1 = area[0]["bbox"]
    assert x0 < ADDRESS["lon"] < x1 and y0 < ADDRESS["lat"] < y1

    bbox = "-1.5985,47.2808,-1.5955,47.2828"
    parcels = client.get("/api/v1/cadastre/parcels", params={"bbox": bbox}).json()
    ids = {f["id"] for f in parcels["features"]}
    assert {CORNER, REGULAR} <= ids
    assert parcels["truncated"] is False
    assert parcels["features"][0]["geometry"]["type"] in ("Polygon", "MultiPolygon")

    too_large = client.get("/api/v1/cadastre/parcels", params={"bbox": "-1.7,47.2,-1.5,47.4"})
    assert too_large.status_code == 422 and too_large.json()["code"] == "bbox_too_large"


def test_lookup_by_point_reference_and_outside_area(client: Any, project: str) -> None:
    url = f"/api/v1/projects/{project}/parcels/lookup"
    found = client.post(url, json=ADDRESS).json()
    assert found["in_service_area"] and found["contained_idu"] == CORNER
    assert all(c["distance_m"] <= 20 for c in found["candidates"])

    by_number = client.post(url, json={"commune_insee": "44209", "section": "AD", "number": "65"}).json()
    assert [c["idu"] for c in by_number["candidates"]] == [REGULAR]

    paris = client.post(url, json={"lon": 2.3522, "lat": 48.8566}).json()
    assert paris == {"in_service_area": False, "contained_idu": None, "candidates": []}

    assert client.post(url, json={"lon": 2.35}).status_code == 422


def test_geocode_uses_cache_and_marks_service_area(
    client: Any, app: Any, imported: Any, enabled: None
) -> None:
    from app.integrations.http import new_client, shared_client

    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(str(request.url))
        return httpx2.Response(200, json=fixture_json("geocode_search.json"))

    app.dependency_overrides[shared_client] = lambda: new_client(
        get_settings(), httpx2.MockTransport(handler)
    )
    first = client.get("/api/v1/geocode", params={"q": "8 rue des Chênes Treillières"})
    second = client.get("/api/v1/geocode", params={"q": "8  RUE des chênes treillières"})
    assert first.status_code == 200 and second.json() == first.json()
    assert len(calls) == 1
    assert first.json()[0]["in_service_area"] is True


def test_geocode_failure_is_explicit(client: Any, app: Any, imported: Any, enabled: None) -> None:
    from app.integrations.http import new_client, shared_client

    app.dependency_overrides[shared_client] = lambda: new_client(
        get_settings(), httpx2.MockTransport(lambda request: httpx2.Response(502))
    )
    response = client.get("/api/v1/geocode", params={"q": "rue introuvable"})
    assert response.status_code == 503 and response.json()["code"] == "geocoding_unavailable"


# ---------------------------------------------------------------------------
# Grundstück
# ---------------------------------------------------------------------------


def test_regular_lot_street_sides_and_rear(client: Any, project: str, db_session: Any) -> None:
    response = client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["revision"] == 1 and body["binding"] and body["warnings"] == []
    assert edge_facing(body, 30)["kind"] == "street"
    assert edge_facing(body, 30)["street_name"] == "Rue des chênes"
    assert edge_facing(body, 120)["kind"] == "side"
    assert edge_facing(body, 300)["kind"] == "side"
    assert edge_facing(body, 210)["kind"] == "rear"
    assert body["street_azimuth_deg"] == pytest.approx(29.6, abs=1)
    assert body["garden_azimuth_deg"] == pytest.approx(209.6, abs=1)
    assert body["area_official_m2"] == 927
    assert abs(body["area_m2"] - 927) < 0.03 * 927
    assert body["notices"] == ["notice.cadastre_accuracy"]
    assert body["terrain"]["status"] == "pending" and body["risks"]["status"] == "pending"
    assert body["context"]["parcels"] and body["context"]["buildings"]
    ring = body["outline_local"][0]
    assert min(p[0] for p in ring) >= 0 and min(p[1] for p in ring) >= 0
    assert body["parcels"][0]["accuracy_class"] == "cadastre_vector"

    jobs = db_session.execute(select(Job).where(Job.kind == "site_enrich")).scalars().all()
    assert len(jobs) == 1 and str(jobs[0].project_id) == project


def test_corner_lot_at_lotissement_crossing(client: Any, project: str) -> None:
    body = client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [CORNER]}).json()
    assert "corner_lot" in body["warnings"]
    assert edge_facing(body, 30)["kind"] == "side"
    assert {edge_facing(body, a)["kind"] for a in (300, 207, 119)} == {"street"}


def test_two_contiguous_parcels_form_one_site(client: Any, project: str) -> None:
    body = client.put(
        f"/api/v1/projects/{project}/site", json={"parcel_idus": [CORNER, "44209000AD0043"]}
    ).json()
    assert len(body["parcels"]) == 2
    assert body["area_official_m2"] == 928 + 991
    assert [e["kind"] for e in body["edges"]].count("street") == 4


def test_invalid_selections_are_rejected(client: Any, project: str) -> None:
    url = f"/api/v1/projects/{project}/site"
    apart = client.put(url, json={"parcel_idus": [CORNER, REGULAR]})
    assert apart.status_code == 422 and apart.json()["code"] == "site_not_contiguous"
    unknown = client.put(url, json={"parcel_idus": ["44209000ZZ9999"]})
    assert unknown.status_code == 422 and unknown.json()["missing"] == ["44209000ZZ9999"]
    malformed = client.put(url, json={"parcel_idus": ["AD0042"]})
    assert malformed.status_code == 422 and malformed.json()["code"] == "validation_error"
    assert client.get(url).json()["code"] == "site_not_found"


def test_same_selection_is_idempotent_and_new_selection_bumps_revision(client: Any, project: str) -> None:
    url = f"/api/v1/projects/{project}/site"
    first = client.put(url, json={"parcel_idus": [REGULAR]}).json()
    again = client.put(url, json={"parcel_idus": [REGULAR]}).json()
    assert again["revision"] == first["revision"] == 1
    other = client.put(url, json={"parcel_idus": [CORNER]}).json()
    assert other["revision"] == 2 and other["parcels"][0]["idu"] == CORNER


def test_site_is_private_to_project(client: Any, app: Any, project: str) -> None:
    from fastapi.testclient import TestClient

    client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    with TestClient(app) as stranger:
        assert stranger.get(f"/api/v1/projects/{project}/site").status_code == 404


# ---------------------------------------------------------------------------
# Kantenkorrektur
# ---------------------------------------------------------------------------


def test_customer_correction_needs_architect_confirmation(
    client: Any, project: str, login_as: Callable[..., Any], db_session: Any
) -> None:
    body = client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]}).json()
    rear = edge_facing(body, 210)
    url = f"/api/v1/projects/{project}/site/edges/{rear['seq']}"

    stale = client.patch(url, json={"kind": "street"}, headers={"If-Match": '"99"'})
    assert stale.status_code == 409 and stale.json()["code"] == "revision_conflict"

    corrected = client.patch(url, json={"kind": "street"}, headers={"If-Match": '"1"'}).json()
    edge = next(e for e in corrected["edges"] if e["seq"] == rear["seq"])
    assert (edge["kind"], edge["kind_auto"], edge["classification_source"]) == ("street", "rear", "customer")
    assert corrected["revision"] == 2 and corrected["binding"] is False
    assert "customer_corrections_unconfirmed" in corrected["warnings"]

    login_as("architect")
    queue = client.get("/api/v1/admin/sites/review").json()
    assert queue[0]["project_id"] == project and queue[0]["customer_corrections"] == 1
    confirmed = client.post(f"/api/v1/admin/projects/{project}/site/edges/confirm").json()
    assert confirmed["binding"] is True and confirmed["revision"] == 3
    edge = next(e for e in confirmed["edges"] if e["seq"] == rear["seq"])
    assert edge["classification_source"] == "architect" and edge["kind"] == "street"

    locked = client.patch(url, json={"kind": None})
    assert locked.status_code == 409 and locked.json()["code"] == "edge_confirmed_by_architect"

    actions = (
        db_session.execute(select(AuditLog.action).where(AuditLog.entity_type == "site")).scalars().all()
    )
    assert actions == ["site_edge.correct", "site_edge.confirm_customer"]


def test_architect_sets_any_kind_and_resets(client: Any, project: str, login_as: Callable[..., Any]) -> None:
    body = client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]}).json()
    side = edge_facing(body, 120)
    login_as("architect")
    url = f"/api/v1/admin/projects/{project}/site/edges/{side['seq']}"
    other = client.patch(url, json={"kind": "other"}).json()
    assert next(e for e in other["edges"] if e["seq"] == side["seq"])["kind"] == "other"
    reset = client.patch(url, json={"kind": None}).json()
    edge = next(e for e in reset["edges"] if e["seq"] == side["seq"])
    assert (edge["kind"], edge["classification_source"]) == ("side", "auto")


def test_staff_endpoints_require_roles(client: Any, project: str, login_as: Callable[..., Any]) -> None:
    assert client.get("/api/v1/admin/sites/review").status_code == 401
    login_as("ops")
    assert client.get("/api/v1/admin/sites/review").status_code == 403
    assert client.get("/api/v1/admin/cadastre/imports").status_code == 200


def test_ops_sees_imports_and_starts_import_job(
    client: Any, imported: Any, login_as: Callable[..., Any], db_session: Any
) -> None:
    login_as("ops")
    status = client.get("/api/v1/admin/cadastre/imports").json()
    assert status[0]["commune_insee"] == "44209" and status[0]["counts"]["parcels"] == 103
    started = client.post("/api/v1/admin/cadastre/imports", json={"force": False})
    assert started.status_code == 202
    job = db_session.get(Job, uuid.UUID(started.json()["job_id"]))
    assert job is not None and job.kind == "cadastre_import"


# ---------------------------------------------------------------------------
# Hintergrundjobs
# ---------------------------------------------------------------------------


@pytest.fixture
def external(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Aufgezeichnete Antworten von Höhendienst und Géorisques; `state["fail"]` simuliert Ausfälle."""
    state: dict[str, Any] = {"fail": False, "calls": []}

    def handler(request: httpx2.Request) -> httpx2.Response:
        state["calls"].append(request.url.path)
        if state["fail"]:
            return httpx2.Response(503)
        if "elevation" in request.url.path:
            count = len(request.url.params["lon"].split("|"))
            return httpx2.Response(200, json={"elevations": [{"z": 52.8 + 0.01 * i} for i in range(count)]})
        if request.url.path.endswith("/rga"):
            return httpx2.Response(200, json=fixture_json("georisques_rga.json"))
        return httpx2.Response(200, json=fixture_json("georisques_report.json"))

    monkeypatch.setattr(
        site_jobs, "client_factory", lambda: httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    yield state


def _run_enrich(db_session: Any) -> None:
    assert run_one("w1", ["default"]) is True
    db_session.expire_all()


def test_site_enrich_stores_terrain_and_risks(
    client: Any, project: str, db_session: Any, external: Any
) -> None:
    client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    _run_enrich(db_session)
    body = client.get(f"/api/v1/projects/{project}/site").json()
    assert body["terrain"]["status"] == "ok" and body["terrain"]["flat"] is True
    assert body["terrain"]["samples"] == 9
    assert body["risks"]["status"] == "ok"
    kinds = {r["kind"]: r for r in body["risks"]["items"]}
    assert kinds["clay_shrink_swell"]["level"] == "low" and kinds["clay_shrink_swell"]["scope"] == "address"
    assert "radon" in kinds
    assert "notice.risks_public_data" in body["notices"]


def test_site_enrich_marks_unavailable_after_last_attempt(
    client: Any, project: str, db_session: Any, external: Any
) -> None:
    external["fail"] = True
    client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    for _ in range(3):
        _run_enrich(db_session)
        db_session.execute(text("UPDATE job SET run_after = now() WHERE status = 'queued'"))
        db_session.commit()
    site = db_session.execute(select(Site)).scalar_one()
    assert (site.terrain_status, site.risks_status) == ("unavailable", "unavailable")
    assert db_session.execute(select(Job.status).where(Job.kind == "site_enrich")).scalar_one() == "succeeded"
    assert db_session.execute(select(func.count()).select_from(Terrain)).scalar_one() == 0


def test_site_enrich_skips_outdated_outline(
    client: Any, project: str, db_session: Any, external: Any
) -> None:
    url = f"/api/v1/projects/{project}/site"
    client.put(url, json={"parcel_idus": [REGULAR]})
    client.put(url, json={"parcel_idus": [CORNER]})
    _run_enrich(db_session)
    _run_enrich(db_session)
    site = db_session.execute(select(Site)).scalar_one()
    assert site.terrain_status == "ok"
    risks = db_session.execute(select(SiteRisk.site_id).distinct()).scalars().all()
    assert risks == [site.id]


def test_project_deletion_removes_site(client: Any, project: str, db_session: Any) -> None:
    client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    db_session.execute(text("DELETE FROM project WHERE id = :id"), {"id": project})
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(Site)).scalar_one() == 0
    assert db_session.execute(select(func.count()).select_from(SiteEdge)).scalar_one() == 0
    assert db_session.get(Project, uuid.UUID(project)) is None


def test_ops_retries_unavailable_enrichment(
    client: Any, project: str, db_session: Any, external: Any, login_as: Callable[..., Any]
) -> None:
    external["fail"] = True
    client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]})
    for _ in range(3):
        _run_enrich(db_session)
        db_session.execute(text("UPDATE job SET run_after = now() WHERE status = 'queued'"))
        db_session.commit()
    external["fail"] = False
    login_as("ops")
    assert client.post("/api/v1/admin/sites/enrich-retry").json() == {"sites": 1}
    _run_enrich(db_session)
    site = db_session.execute(select(Site)).scalar_one()
    assert (site.terrain_status, site.risks_status) == ("ok", "ok")


def test_review_queue_defaults_to_customer_corrections(
    client: Any, project: str, app: Any, login_as: Callable[..., Any]
) -> None:
    from fastapi.testclient import TestClient

    client.put(
        f"/api/v1/projects/{project}/site", json={"parcel_idus": [CORNER]}
    )  # Eckgrundstück, keine Korrektur
    login_as("architect")
    assert client.get("/api/v1/admin/sites/review").json() == []
    assert [i["project_id"] for i in client.get("/api/v1/admin/sites/review?scope=all").json()] == [project]
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/admin/sites/review").status_code == 401


def test_geocode_cache_is_cleaned(db_session: Any) -> None:
    from app.site.models import GeocodeCache

    db_session.add(GeocodeCache(key="alt", response=[]))
    db_session.add(GeocodeCache(key="neu", response=[]))
    db_session.commit()
    db_session.execute(
        text("UPDATE geocode_cache SET fetched_at = now() - interval '2 days' WHERE key = 'alt'")
    )
    from app.platform.jobs import enqueue

    enqueue(db_session, "site_housekeeping")
    db_session.commit()
    run_one("w1", ["default"])
    db_session.expire_all()
    assert set(db_session.execute(select(GeocodeCache.key)).scalars()) == {"neu"}
