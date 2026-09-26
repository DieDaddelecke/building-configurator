"""Modul G2 gegen PostGIS: Planimport aus aufgezeichneten GPU-Antworten (Treillières, PLUi Erdre et Gesvres),
Auswertung mit aufgezeichneter Modellantwort, Kunden- und Büro-API. Das Testgrundstück AD 65 liegt in Zone Uh.
"""

import json
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.config import get_settings
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.integrations.openrouter import ExtractionError, ExtractionRequest, ExtractionResponse
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.platform.models import AuditLog, FeatureFlag, Job
from app.rules import extract, service
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
from app.rules.schemas import RuleIn, RuleOut, RuleSetVersionIn
from app.site.cadastre_import import import_commune as import_cadastre
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


def chapter_id(db_session: Any, doc_id: str = DOC_ID) -> uuid.UUID:
    return db_session.execute(
        select(RegulationChapter.id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(RegulationChapter.code == "Uh", LandUsePlan.gpu_doc_id == doc_id)
    ).scalar_one()


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
    assert street.params == {
        "mode": "range",
        "min_m": 5.0,
        "max_m": 20.0,
        "band": "building",
        "measured_from": "facade",
    }
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

    monkeypatch.delenv("EMPRISE_OPENROUTER_API_KEY")
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
    # Der Import hat schon einen Job eingeplant: ein Klick legt keinen zweiten an (kostet nicht doppelt)
    waiting = db_session.execute(select(Job.id).where(Job.kind == "rules_extract")).scalar_one()
    started = client.post(f"/api/v1/admin/rules/chapters/{chapter}/extract", json={"force": True})
    assert started.status_code == 202 and started.json()["job_id"] == str(waiting)
    db_session.execute(text("UPDATE job SET status = 'succeeded' WHERE id = :id"), {"id": waiting})
    db_session.commit()
    again = client.post(f"/api/v1/admin/rules/chapters/{chapter}/extract", json={"force": True})
    second = client.post(f"/api/v1/admin/rules/chapters/{chapter}/extract", json={})
    assert again.json()["job_id"] == second.json()["job_id"] != str(waiting)
    job = db_session.get(Job, uuid.UUID(again.json()["job_id"]))
    assert job.kind == "rules_extract" and job.payload["force"] is True
    assert client.post("/api/v1/admin/rules/imports", json={"communes": ["44209"]}).status_code == 202


def test_running_extraction_is_not_started_twice(db_session: Any, plan: Any, settings: Any) -> None:
    chapter = db_session.get(RegulationChapter, chapter_id(db_session))
    chapter.status = "extracting"
    db_session.commit()
    extractor = FakeExtractor([uh_output()])
    assert run_extraction(db_session, settings, extractor).detail == "already_running"
    assert run_extraction(db_session, settings, extractor, force=True).detail == "already_running"
    assert extractor.requests == []
    # Wiederholung desselben Jobs nach Absturz
    retry = run_extraction(db_session, settings, FakeExtractor([uh_output()]), skip_if_running=False)
    assert retry.status == "succeeded"


# ---------------------------------------------------------------------------
# Robustheit (Prüfung vom 14.09.2026)
# ---------------------------------------------------------------------------


def _document(tmp_path: Path, doc_id: str = "new-document", **changes: Any) -> None:
    """Planstand im GPU ändern: neues Dokument für die Zonen oder geänderte Angaben desselben Dokuments."""
    if doc_id != DOC_ID:
        zones = json.loads((tmp_path / "zone-urba-44209.json").read_text(encoding="utf-8"))
        for feature in zones["features"]:
            if feature["properties"]["partition"] == "DU_244400503":
                feature["properties"]["gpu_doc_id"] = doc_id
        (tmp_path / "zone-urba-44209.json").write_text(json.dumps(zones), encoding="utf-8")
    source = json.loads((tmp_path / f"document-{DOC_ID}.json").read_text(encoding="utf-8"))
    (tmp_path / f"document-{doc_id}.json").write_text(
        json.dumps(source | {"id": doc_id} | changes), encoding="utf-8"
    )


def test_force_import_keeps_office_version_runs_and_evaluation(
    db_session: Any, plan: Any, tmp_path: Path, settings: Any
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output()]))
    rule_set = db_session.execute(select(RuleSet)).scalar_one()
    service.create_office_version(
        db_session,
        rule_set.id,
        RuleSetVersionIn(
            rules=[RuleIn(kind="max_footprint_ratio", status="effective", params={"ratio": 0.25})],
            note="Geprüft bei Anfrage",
        ),
        "staff:test",
    )
    runs = db_session.execute(select(func.count()).select_from(RuleExtractionRun)).scalar_one()
    jobs = db_session.execute(
        select(func.count()).select_from(Job).where(Job.kind == "rules_extract")
    ).scalar_one()

    result = import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209", force=True)
    assert result.status == "refreshed"
    db_session.expire_all()
    assert db_session.execute(select(func.count()).select_from(LandUsePlan)).scalar_one() == 1
    current = db_session.get(RuleSetVersion, db_session.get(RuleSet, rule_set.id).current_version_id)
    assert current.status == "office_reviewed"
    assert db_session.execute(select(func.count()).select_from(RuleExtractionRun)).scalar_one() == runs
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "succeeded"
    assert (
        db_session.execute(
            select(func.count()).select_from(Job).where(Job.kind == "rules_extract")
        ).scalar_one()
        == jobs
    )


