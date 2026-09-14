"""Modul G2 gegen PostGIS: Planimport aus aufgezeichneten GPU-Antworten (Treillières, PLUi Erdre et Gesvres),
Auswertung mit aufgezeichneter Modellantwort, Kunden- und Büro-API. Das Testgrundstück AD 65 liegt in Zone Uh.
"""

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.config import get_settings
from app.integrations.claude import ExtractionError
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.platform.models import AuditLog, FeatureFlag, Job
from app.rules import extract
from app.rules.models import (
    LandUsePlan,
    OverlayConstraint,
    RegulationChapter,
    Rule,
    RuleExtractionRun,
    RulesCommune,
    RuleSet,
    RuleSetVersion,
    Zone,
)
from app.rules.plan_import import DirectoryGpu, import_commune
from app.site.cadastre_import import import_commune as import_cadastre
from tests.rules_support import FakeExtractor, gpu_directory, uh_output

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
    monkeypatch.setenv("EMPRISE_ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def plan(db_session: Any, tmp_path: Path, settings: Any) -> Any:
    result = import_commune(db_session, DirectoryGpu(gpu_directory(tmp_path)), settings, "44209")
    assert result.status == "imported", result
    return result


@contextmanager
def sessions() -> Iterator[Any]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def chapter_id(db_session: Any) -> uuid.UUID:
    return db_session.execute(select(RegulationChapter.id).where(RegulationChapter.code == "Uh")).scalar_one()


def run_extraction(
    db_session: Any, settings: Any, extractor: FakeExtractor, **kwargs: Any
) -> extract.ChapterOutcome:
    outcome = extract.extract_chapter(
        sessions, settings, chapter_id(db_session), extractor.factory(), **kwargs
    )
    db_session.expire_all()
    return outcome


@pytest.fixture
def site_project(client: Any, db_session: Any) -> str:
    result = import_cadastre(
        db_session,
        DirectoryCadastre(SITE_FIXTURES, "2026-06-01"),
        get_settings(),
        "44209",
        roads=DirectoryRoads(SITE_FIXTURES),
    )
    assert result.status == "succeeded"
    db_session.add(FeatureFlag(key="site_selection", enabled_for_all=True))
    db_session.add(FeatureFlag(key="rules_simulation", enabled_for_all=True))
    db_session.commit()
    project = str(client.post("/api/v1/projects").json()["id"])
    assert client.put(f"/api/v1/projects/{project}/site", json={"parcel_idus": [REGULAR]}).status_code == 200
    return project


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_chooses_plan_detects_chapter_and_enqueues_extraction(
    db_session: Any, plan: Any, memory_storage: dict[str, bytes], tmp_path: Path, settings: Any
) -> None:
    stored = db_session.execute(select(LandUsePlan)).scalar_one()
    assert stored.partition == "DU_244400503" and stored.status == "active" and stored.communes == ["44209"]
    assert "ERDRE ET GESVRES" in stored.title.upper()
    # Nur Zonen des gewählten Plans; Nachbarplan Nantes Métropole (Ad, UMe) fällt weg
    codes = set(db_session.execute(select(Zone.code)).scalars())
    assert codes == {"N", "Uh", "A", "Uec", "Ue"}
    chapter = db_session.execute(select(RegulationChapter)).scalar_one()
    assert (chapter.code, chapter.sectors, chapter.first_page, chapter.last_page) == ("Uh", ["Uh"], 4, 24)
    assert chapter.detection == "headings" and chapter.status == "pending"
    assert "zones_without_chapter:A,N,Ue,Uec" in plan.notes
    assert all(
        o.partition == "DU_244400503"
        for o in db_session.execute(select(OverlayConstraint)).scalars()
        if o.category != "servitude"
    )
    assert len(memory_storage) == 1
    jobs = db_session.execute(select(Job).where(Job.kind == "rules_extract")).scalars().all()
    assert len(jobs) == 1 and jobs[0].payload == {"chapter_id": str(chapter.id)}
    assert db_session.get(RulesCommune, "44209").status == "ok"

    again = import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209")
    assert again.status == "unchanged"
    assert db_session.execute(select(func.count()).select_from(LandUsePlan)).scalar_one() == 1


def test_new_plan_version_supersedes_previous(
    db_session: Any, plan: Any, tmp_path: Path, settings: Any
) -> None:
    import json

    zones = json.loads((tmp_path / "zone-urba-44209.json").read_text(encoding="utf-8"))
    for feature in zones["features"]:
        if feature["properties"]["partition"] == "DU_244400503":
            feature["properties"]["gpu_doc_id"] = "new-document"
    (tmp_path / "zone-urba-44209.json").write_text(json.dumps(zones), encoding="utf-8")
    document = json.loads(
        (tmp_path / "document-911b23511c396d7211def55c6bf40bd4.json").read_text(encoding="utf-8")
    )
    (tmp_path / "document-new-document.json").write_text(
        json.dumps(document | {"id": "new-document"}), encoding="utf-8"
    )

    result = import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209")
    assert result.status == "imported"
    db_session.expire_all()
    statuses = dict(db_session.execute(select(LandUsePlan.gpu_doc_id, LandUsePlan.status)).all())
    assert statuses == {"911b23511c396d7211def55c6bf40bd4": "superseded", "new-document": "active"}


def test_rnu_commune_has_no_plan(db_session: Any, tmp_path: Path, settings: Any) -> None:
    import json

    directory = gpu_directory(tmp_path)
    municipality = json.loads((directory / "municipality-44209.json").read_text(encoding="utf-8"))
    municipality["features"][0]["properties"]["is_rnu"] = True
    (directory / "municipality-44209.json").write_text(json.dumps(municipality), encoding="utf-8")
    assert import_commune(db_session, DirectoryGpu(directory), settings, "44209").status == "rnu"
    assert db_session.get(RulesCommune, "44209").status == "rnu"


# ---------------------------------------------------------------------------
# Auswertung
# ---------------------------------------------------------------------------


def test_extraction_writes_simulated_rule_set(db_session: Any, plan: Any, settings: Any) -> None:
    extractor = FakeExtractor([uh_output(), uh_output()])
    outcome = run_extraction(db_session, settings, extractor)
    assert outcome.status == "succeeded" and outcome.cost_usd == pytest.approx(0.16)
    assert len(extractor.requests) == 2
    request = extractor.requests[0]
    assert request.sectors == ["Uh"] and request.chapter_pages == list(range(4, 25))
    assert request.general_pages == [1, 2, 3] and request.general_pdf is not None

    rule_set = db_session.execute(select(RuleSet)).scalar_one()
    version = db_session.get(RuleSetVersion, rule_set.current_version_id)
    assert (
        version.status == "simulated"
        and version.origin == "extraction"
        and len(version.extraction_run_ids) == 2
    )
    rules = {(r.kind, r.building_kind): r for r in db_session.execute(select(Rule)).scalars()}
    street = rules[("setback_street", "main")]
    assert street.status == "effective" and street.page == 9 and street.quote_verified
    assert street.params == {"mode": "range", "min_m": 5.0, "max_m": 20.0, "measured_from": "facade"}
    assert rules[("max_height", "main")].params["ridge_m"] == 10.0
    assert rules[("roof", "main")].reason == "missing"
    assert version.coverage["mandatory_unknown"] == 3
    runs = db_session.execute(select(RuleExtractionRun)).scalars().all()
    assert {r.status for r in runs} == {"succeeded"} and sum(r.cost_usd for r in runs) == pytest.approx(0.16)

    # Unveränderte Eingabe: kein weiterer Aufruf
    assert run_extraction(db_session, settings, extractor).status == "skipped"
    assert len(extractor.requests) == 2


def test_disagreeing_runs_make_value_unknown(db_session: Any, plan: Any, settings: Any) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output(footprint=0.3)]))
    footprint = db_session.execute(
        select(Rule).where(Rule.kind == "max_footprint_ratio", Rule.building_kind == "main")
    ).scalar_one()
    assert footprint.status == "unknown" and footprint.reason == "runs_disagree"


