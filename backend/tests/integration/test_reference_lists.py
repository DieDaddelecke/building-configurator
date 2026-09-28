"""Referenzlisten in der gemeinsamen Verwaltung (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10, VA10).

Die gemeinsame Datenbank liegt in Tests in der Testdatenbank. Gemessen wird die Auswertung des Kapitels Uh
(Treillières) mit der aufgezeichneten Modellantwort.
"""

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app import cli
from app.config import get_settings
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.platform.shared import SharedAudit
from app.rules import extract
from app.rules.models import LandUsePlan, RegulationChapter, SourceFile
from app.rules.plan_import import DirectoryGpu, import_commune
from app.rules.reference_models import ReferenceList
from tests.rules_support import DOC_ID, FakeExtractor, gpu_directory, uh_output

STREET = {
    "kind": "setback_street",
    "building_kind": "main",
    "expected": "effective",
    "params": {"mode": "range", "min_m": 5.0, "max_m": 20.0},
    "page": 9,
    "quote": "Les constructions principales, hors extension, doivent être implantées dans une bande "
    "située entre 5 m et 20m par rapport à l’alignement des voies .",
}
ROOF = {
    "kind": "roof",
    "building_kind": "main",
    "expected": "effective",
    "params": {"pitch_min_deg": 30.0},
    "page": 14,
    "quote": "présenteront 2 versants principaux dont la pente est comprise entre 30° et 45°",
}


@pytest.fixture(autouse=True)
def memory_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    objects: dict[str, bytes] = {}
    monkeypatch.setattr(
        storage, "put_bytes", lambda key, data, content_type="": objects.__setitem__(key, data)
    )
    monkeypatch.setattr(storage, "get_bytes", lambda key: objects[key])
    return objects