def test_changed_document_date_refreshes_plan(
    db_session: Any, plan: Any, tmp_path: Path, settings: Any
) -> None:
    _document(tmp_path, DOC_ID, updateDate="01/09/2026 10:00:00")
    assert import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209").status == "refreshed"
    db_session.expire_all()
    stored = db_session.execute(select(LandUsePlan)).scalar_one()
    assert stored.gpu_update_date == "01/09/2026 10:00:00"
    assert import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209").status == "unchanged"


def test_new_plan_shows_previous_rules_as_outdated_until_evaluated(
    client: Any, db_session: Any, site_project: str, plan: Any, tmp_path: Path, settings: Any
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output()]))
    _document(tmp_path)
    assert import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209").status == "imported"
    url = f"/api/v1/projects/{site_project}/rules"
    body = client.get(url).json()
    assert "rules_outdated" in body["warnings"] and body["plan"]["gpu_doc_id"] == DOC_ID
    assert body["zones"][0]["status"] == "outdated" and body["zones"][0]["rules"]

    extract.extract_chapter(
        sessions, settings, chapter_id(db_session, "new-document"), FakeExtractor([uh_output()]).factory()
    )
    db_session.expire_all()
    body = client.get(url).json()
    assert body["plan"]["gpu_doc_id"] == "new-document" and body["zones"][0]["status"] == "simulated"
    assert "rules_outdated" not in body["warnings"]
    assert db_session.get(RulesCommune, "44209").fallback_land_use_plan_id is None


def test_unreadable_new_plan_keeps_previous_rules(
    client: Any, db_session: Any, site_project: str, plan: Any, tmp_path: Path, settings: Any
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output()]))
    _document(tmp_path, files=[])
    assert import_commune(db_session, DirectoryGpu(tmp_path), settings, "44209").status == "no_regulation"
    body = client.get(f"/api/v1/projects/{site_project}/rules").json()
    assert "plan_update_failed" in body["warnings"] and body["zones"][0]["status"] == "outdated"
    assert db_session.get(RulesCommune, "44209").status == "no_regulation"


def test_several_regulation_files_are_not_evaluated(db_session: Any, tmp_path: Path, settings: Any) -> None:
    directory = gpu_directory(tmp_path)
    source = json.loads((directory / f"document-{DOC_ID}.json").read_text(encoding="utf-8"))
    source["files"].append({"name": "244400503_reglement_tome2.pdf", "title": "Règlement écrit – Tome 2"})
    (directory / f"document-{DOC_ID}.json").write_text(json.dumps(source), encoding="utf-8")
    result = import_commune(db_session, DirectoryGpu(directory), settings, "44209")
    assert result.status == "multiple_regulations"
    state = db_session.get(RulesCommune, "44209")
    assert state.status == "multiple_regulations" and "tome2" in state.error


def test_too_long_answer_splits_sectors(db_session: Any, plan: Any, settings: Any) -> None:
    chapter = db_session.get(RegulationChapter, chapter_id(db_session))
    chapter.sectors = ["Uh", "Uhb"]
    db_session.commit()
    extractor = FakeExtractor(
        [
            ExtractionError("max_tokens", retryable=False),
            uh_output(),
            {"remarks": "", "rules": []},
            uh_output(),
        ]
    )
    outcome = run_extraction(db_session, settings, extractor)
    assert outcome.status == "succeeded"
    assert [r.sectors for r in extractor.requests[:3]] == [["Uh", "Uhb"], ["Uh"], ["Uhb"]]
    assert extractor.requests[3].claims
    zones = set(db_session.execute(select(RuleSet.zone_code)).scalars())
    assert zones == {"Uh", "Uhb"}


def test_new_engine_version_reassesses_stored_answers_without_api(
    db_session: Any, plan: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output()]))
    chapter = db_session.get(RegulationChapter, chapter_id(db_session))
    chapter.engine_version = "g2-0.9.0"
    db_session.commit()
    monkeypatch.delenv("EMPRISE_OPENROUTER_API_KEY")
    get_settings.cache_clear()
    outcome = run_extraction(db_session, get_settings(), FakeExtractor([]))  # ein Aufruf schlüge fehl
    assert outcome.status == "succeeded" and outcome.cost_usd == 0
    assert db_session.execute(select(func.count()).select_from(RuleSetVersion)).scalar_one() == 2


class _Interrupted:
    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        raise TimeoutError("job timeout")