def test_budget_and_missing_key_stop_before_calling_the_model(
    db_session: Any, plan: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    extractor = FakeExtractor([uh_output()])
    db_session.add(
        RuleExtractionRun(
            chapter_id=chapter_id(db_session),
            run_no=1,
            input_hash="x",
            model="m",
            prompt_version="p",
            status="succeeded",
            cost_usd=settings.rules_budget_month_usd,
        )
    )
    db_session.commit()
    assert run_extraction(db_session, settings, extractor).status == "budget_exceeded"
    assert extractor.requests == []
    assert db_session.get(RegulationChapter, chapter_id(db_session)).error == "budget_exceeded"

    monkeypatch.delenv("EMPRISE_ANTHROPIC_API_KEY")
    get_settings.cache_clear()
    assert run_extraction(db_session, get_settings(), extractor).status == "not_configured"


def test_retryable_error_keeps_successful_run(db_session: Any, plan: Any, settings: Any) -> None:
    flaky = FakeExtractor([uh_output(), ExtractionError("rate_limited", retryable=True)])
    with pytest.raises(extract.RetryableExtractionError):
        run_extraction(db_session, settings, flaky, final_attempt=False)
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "pending"

    retry = FakeExtractor([uh_output()])
    assert run_extraction(db_session, settings, retry).status == "succeeded"
    assert len(retry.requests) == 1  # Lauf 1 aus dem ersten Versuch wiederverwendet
    statuses = sorted(r.status for r in db_session.execute(select(RuleExtractionRun)).scalars())
    assert statuses == ["failed", "succeeded", "succeeded"]


def test_refusal_fails_chapter_without_retry(db_session: Any, plan: Any, settings: Any) -> None:
    outcome = run_extraction(
        db_session,
        settings,
        FakeExtractor([ExtractionError("refusal", retryable=False)]),
        final_attempt=False,
    )
    assert outcome.status == "failed" and outcome.detail == "refusal"
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "failed"


def test_rules_are_immutable(db_session: Any, plan: Any, settings: Any) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output()]))
    with pytest.raises(DBAPIError):
        db_session.execute(text("UPDATE rule SET status = 'effective' WHERE reason = 'missing'"))
    db_session.rollback()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_customer_sees_simulation_for_site(
    client: Any, db_session: Any, site_project: str, plan: Any, settings: Any
) -> None:
    url = f"/api/v1/projects/{site_project}/rules"
    pending = client.get(url).json()
    assert pending["status"] == "in_progress" and pending["simulation"] is True
    assert [z["code"] for z in pending["zones"]] == ["Uh"] and pending["zones"][0]["share"] > 0.99

    run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output()]))
    body = client.get(url).json()
    assert body["status"] == "ok" and body["plan"]["du_type"] == "PLUi"
    assert body["notices"] == ["notice.rules_simulation", "notice.rules_lotissement"]
    zone = body["zones"][0]
    assert zone["status"] == "simulated" and zone["version"]["origin"] == "extraction"
    street = next(r for r in zone["rules"] if r["kind"] == "setback_street" and r["building_kind"] == "main")
    assert street["source_url"].endswith("244400503_reglement_20260304.pdf#page=9")
    assert street["origin"] == "extraction" and street["quote_verified"]
    assert [h["kind"] for h in zone["hints"]] == ["text_only"]