@contextmanager
def sessions() -> Iterator[Any]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def evaluated(db_session: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Kapitel Uh ausgewertet; gibt die Prüfsumme der Planunterlage zurück."""
    monkeypatch.setenv("EMPRISE_OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()
    assert (
        import_commune(db_session, DirectoryGpu(gpu_directory(tmp_path)), settings, "44209").status
        == "imported"
    )
    chapter = db_session.execute(
        select(RegulationChapter)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(RegulationChapter.code == "Uh", LandUsePlan.gpu_doc_id == DOC_ID)
    ).scalar_one()
    extractor = FakeExtractor([uh_output(), uh_output()])
    assert extract.extract_chapter(sessions, settings, chapter.id, extractor.factory()).status == "succeeded"
    db_session.expire_all()
    return str(db_session.get(SourceFile, chapter.source_file_id).sha256)


def test_list_entries_measurement_and_status(
    client: Any, login_as: Callable[..., Any], evaluated: str, db_session: Any
) -> None:
    login_as("rules_admin")
    candidates = client.get("/api/v1/admin/reference-lists/candidates").json()
    assert [(c["document_sha256"], "Uh" in c["sectors"]) for c in candidates] == [(evaluated, True)]

    created = client.post(
        "/api/v1/admin/reference-lists",
        json={"document_sha256": evaluated, "document_title": "PLUi Erdre et Gesvres", "sector": "Uh"},
    )
    assert created.status_code == 201, created.json()
    list_id = created.json()["id"]
    assert created.json()["status"] == "draft" and created.json()["summary"] is None
    duplicate = client.post(
        "/api/v1/admin/reference-lists",
        json={"document_sha256": evaluated, "document_title": "x", "sector": "Uh"},
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "reference_list_exists"

    client.post(f"/api/v1/admin/reference-lists/{list_id}/entries", json=STREET)
    body = client.post(f"/api/v1/admin/reference-lists/{list_id}/entries", json=ROOF).json()
    assert [e["kind"] for e in body["entries"]] == ["setback_street", "roof"]
    assert body["summary"]["counts"]["hit"] == 1 and body["summary"]["counts"]["named_gap"] == 1

    measured = client.get(f"/api/v1/admin/reference-lists/{list_id}/measurement").json()
    assert measured["version"] == 1 and measured["versions"] == [1] and measured["recall"] == 0.5
    roof = next(r for r in measured["results"] if r["entry_id"] == body["entries"][1]["id"])
    assert roof["outcome"] == "named_gap" and roof["found"]["reason"] == "missing"
    assert {e["kind"] for e in measured["extra"]} >= {"max_height", "max_footprint_ratio"}

    checked = client.patch(f"/api/v1/admin/reference-lists/{list_id}", json={"status": "checked"}).json()
    assert checked["status"] == "checked"
    # Eine Änderung an einem Eintrag macht die Liste wieder zum Entwurf
    changed = client.put(
        f"/api/v1/admin/reference-lists/{list_id}/entries/{body['entries'][1]['id']}",
        json={**ROOF, "params": {"pitch_min_deg": 30.0, "pitch_max_deg": 45.0}},
    ).json()
    assert changed["status"] == "draft" and changed["entries"][1]["params"]["pitch_max_deg"] == 45.0
    invalid = client.post(
        f"/api/v1/admin/reference-lists/{list_id}/entries", json={**ROOF, "params": {"ratio": 0.4}}
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "reference_invalid"

    actions = set(db_session.execute(select(SharedAudit.action)).scalars())
    assert {"reference_list_created", "reference_entry_added", "reference_list_changed"} <= actions


def test_export_import_and_draft_from_evaluation(
    client: Any, login_as: Callable[..., Any], evaluated: str
) -> None:
    login_as("ops")
    list_id = client.post(
        "/api/v1/admin/reference-lists",
        json={"document_sha256": evaluated, "document_title": "PLUi", "sector": "Uh"},
    ).json()["id"]
    drafted = client.post(f"/api/v1/admin/reference-lists/{list_id}/from-evaluation").json()
    kinds = {(e["kind"], e["expected"]) for e in drafted["entries"]}
    assert ("setback_street", "effective") in kinds and ("text_only", "text_only") in kinds
    assert ("roof", "effective") not in kinds  # offen ohne Befund: fehlt der Auswertung, nicht der Liste
    assert drafted["summary"]["counts"]["wrong_value"] == 0

    exported = client.get(f"/api/v1/admin/reference-lists/{list_id}/export").json()
    assert exported["format"] == "emprise-reference/1" and len(exported["entries"]) == len(drafted["entries"])
    again = client.post("/api/v1/admin/reference-lists/import", json=exported)
    assert again.status_code == 409
    replaced = client.post("/api/v1/admin/reference-lists/import?replace=true", json=exported)
    assert replaced.status_code == 201 and replaced.json()["id"] == list_id
    assert client.delete(f"/api/v1/admin/reference-lists/{list_id}").status_code == 204
    assert client.get("/api/v1/admin/reference-lists").json() == []


def test_architects_do_not_manage_reference_lists(client: Any, login_as: Callable[..., Any]) -> None:
    login_as("architect")
    assert client.get("/api/v1/admin/reference-lists").status_code == 403


def test_seed_list_imports_and_is_not_evaluated_here(
    client: Any, login_as: Callable[..., Any], db_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.cmd_reference_import(type("Args", (), {"file": "beyenes_uc.json", "replace": False})())
    assert "25 Einträge" in capsys.readouterr().out
    row = db_session.execute(select(ReferenceList)).scalar_one()
    assert (row.sector, row.status) == ("UC", "draft")
    login_as("ops")
    listed = client.get("/api/v1/admin/reference-lists").json()
    assert listed[0]["entries_count"] == 25 and listed[0]["summary"] is None
    missing = client.get(f"/api/v1/admin/reference-lists/{row.id}/measurement")
    assert missing.status_code == 404 and missing.json()["code"] == "reference_not_evaluated"
    assert client.get(f"/api/v1/admin/reference-lists/{uuid.uuid4()}").status_code == 404