def test_interrupted_extraction_does_not_stay_extracting(
    db_session: Any, plan: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(TimeoutError):
        extract.extract_chapter(sessions, settings, chapter_id(db_session), _Interrupted, final_attempt=False)
    db_session.expire_all()
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "pending"

    monkeypatch.setattr(storage, "get_bytes", lambda key: (_ for _ in ()).throw(RuntimeError("storage")))
    with pytest.raises(RuntimeError):
        extract.extract_chapter(sessions, settings, chapter_id(db_session), _Interrupted)
    db_session.expire_all()
    chapter = db_session.get(RegulationChapter, chapter_id(db_session))
    assert (chapter.status, chapter.error) == ("failed", "interrupted:RuntimeError")
    errors = set(db_session.execute(select(RuleExtractionRun.error)).scalars())
    assert errors == {"interrupted:TimeoutError"}


def test_time_budget_reschedules_before_calling(db_session: Any, plan: Any, settings: Any) -> None:
    extractor = FakeExtractor([uh_output()])
    with pytest.raises(extract.RetryableExtractionError):
        run_extraction(db_session, settings, extractor, deadline=time.monotonic())
    assert extractor.requests == []
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "pending"


def test_housekeeping_restarts_recoverable_chapters(db_session: Any, plan: Any, settings: Any) -> None:
    def state(status: str, error: str | None = None, **extra: Any) -> None:
        db_session.execute(text("UPDATE job SET status = 'succeeded' WHERE kind = 'rules_extract'"))
        chapter = db_session.get(RegulationChapter, chapter_id(db_session))
        chapter.status, chapter.error = status, error
        for key, value in extra.items():
            setattr(chapter, key, value)
        db_session.commit()

    state("failed", "not_configured")
    assert service.housekeeping(db_session, settings) == {"configured": 1}
    assert db_session.get(RegulationChapter, chapter_id(db_session)).status == "pending"
    assert service.housekeeping(db_session, settings) == {}  # Job wartet schon

    state("failed", "refusal")
    assert service.housekeeping(db_session, settings) == {}

    state("extracting")
    db_session.execute(text("UPDATE regulation_chapter SET updated_at = now() - interval '2 hours'"))
    db_session.commit()
    assert service.housekeeping(db_session, settings) == {"stale": 1}
    db_session.expire_all()
    assert db_session.get(RegulationChapter, chapter_id(db_session)).error == "interrupted:stale"

    state("succeeded", None, engine_version="g2-0.9.0")
    assert service.housekeeping(db_session, settings) == {"engine_changed": 1}


def test_partly_uncovered_site_is_flagged(
    client: Any, db_session: Any, site_project: str, plan: Any, settings: Any
) -> None:
    run_extraction(db_session, settings, FakeExtractor([uh_output()]))
    db_session.execute(
        text(
            """
            UPDATE zone z SET geometry = ST_Multi(ST_CollectionExtract(ST_Difference(z.geometry, (
                SELECT ST_MakeEnvelope(ST_XMin(s.geometry), ST_YMin(s.geometry),
                                       (ST_XMin(s.geometry) + ST_XMax(s.geometry)) / 2,
                                       ST_YMax(s.geometry), 2154)
                FROM site s)), 3))
            WHERE z.code = 'Uh'
            """
        )
    )
    db_session.commit()
    body = client.get(f"/api/v1/projects/{site_project}/rules").json()
    assert "zone_coverage_incomplete" in body["warnings"] and body["uncovered_share"] > 0.2


def _rule(kind: str, building_kind: str) -> RuleOut:
    return RuleOut(
        kind=kind,
        building_kind=building_kind,
        status="effective",
        reason=None,
        params={"min_m": 3},
        page=7,
        quote="q",
        quote_verified=True,
        source_url=None,
        confidence=0.9,
        notes=None,
        origin="extraction",
    )


def test_project_override_for_main_building_narrows_general_rule() -> None:
    from app.rules.models import ProjectRuleOverride

    def override(kind: str, building_kind: str) -> ProjectRuleOverride:
        return ProjectRuleOverride(
            kind=kind, building_kind=building_kind, status="effective", params={}, note="x"
        )

    rules = [_rule("setback_side", "any"), _rule("max_footprint_ratio", "any")]
    side = service.apply_override(rules, override("setback_side", "main"))
    assert sorted((r.kind, r.building_kind, r.origin) for r in side) == [
        ("max_footprint_ratio", "any", "extraction"),
        ("setback_side", "annex", "extraction"),
        ("setback_side", "main", "project"),
        ("setback_side", "pool", "extraction"),
    ]
    footprint = service.apply_override(rules, override("max_footprint_ratio", "main"))
    assert [(r.kind, r.building_kind, r.origin) for r in footprint if r.kind == "max_footprint_ratio"] == [
        ("max_footprint_ratio", "main", "project")
    ]
    everything = service.apply_override(side, override("setback_side", "any"))
    assert [(r.kind, r.building_kind) for r in everything if r.kind == "setback_side"] == [
        ("setback_side", "any")
    ]