def test_customer_endpoint_needs_flag_and_own_project(
    client: Any, db_session: Any, site_project: str, plan: Any
) -> None:
    from fastapi.testclient import TestClient

    other = TestClient(client.app, base_url="http://testserver")
    other.get("/api/v1/session")
    assert other.get(f"/api/v1/projects/{site_project}/rules").status_code in (403, 404)
    db_session.execute(text("DELETE FROM feature_flag WHERE key = 'rules_simulation'"))
    db_session.commit()
    assert client.get(f"/api/v1/projects/{site_project}/rules").json()["code"] == "feature_disabled"


def test_outside_imported_communes_is_unavailable(client: Any, site_project: str) -> None:
    body = client.get(f"/api/v1/projects/{site_project}/rules").json()
    assert body["status"] == "unavailable" and body["reason"] == "not_imported"


def test_office_coverage_zone_correction_and_project_override(
    client: Any, db_session: Any, site_project: str, plan: Any, settings: Any, login_as: Callable[..., Any]
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output()]))
    login_as("architect")
    coverage = client.get("/api/v1/admin/rules/coverage").json()
    commune = coverage["communes"][0]
    assert (
        commune["commune_insee"] == "44209" and commune["status"] == "ok" and coverage["configured"] is True
    )
    chapter = commune["chapters"][0]
    assert chapter["runs"] == 2 and chapter["rule_sets"]["Uh"]["status"] == "simulated"
    rule_set_id = chapter["rule_set_ids"]["Uh"]

    detail = client.get(f"/api/v1/admin/rule-sets/{rule_set_id}").json()
    assert detail["current"]["status"] == "simulated"
    corrected = [
        {
            "kind": "setback_street",
            "status": "effective",
            "params": {"mode": "range", "min_m": 5, "max_m": 20},
            "page": 97,
        },
        {"kind": "max_footprint_ratio", "status": "effective", "params": {"ratio": 0.25}},
        {"kind": "roof", "status": "not_regulated", "notes": "Pas de règle chiffrée"},
    ]
    invalid = client.post(
        f"/api/v1/admin/rule-sets/{rule_set_id}/versions",
        json={
            "rules": [{"kind": "max_footprint_ratio", "status": "effective", "params": {"ratio": 25}}],
            "note": "Test",
        },
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "rule_params_invalid"
    created = client.post(
        f"/api/v1/admin/rule-sets/{rule_set_id}/versions",
        json={"rules": corrected, "note": "Geprüft bei Anfrage"},
    )
    assert created.status_code == 201, created.json()
    assert (
        created.json()["current"]["status"] == "office_reviewed"
        and created.json()["versions"][1]["status"] == "retired"
    )
    zone = client.get(f"/api/v1/projects/{site_project}/rules").json()["zones"][0]
    assert zone["status"] == "office_reviewed" and {r["origin"] for r in zone["rules"]} == {"office"}

    # Neue automatische Auswertung ersetzt die geprüfte Version nicht
    run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output()]), force=True)
    assert (
        db_session.get(
            RuleSetVersion, db_session.get(RuleSet, uuid.UUID(rule_set_id)).current_version_id
        ).status
        == "office_reviewed"
    )

    override = client.put(
        f"/api/v1/admin/projects/{site_project}/rule-overrides",
        json={
            "zone_code": "Uh",
            "kind": "max_footprint_ratio",
            "status": "effective",
            "params": {"ratio": 0.2},
            "note": "Règlement du lotissement",
        },
    )
    assert override.status_code == 200 and override.json()[0]["params"]["ratio"] == 0.2
    zone = client.get(f"/api/v1/projects/{site_project}/rules").json()["zones"][0]
    footprint = [r for r in zone["rules"] if r["kind"] == "max_footprint_ratio"]
    assert (
        len(footprint) == 1 and footprint[0]["origin"] == "project" and footprint[0]["params"]["ratio"] == 0.2
    )
    removed = client.delete(
        f"/api/v1/admin/projects/{site_project}/rule-overrides/{override.json()[0]['id']}"
    )
    assert removed.status_code == 200 and removed.json() == []
    actions = set(db_session.execute(select(AuditLog.action)).scalars())
    assert {"rule_set.office_version", "project_rule_override.put", "project_rule_override.delete"} <= actions


