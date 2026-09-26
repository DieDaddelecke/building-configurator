"""Modul G3 gegen PostGIS: Baurahmen des Testgrundstücks AD 65 (Zone Uh, PLUi Erdre et Gesvres) aus den
aufgezeichneten Antworten von GPU und Sprachmodell, Zugriff, Prüfsumme und Steckbrief.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.envelope import service as envelope_service
from app.envelope.models import EnvelopeSheet
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.platform.models import FeatureFlag, Job
from app.rules import extract
from app.rules import service as rules_service
from app.rules.models import LandUsePlan, RegulationChapter
from app.rules.plan_import import DirectoryGpu, import_commune
from app.rules.schemas import ProjectOverrideIn
from app.site import service as site_service
from app.site.cadastre_import import import_commune as import_cadastre
from app.site.models import Site, SiteEdge, Terrain
from tests.rules_support import DOC_ID, FakeExtractor, gpu_directory, uh_output

SITE_FIXTURES = Path(__file__).parents[1] / "fixtures" / "site"
REGULAR = "44209000AD0065"


@pytest.fixture(autouse=True)
def memory_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    objects: dict[str, bytes] = {}
    monkeypatch.setattr(
        storage, "put_bytes", lambda key, data, content_type="": objects.__setitem__(key, data)
    )
    monkeypatch.setattr(storage, "get_bytes", lambda key: objects[key])
    return objects


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("EMPRISE_OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@contextmanager
def sessions() -> Iterator[Any]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def project(client: Any, db_session: Any, tmp_path: Path, settings: Any) -> str:
    """Grundstück AD 65 mit importiertem Planwerk und ausgewerteter Zone Uh; alle Flags gesetzt."""
    assert (
        import_cadastre(
            db_session,
            DirectoryCadastre(SITE_FIXTURES, "2026-06-01"),
            settings,
            "44209",
            roads=DirectoryRoads(SITE_FIXTURES),
        ).status
        == "succeeded"
    )
    assert import_commune(db_session, DirectoryGpu(gpu_directory(tmp_path)), settings, "44209").status == (
        "imported"
    )
    for key in ("site_selection", "rules_simulation", "envelope_simulation"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()
    chapter = db_session.execute(
        select(RegulationChapter.id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(RegulationChapter.code == "Uh", LandUsePlan.gpu_doc_id == DOC_ID)
    ).scalar_one()
    outcome = extract.extract_chapter(sessions, settings, chapter, FakeExtractor([uh_output()]).factory())
    assert outcome.status == "succeeded", outcome
    db_session.expire_all()
    project_id = str(client.post("/api/v1/projects").json()["id"])
    assert (
        client.put(f"/api/v1/projects/{project_id}/site", json={"parcel_idus": [REGULAR]}).status_code == 200
    )
    return project_id


def get_envelope(client: Any, project: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects/{project}/envelope")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def limit(
    envelope: dict[str, Any], key: str, zone: str = "Uh", building_kind: str = "main"
) -> dict[str, Any]:
    """Grenzwert einer Zone; Regeln gibt es je Baukörper (Hauptgebäude, Nebengebäude)."""
    part = next(p for p in envelope["parts"] if p["zone_code"] == zone)
    return next(
        item
        for item in part["limits"]
        if item["key"] == key and item["building_kind"] in (building_kind, "any")
    )


# ---------------------------------------------------------------------------
# Baurahmen des echten Testgrundstücks
# ---------------------------------------------------------------------------


def test_envelope_of_the_real_site(client: Any, project: str, db_session: Any) -> None:
    """Zone Uh: Bauband 5–20 m, seitlich auf der Grenze oder 3 m, Grundfläche 25 %, Traufe 7 m."""
    envelope = get_envelope(client, project)
    assert envelope["simulation"] is True
    assert envelope["status"] in ("ok", "partial")
    assert envelope["engine_version"].startswith("g3-")
    assert envelope["input_hash"].startswith("sha256:")
    assert envelope["parcels"] == [REGULAR]

    part = next(p for p in envelope["parts"] if p["zone_code"] == "Uh")
    assert part["excluded"] is None
    footprint = limit(envelope, "footprint_max_m2")
    assert footprint["value"] == pytest.approx(0.25 * part["area_m2"], abs=0.5)
    assert limit(envelope, "max_height")["params"]["eave_m"] == 7.0
    assert limit(envelope, "setback_street")["params"]["band"] == "building"

    lenient = envelope["contours"]["lenient"]
    strict = envelope["contours"]["strict"]
    assert 0 < strict["area_m2"] <= lenient["area_m2"] < envelope["area_m2"]
    assert lenient["geojson"]["type"] in ("Polygon", "MultiPolygon")
    assert envelope["bands"] and envelope["bands"][0]["band"] == "building"

    street = next(e for e in envelope["edges"] if e["kind"] == "street")
    assert street["lenient_m"] == pytest.approx(5.0)
    side = next(e for e in envelope["edges"] if e["kind"] in ("side", "rear"))
    assert side["lenient_m"] == 0.0  # auf der Grenze zulässig
    assert side["strict_m"] == pytest.approx(3.0)
    assert any(s["citation"]["quote_verified"] for s in street["setbacks"])
    assert "notice.envelope_simulation" in envelope["notices"]


def test_envelope_uses_the_same_zones_as_the_rules_view(client: Any, project: str) -> None:
    """Anzeige und Baurahmen dürfen nie verschiedene Zonen oder Planstände zeigen (Plan G3 4.2)."""
    rules = client.get(f"/api/v1/projects/{project}/rules").json()
    envelope = get_envelope(client, project)
    assert [z["code"] for z in rules["zones"]] == [p["zone_code"] for p in envelope["parts"]]
    assert envelope["provenance"]["plan_id"] == rules["plan"]["id"]


def test_sum_of_part_areas_matches_the_site(client: Any, project: str) -> None:
    envelope = get_envelope(client, project)
    total = sum(p["area_m2"] for p in envelope["parts"])
    assert total == pytest.approx(envelope["area_m2"], rel=0.02)


# ---------------------------------------------------------------------------
# Prüfsumme über den Inhalt
# ---------------------------------------------------------------------------


def test_hash_changes_when_terrain_arrives(client: Any, project: str, db_session: Any) -> None:
    """Gelände trifft ohne neue Revision ein; ein Zwischenspeicher nach Nummern wäre veraltet."""
    before = get_envelope(client, project)
    site = db_session.execute(select(Site)).scalar_one()
    db_session.add(
        Terrain(
            site_id=site.id,
            method="ign_altimetry",
            reference_altitude_ngf=30.0,
            slope_percent=9.0,
            samples=[[0.0, 0.0, 30.0]],
            outline_hash=site.outline_hash,
        )
    )
    site.terrain_status = "ok"
    db_session.commit()
    after = get_envelope(client, project)
    assert after["input_hash"] != before["input_hash"]
    assert after["provenance"]["terrain_status"] == "ok"
    assert "terrain_steep" in after["warnings"]
    assert before["provenance"]["site_revision"] == after["provenance"]["site_revision"]


def test_hash_changes_with_a_project_correction(client: Any, project: str, db_session: Any) -> None:
    before = get_envelope(client, project)
    rules_service.set_override(
        db_session,
        uuid.UUID(project),
        ProjectOverrideIn(
            zone_code="Uh",
            kind="setback_street",
            status="effective",
            params={"mode": "min", "min_m": 8.0},
            note="Regeln des Lotissement",
        ),
        "tester",
    )
    db_session.commit()
    after = get_envelope(client, project)
    assert after["input_hash"] != before["input_hash"]
    assert after["provenance"]["project_overrides"] == 1
    street = next(e for e in after["edges"] if e["kind"] == "street")
    assert street["lenient_m"] == pytest.approx(8.0)
    assert street["setbacks"][0]["citation"]["origin"] == "project"
    # Die Korrektur ersetzt die Regel der Art vollständig (RW27): ohne Bauband wird die Fläche größer
    assert after["bands"] == []
    assert after["contours"]["lenient"]["area_m2"] > before["contours"]["lenient"]["area_m2"]


def test_hash_changes_with_an_edge_correction(client: Any, project: str, db_session: Any) -> None:
    before = get_envelope(client, project)
    seq = (
        db_session.execute(select(SiteEdge.seq).where(SiteEdge.kind == "side").order_by(SiteEdge.seq))
        .scalars()
        .first()
    )
    assert seq is not None
    response = client.patch(f"/api/v1/projects/{project}/site/edges/{seq}", json={"kind": "street"})
    assert response.status_code == 200, response.text
    after = get_envelope(client, project)
    assert after["input_hash"] != before["input_hash"]
    assert "customer_edges_unconfirmed" in after["warnings"]
    corrected = next(e for e in after["edges"] if e["seq"] == seq)
    assert "customer_correction" in corrected["markers"]


# ---------------------------------------------------------------------------
# Zustände ohne vollständige Regeln
# ---------------------------------------------------------------------------


def test_envelope_without_rules_is_unavailable(client: Any, db_session: Any, settings: Any) -> None:
    """Ohne Planwerk (kein Import) gibt es keinen Baurahmen, aber auch keinen Fehler."""
    import_cadastre(
        db_session,
        DirectoryCadastre(SITE_FIXTURES, "2026-06-01"),
        settings,
        "44209",
        roads=DirectoryRoads(SITE_FIXTURES),
    )
    for key in ("site_selection", "rules_simulation", "envelope_simulation"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()
    project_id = client.post("/api/v1/projects").json()["id"]
    client.put(f"/api/v1/projects/{project_id}/site", json={"parcel_idus": [REGULAR]})
    envelope = get_envelope(client, project_id)
    assert envelope["status"] == "unavailable"
    assert envelope["contours"]["lenient"]["area_m2"] == 0.0
    assert envelope["parts"] == []


def test_envelope_without_site_is_not_found(client: Any, db_session: Any) -> None:
    db_session.add(FeatureFlag(key="envelope_simulation", enabled_for_all=True))
    db_session.commit()
    project_id = client.post("/api/v1/projects").json()["id"]
    response = client.get(f"/api/v1/projects/{project_id}/envelope")
    assert response.status_code == 404
    assert response.json()["code"] == "site_not_found"


# ---------------------------------------------------------------------------
# Weg E: freies Zeichnen ohne Kataster (Plan 3.3, D13)
# ---------------------------------------------------------------------------

MANUAL_EDGES = [
    {"length_m": 10, "angle_deg": 90},
    {"length_m": 20, "angle_deg": 180},
    {"length_m": 10, "angle_deg": 270},
]


@pytest.fixture
def manual_project(client: Any, db_session: Any) -> str:
    """Grundstück ohne Kataster, keine Zonen oder Regeln nötig: G2 wird für Weg E nicht aufgerufen."""
    for key in ("site_selection", "envelope_simulation"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()
    project_id = str(client.post("/api/v1/projects").json()["id"])
    body = {"edges": MANUAL_EDGES, "address_label": "12 rue imaginaire"}
    formed = client.put(f"/api/v1/projects/{project_id}/site", json=body)
    assert formed.status_code == 200, formed.json()
    return project_id


def test_manual_envelope_unavailable_without_rules(client: Any, manual_project: str) -> None:
    """G2 wird nicht aufgerufen (kein Planwerk, kein Regelwerk importiert): trotzdem eine Antwort, kein
    Fehler – der gezeichnete Umriss bleibt sichtbar, nur ohne Baurahmen (Plan 3.3, D13)."""
    response = client.get(f"/api/v1/projects/{manual_project}/envelope")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "unavailable" and body["reason"] == "manual_sketch"
    assert body["notices"] == ["notice.manual_sketch"]
    assert body["parts"] == [] and body["contours"] == {}
    assert body["area_m2"] == pytest.approx(200.0)


def test_manual_sketch_has_no_sheet(client: Any, manual_project: str) -> None:
    """Kein Steckbrief für Weg E: ohne Baurahmen keine Simulation, die er zusammenfassen könnte."""
    create = client.post(f"/api/v1/projects/{manual_project}/envelope/sheet")
    assert create.status_code == 409 and create.json()["code"] == "sheet_unavailable_manual_sketch"
    download = client.get(f"/api/v1/projects/{manual_project}/envelope/sheet")
    assert download.status_code == 409 and download.json()["code"] == "sheet_unavailable_manual_sketch"


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------


def test_feature_flag_and_project_access(client: Any, project: str, db_session: Any) -> None:
    db_session.execute(
        text("UPDATE feature_flag SET enabled_for_all = false WHERE key = 'envelope_simulation'")
    )
    db_session.commit()
    assert client.get(f"/api/v1/projects/{project}/envelope").status_code == 403
    db_session.execute(
        text("UPDATE feature_flag SET enabled_for_all = true WHERE key = 'envelope_simulation'")
    )
    db_session.commit()
    assert client.get(f"/api/v1/projects/{project}/envelope").status_code == 200
    other = uuid.uuid4()
    assert client.get(f"/api/v1/projects/{other}/envelope").status_code in (403, 404)


def test_staff_endpoint_needs_a_role(client: Any, project: str, login_as: Any) -> None:
    assert client.get(f"/api/v1/admin/projects/{project}/envelope").status_code == 401
    login_as("architect")
    response = client.get(f"/api/v1/admin/projects/{project}/envelope")
    assert response.status_code == 200
    assert response.json()["status"] in ("ok", "partial")


# ---------------------------------------------------------------------------
# Steckbrief
# ---------------------------------------------------------------------------


def test_sheet_is_created_once_per_input_state(
    client: Any, project: str, db_session: Any, memory_storage: dict[str, bytes]
) -> None:
    response = client.post(f"/api/v1/projects/{project}/envelope/sheet")
    assert response.status_code == 202, response.text
    pending = response.json()
    assert pending["status"] == "pending"
    assert client.get(f"/api/v1/projects/{project}/envelope/sheet").status_code == 409

    # Zweiter Klick legt keinen zweiten Job an (Idempotenz über die Prüfsumme)
    assert client.post(f"/api/v1/projects/{project}/envelope/sheet").json()["job_id"] == pending["job_id"]
    assert db_session.execute(select(Job).where(Job.kind == "envelope_sheet")).scalars().all() != []

    from app.envelope.jobs import envelope_sheet
    from app.platform.jobs.registry import JobContext

    result = envelope_sheet(
        JobContext(job_id=uuid.uuid4(), attempt=1, project_id=uuid.UUID(project)),
        {"project_id": project, "input_hash": pending["input_hash"], "locale": "de"},
    )
    assert result["size_bytes"] > 1000
    db_session.expire_all()
    stored = db_session.execute(select(EnvelopeSheet)).scalar_one()
    assert stored.input_hash == pending["input_hash"]
    assert memory_storage[stored.storage_key][:4] == b"%PDF"

    download = client.get(f"/api/v1/projects/{project}/envelope/sheet")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert client.post(f"/api/v1/projects/{project}/envelope/sheet").json()["status"] == "ready"


def test_sheet_job_uses_the_current_state(client: Any, project: str, db_session: Any) -> None:
    """Hat sich zwischen Auftrag und Lauf etwas geändert, entsteht der Steckbrief zum **aktuellen** Stand.

    Ein Job, der einen überholten Stand nur überspränge, käme nie zum Ziel, solange eine Eingabe noch
    eintrifft (Gelände nach `site_enrich`)."""
    from app.envelope.jobs import envelope_sheet
    from app.platform.jobs.registry import JobContext

    result = envelope_sheet(
        JobContext(job_id=uuid.uuid4(), attempt=1, project_id=uuid.UUID(project)),
        {"project_id": project, "input_hash": "sha256:veraltet"},
    )
    assert result["matched_request"] is False
    db_session.expire_all()
    stored = db_session.execute(select(EnvelopeSheet)).scalar_one()
    assert stored.input_hash == get_envelope(client, project)["input_hash"]
    assert client.get(f"/api/v1/projects/{project}/envelope/sheet").status_code == 200


# ---------------------------------------------------------------------------
# Dienstschnittstelle für andere Module
# ---------------------------------------------------------------------------


def test_service_returns_input_and_envelope_for_later_modules(db_session: Any, project: str) -> None:
    """Modul A übernimmt Baurahmen und Prüfsumme in den Snapshot (Plan G3 7)."""
    envelope, data = envelope_service.build_envelope(db_session, uuid.UUID(project))
    assert envelope.input_hash == envelope_service.fingerprint(data)
    assert data.site.parcels == [REGULAR]
    site = site_service.envelope_site(db_session, uuid.UUID(project))
    assert site.engine_version.startswith("g1-")