def test_office_roles(
    client: Any, db_session: Any, site_project: str, plan: Any, login_as: Callable[..., Any]
) -> None:
    assert client.get("/api/v1/admin/rules/coverage").status_code == 401
    login_as("catalog_admin")
    assert client.get("/api/v1/admin/rules/coverage").status_code == 403
    login_as("architect")
    chapter = chapter_id(db_session)
    assert (
        client.post(f"/api/v1/admin/rules/chapters/{chapter}/extract", json={"force": True}).status_code
        == 403
    )
    login_as("ops")
    started = client.post(f"/api/v1/admin/rules/chapters/{chapter}/extract", json={"force": True})
    assert started.status_code == 202
    job = db_session.get(Job, uuid.UUID(started.json()["job_id"]))
    assert job.kind == "rules_extract" and job.payload["force"] is True
    assert client.post("/api/v1/admin/rules/imports", json={"communes": ["44209"]}).status_code == 202


def test_running_extraction_is_not_started_twice(db_session: Any, plan: Any, settings: Any) -> None:
    chapter = db_session.get(RegulationChapter, chapter_id(db_session))
    chapter.status = "extracting"
    db_session.commit()
    extractor = FakeExtractor([uh_output()])
    assert run_extraction(db_session, settings, extractor).detail == "already_running"
    assert extractor.requests == []
    assert (
        run_extraction(db_session, settings, FakeExtractor([uh_output(), uh_output()]), force=True).status
        == "succeeded"
    )
