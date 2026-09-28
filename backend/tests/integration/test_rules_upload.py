"""Hochgeladenes règlement écrit (AN2, docs/PLAN_AN2_PLU.md) gegen PostGIS.

Grundlage ist dasselbe Reglement wie im GPU-Test (PLUi Erdre et Gesvres, Kapitel Uh, `tests/rules_support.py`)
und dieselbe aufgezeichnete Modellantwort. So ist der zweite Einstieg in `resolve_rules` gegen den ersten
geprüft (PLAN_ANALYSE 7 Punkt 5): gleiche Regeln, gleicher Baurahmen.
"""

import hashlib
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.platform.jobs.worker import run_one
from app.platform.models import FeatureFlag, Job
from app.rules import documents, extract
from app.rules.models import (
    LandUsePlan,
    ProjectRegulation,
    RegulationChapter,
    RuleExtractionRun,
    SourceFile,
    SourcePage,
)
from app.rules.plan_import import DirectoryGpu, import_commune
from app.site.cadastre_import import import_commune as import_cadastre
from tests.integration.test_site_upload import LOCAL_RING, dxf_bytes
from tests.rules_support import DOC_ID, FakeExtractor, gpu_directory, regulation_fixture, text_pdf, uh_output

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
def flags(db_session: Any) -> None:
    for key in ("site_selection", "rules_simulation", "envelope_simulation"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def architect(login_as: Callable[..., Any], flags: None) -> Any:
    return login_as("architect")


def new_project(client: Any) -> str:
    return str(client.post("/api/v1/projects").json()["id"])


@pytest.fixture
def upload_project(client: Any, architect: Any) -> str:
    """Projekt des Architekten mit einer Parzelle aus einer DXF-Datei (20 × 30 m, ohne Lage)."""
    project = new_project(client)
    response = client.post(
        f"/api/v1/projects/{project}/site/upload",
        files={"file": ("plan.dxf", dxf_bytes((LOCAL_RING, "PARCELLE")), "application/octet-stream")},
        data={"address_label": "Parzelle aus Datei"},
    )
    assert response.status_code == 200, response.json()
    return project


def upload_regulation(
    client: Any, project: str, data: bytes, name: str = "reglement.pdf", **form: Any
) -> Any:
    return client.post(
        f"/api/v1/projects/{project}/regulations",
        files={"file": (name, data, "application/pdf")},
        data=form,
    )


def read_document(document_id: str, file_name: str = "reglement.pdf") -> dict[str, Any]:
    with sessions() as session:
        return documents.read_document(session, uuid.UUID(document_id), file_name)


def uploaded(client: Any, project: str) -> dict[str, Any]:
    """Reglement hochladen und lesen; liefert den Stand des Projekts."""
    pdf, _pages = regulation_fixture()
    response = upload_regulation(client, project, pdf, title="PLUi Erdre et Gesvres", du_type="PLUi")
    assert response.status_code == 202, response.json()
    document_id = response.json()["document"]["id"]
    assert read_document(document_id)["status"] == "active"
    listed = client.get(f"/api/v1/projects/{project}/regulations").json()
    assert len(listed) == 1
    body: dict[str, Any] = listed[0]
    return body


def choose(client: Any, project: str, document_id: str, **body: Any) -> Any:
    return client.put(f"/api/v1/projects/{project}/regulations/{document_id}/zone", json=body)


def upload_chapter(db_session: Any, code: str = "Uh") -> uuid.UUID:
    db_session.expire_all()
    return db_session.execute(
        select(RegulationChapter.id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(RegulationChapter.code == code, LandUsePlan.origin == "upload")
    ).scalar_one()


def evaluate(db_session: Any, settings: Any, code: str = "Uh") -> extract.ChapterOutcome:
    outcome = extract.extract_chapter(
        sessions, settings, upload_chapter(db_session, code), FakeExtractor([uh_output()]).factory()
    )
    db_session.expire_all()
    return outcome


def extract_jobs(db_session: Any) -> list[Job]:
    db_session.expire_all()
    return list(db_session.execute(select(Job).where(Job.kind == "rules_extract")).scalars())


# ---------------------------------------------------------------------------
# Hochladen und lesen
# ---------------------------------------------------------------------------


def test_upload_reads_chapters_without_costs(
    client: Any, upload_project: str, db_session: Any, memory_storage: dict[str, bytes]
) -> None:
    pdf, _pages = regulation_fixture()
    response = upload_regulation(client, upload_project, pdf, title="PLUi Erdre et Gesvres", du_type="PLUi")
    assert response.status_code == 202, response.json()
    body = response.json()
    assert body["role"] == "plu" and body["zone_code"] is None
    assert body["document"]["status"] == "importing" and body["document"]["chapters"] == []
    assert list(memory_storage) == [documents.storage_key(hashlib.sha256(pdf).hexdigest())]
    # Gelesen wird im Job, nicht im Request; ausgewertet wird noch nichts
    assert [j.kind for j in db_session.execute(select(Job)).scalars()] == ["rules_document_read"]

    assert run_one("w1", ["default"]) is True
    listed = client.get(f"/api/v1/projects/{upload_project}/regulations").json()[0]["document"]
    assert listed["status"] == "active" and listed["title"] == "PLUi Erdre et Gesvres"
    assert listed["du_type"] == "PLUi" and listed["page_count"] == 24
    assert listed["file_url"].startswith("/api/v1/regulation-files/")
    chapter = next(c for c in listed["chapters"] if c["code"] == "Uh")
    assert (chapter["first_page"], chapter["last_page"], chapter["general_pages"]) == (4, 24, [1, 2, 3])
    assert chapter["status"] == "idle" and chapter["sectors"] == [] and chapter["cost_usd"] == 0
    assert extract_jobs(db_session) == []


def test_scanned_regulation_fails_with_reason(client: Any, upload_project: str) -> None:
    scan = text_pdf(["", "", "Page de garde", ""])
    response = upload_regulation(client, upload_project, scan)
    assert response.status_code == 202
    document_id = response.json()["document"]["id"]
    assert read_document(document_id) == {"status": "failed", "error": "document_no_text"}
    body = client.get(f"/api/v1/projects/{upload_project}/regulations").json()[0]
    assert body["document"]["status"] == "failed" and body["document"]["error"] == "document_no_text"
    rules = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert rules["status"] == "unavailable" and rules["reason"] == "document_no_text"
    refused = choose(client, upload_project, document_id, zone_code="Uh", chapter_code="Uh")
    assert refused.status_code == 409 and refused.json()["code"] == "document_failed"


@pytest.mark.parametrize(
    ("data", "code"),
    [(b"PK\x03\x04 kein PDF", "not_a_pdf"), (b"%PDF-1.7\n kaputt", "pdf_unreadable")],
)
def test_upload_rejects_what_is_no_readable_pdf(
    client: Any, upload_project: str, data: bytes, code: str
) -> None:
    response = upload_regulation(client, upload_project, data)
    assert response.status_code == 422 and response.json()["code"] == code


def test_same_pdf_is_one_document_for_two_projects(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    first = uploaded(client, upload_project)
    assert (
        choose(client, upload_project, first["document"]["id"], zone_code="Uh", chapter_code="Uh").status_code
        == 200
    )

    second = new_project(client)
    pdf, _pages = regulation_fixture()
    again = upload_regulation(client, second, pdf, title="anderer Titel")
    assert again.status_code == 202
    body = again.json()
    # Dasselbe Dokument: schon gelesen, Titel des ersten Uploads, kein zweiter Lesejob
    assert body["document"]["id"] == first["document"]["id"] and body["document"]["status"] == "active"
    assert body["document"]["title"] == "PLUi Erdre et Gesvres"
    db_session.expire_all()
    assert db_session.execute(select(func.count()).select_from(LandUsePlan)).scalar_one() == 1
    assert (
        db_session.execute(
            select(func.count()).select_from(Job).where(Job.kind == "rules_document_read")
        ).scalar_one()
        == 1
    )

    # Dieselbe Zone im zweiten Projekt: keine neue Eingabe, kein neuer Auswertungsjob
    assert (
        choose(client, second, first["document"]["id"], zone_code="Uh", chapter_code="Uh").status_code == 200
    )
    assert len(extract_jobs(db_session)) == 1


# ---------------------------------------------------------------------------
# Zone wählen
# ---------------------------------------------------------------------------


def test_zone_choice_plans_one_extraction(client: Any, upload_project: str, db_session: Any) -> None:
    state = uploaded(client, upload_project)
    before = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert before["status"] == "unavailable" and before["reason"] == "zone_not_chosen"
    assert before["plan"]["origin"] == "upload" and before["plan"]["gpu_doc_id"] is None
    assert before["notices"] == ["notice.rules_simulation", "notice.rules_upload"]

    response = choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert (body["zone_code"], body["chapter_code"]) == ("Uh", "Uh")
    chapter = next(c for c in body["document"]["chapters"] if c["code"] == "Uh")
    assert chapter["status"] == "pending" and chapter["sectors"] == ["Uh"]
    jobs = extract_jobs(db_session)
    assert len(jobs) == 1 and jobs[0].payload == {"chapter_id": str(upload_chapter(db_session))}

    # Noch einmal dieselbe Wahl: keine neue Eingabe, kein zweiter Job
    assert (
        choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh").status_code
        == 200
    )
    assert len(extract_jobs(db_session)) == 1
    pending = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert pending["status"] == "in_progress" and [z["code"] for z in pending["zones"]] == ["Uh"]


def test_manual_page_range_and_limits(client: Any, upload_project: str, db_session: Any) -> None:
    state = uploaded(client, upload_project)
    document_id = state["document"]["id"]
    manual = choose(
        client, upload_project, document_id, zone_code="Uh1", chapter_code="U1", first_page=5, last_page=9
    )
    assert manual.status_code == 200, manual.json()
    chapter = next(c for c in manual.json()["document"]["chapters"] if c["code"] == "U1")
    assert chapter["detection"] == "manual" and (chapter["first_page"], chapter["last_page"]) == (5, 9)
    # Ohne eigene Angabe übernimmt das Kapitel die erkannten allgemeinen Seiten
    assert chapter["general_pages"] == [1, 2, 3] and chapter["sectors"] == ["Uh1"]

    outside = choose(client, upload_project, document_id, zone_code="Uh", first_page=20, last_page=30)
    assert outside.status_code == 422 and outside.json()["code"] == "page_out_of_range"
    unknown = choose(client, upload_project, document_id, zone_code="Ub", chapter_code="Ub")
    assert unknown.status_code == 422 and unknown.json()["code"] == "chapter_not_found"
    invalid = choose(client, upload_project, document_id, zone_code="Uh")
    assert invalid.status_code == 422


def test_too_long_chapter_is_refused_before_any_job(
    client: Any, upload_project: str, db_session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(documents, "CHAPTER_MAX_PAGES", 10)
    state = uploaded(client, upload_project)
    response = choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh")
    assert response.status_code == 422 and response.json()["code"] == "chapter_too_long"
    assert extract_jobs(db_session) == []


def test_second_sector_reevaluates_chapter_and_keeps_rules_meanwhile(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    state = uploaded(client, upload_project)
    document_id = state["document"]["id"]
    choose(client, upload_project, document_id, zone_code="Uh", chapter_code="Uh")
    assert evaluate(db_session, settings).status == "succeeded"
    assert client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()["status"] == "ok"

    other = new_project(client)
    upload_regulation(client, other, regulation_fixture()[0])
    body = choose(client, other, document_id, zone_code="Uh1", chapter_code="Uh").json()
    chapter = next(c for c in body["document"]["chapters"] if c["code"] == "Uh")
    assert chapter["sectors"] == ["Uh", "Uh1"] and chapter["status"] == "pending"
    assert len(extract_jobs(db_session)) == 2
    # Das Regelwerk von Uh bleibt wirksam, bis die neue Auswertung fertig ist
    rules = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert rules["status"] == "ok" and "rules_updating" in rules["warnings"]


def test_sector_added_during_extraction_gets_a_follow_up(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    """7.1 Nr. 11: Der Job für den neuen Sektor endet mit `already_running`; der laufende plant nach."""
    state = uploaded(client, upload_project)
    document_id = state["document"]["id"]
    choose(client, upload_project, document_id, zone_code="Uh", chapter_code="Uh")
    chapter_id = upload_chapter(db_session)

    class AddsSectorWhileRunning(FakeExtractor):
        def extract(self, request: Any) -> Any:
            if not self.requests:
                other = new_project(client)
                upload_regulation(client, other, regulation_fixture()[0])
                assert (
                    choose(client, other, document_id, zone_code="Uh1", chapter_code="Uh").status_code == 200
                )
                skipped = extract.extract_chapter(
                    sessions, settings, chapter_id, FakeExtractor([uh_output()]).factory()
                )
                assert skipped.detail == "already_running"
            return super().extract(request)

    outcome = extract.extract_chapter(
        sessions, settings, chapter_id, AddsSectorWhileRunning([uh_output()]).factory()
    )
    assert outcome.status == "succeeded"
    db_session.expire_all()
    chapter = db_session.get(RegulationChapter, chapter_id)
    assert chapter.status == "pending" and chapter.sectors == ["Uh", "Uh1"]
    follow_up = [j for j in extract_jobs(db_session) if (j.idempotency_key or "").endswith(":follow_up")]
    assert len(follow_up) == 1
    # Die Regeln von Uh sind trotzdem geschrieben
    assert client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()["zones"][0]["rules"]


def test_a_model_without_pdf_input_gets_the_text_layer_with_page_marks(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    """PU12: dieselbe Auswertung mit der Textschicht; die Marken zählen wie im PDF-Auszug ab 1, die Zitate
    werden gegen denselben Text geprüft."""
    state = uploaded(client, upload_project)
    choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh")
    chapter_id = upload_chapter(db_session)
    fake = FakeExtractor([uh_output()])
    text_settings = settings.model_copy(update={"rules_input": "text"})
    assert extract.extract_chapter(sessions, text_settings, chapter_id, fake.factory()).status == "succeeded"

    first = fake.requests[0]
    assert first.chapter_pdf == b"" and first.general_pdf is None
    assert first.chapter_text is not None and first.chapter_text.startswith("=== page 1 ===")
    assert first.chapter_text.count("=== page ") == len(first.chapter_pages)
    assert (first.general_text is None) == (not first.general_pages)
    db_session.expire_all()
    chapter = db_session.get(RegulationChapter, chapter_id)
    page_text = db_session.execute(
        select(SourcePage.text).where(
            SourcePage.source_file_id == chapter.source_file_id, SourcePage.page == first.chapter_pages[0]
        )
    ).scalar_one()
    assert page_text.strip() in first.chapter_text
    rules = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert rules["status"] == "ok" and rules["zones"][0]["rules"]
    # Eigene Eingabe, eigener Hash: gespeicherte PDF-Antworten werden nicht für Text verwendet
    db_session.expire_all()
    chapter = db_session.get(RegulationChapter, chapter_id)
    runs = db_session.execute(select(RuleExtractionRun).where(RuleExtractionRun.chapter_id == chapter_id))
    assert {run.input_hash for run in runs.scalars()} == {chapter.input_hash}
    source = db_session.get(SourceFile, chapter.source_file_id)
    assert chapter.input_hash != extract.input_hash(settings, source.sha256, chapter)


# ---------------------------------------------------------------------------
# Regeln und Baurahmen
# ---------------------------------------------------------------------------


def test_rules_and_envelope_for_an_uploaded_site(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    before = client.get(f"/api/v1/admin/projects/{upload_project}/envelope").json()
    assert before["status"] == "unavailable" and before["reason"] == "upload"

    state = uploaded(client, upload_project)
    choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh")
    assert evaluate(db_session, settings).status == "succeeded"

    rules = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert rules["status"] == "ok" and rules["commune_insee"] is None and rules["overlays"] == []
    zone = rules["zones"][0]
    assert (zone["code"], zone["status"], zone["share"]) == ("Uh", "simulated", 1.0)
    street = next(r for r in zone["rules"] if r["kind"] == "setback_street" and r["building_kind"] == "main")
    file_url = state["document"]["file_url"]
    assert street["source_url"] == f"{file_url}#page=9" and street["quote_verified"]

    envelope = client.get(f"/api/v1/admin/projects/{upload_project}/envelope").json()
    assert envelope["status"] in ("ok", "partial"), envelope
    assert [p["zone_code"] for p in envelope["parts"]] == ["Uh"]
    assert "notice.site_without_cadastre" in envelope["notices"]
    assert "notice.cadastre_accuracy" not in envelope["notices"]
    assert envelope["contours"]["lenient"]["area_m2"] > 0

    # Die Datei der Zitate liefert die API inline aus, nur für das Büro
    pdf = client.get(file_url)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline;")
    assert pdf.content == regulation_fixture()[0]


def test_upload_matches_the_gpu_path_for_the_same_parcel(
    client: Any, db_session: Any, tmp_path: Path, settings: Any, flags: None, login_as: Callable[..., Any]
) -> None:
    """PLAN_ANALYSE 7 Punkt 5: AD 65 einmal über Kataster und GPU, einmal mit hochgeladenem Reglement."""
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
    assert (
        import_commune(db_session, DirectoryGpu(gpu_directory(tmp_path)), settings, "44209").status
        == "imported"
    )
    gpu_chapter = db_session.execute(
        select(RegulationChapter.id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(LandUsePlan.gpu_doc_id == DOC_ID)
    ).scalar_one()
    assert extract.extract_chapter(
        sessions, settings, gpu_chapter, FakeExtractor([uh_output()]).factory()
    ).status == ("succeeded")
    gpu_project = new_project(client)
    assert (
        client.put(f"/api/v1/projects/{gpu_project}/site", json={"parcel_idus": [REGULAR]}).status_code == 200
    )

    login_as("architect")
    upload_project = new_project(client)
    assert (
        client.put(f"/api/v1/projects/{upload_project}/site", json={"parcel_idus": [REGULAR]}).status_code
        == 200
    )
    state = uploaded(client, upload_project)
    choose(client, upload_project, state["document"]["id"], zone_code="Uh", chapter_code="Uh")
    assert evaluate(db_session, settings).status == "succeeded"

    via_gpu = client.get(f"/api/v1/admin/projects/{gpu_project}/rules").json()
    via_upload = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert via_gpu["plan"]["origin"] == "gpu" and via_upload["plan"]["origin"] == "upload"

    def values(body: dict[str, Any]) -> list[tuple[Any, ...]]:
        zone = body["zones"][0]
        return sorted(
            (r["kind"], r["building_kind"], r["status"], str(r["params"]))
            for r in zone["rules"] + zone["hints"]
        )

    assert values(via_upload) == values(via_gpu)

    envelope_gpu = client.get(f"/api/v1/admin/projects/{gpu_project}/envelope").json()
    envelope_upload = client.get(f"/api/v1/admin/projects/{upload_project}/envelope").json()
    for reading in ("lenient", "strict"):
        assert envelope_upload["contours"][reading]["area_m2"] == pytest.approx(
            envelope_gpu["contours"][reading]["area_m2"], abs=0.5
        ), reading
    assert [e["lenient_m"] for e in envelope_upload["edges"]] == [
        e["lenient_m"] for e in envelope_gpu["edges"]
    ]


def test_removing_the_document_restores_the_previous_state(
    client: Any, upload_project: str, db_session: Any
) -> None:
    state = uploaded(client, upload_project)
    document_id = state["document"]["id"]
    assert client.delete(f"/api/v1/projects/{upload_project}/regulations/{document_id}").status_code == 204
    assert client.get(f"/api/v1/projects/{upload_project}/regulations").json() == []
    envelope = client.get(f"/api/v1/admin/projects/{upload_project}/envelope").json()
    assert envelope["status"] == "unavailable" and envelope["reason"] == "upload"
    # Das Dokument bleibt für andere Projekte (E-AN2-4), ebenso beim Löschen des Projekts
    upload_regulation(client, upload_project, regulation_fixture()[0])
    assert client.delete(f"/api/v1/projects/{upload_project}").status_code == 204
    db_session.expire_all()
    assert db_session.execute(select(func.count()).select_from(LandUsePlan)).scalar_one() == 1
    assert db_session.execute(select(func.count()).select_from(ProjectRegulation)).scalar_one() == 0


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------


def test_customers_cannot_upload_and_files_need_a_role(
    client: Any, db_session: Any, flags: None, login_as: Callable[..., Any]
) -> None:
    from fastapi.testclient import TestClient

    customer = new_project(client)
    pdf, _pages = regulation_fixture()
    # Kundenprojekt mit Cookie: kein Upload, keine Liste (Kosten, 3.7)
    assert upload_regulation(client, customer, pdf).status_code == 404
    assert client.get(f"/api/v1/projects/{customer}/regulations").status_code == 404

    login_as("architect")
    # Auch der Architekt nicht auf einem Kundenprojekt ohne Eigentümer
    assert upload_regulation(client, customer, pdf).status_code == 404
    own = new_project(client)
    document = upload_regulation(client, own, pdf).json()["document"]
    read_document(document["id"])
    file_url = client.get(f"/api/v1/projects/{own}/regulations").json()[0]["document"]["file_url"]
    assert client.get(file_url).status_code == 200

    anonymous = TestClient(client.app, base_url="http://testserver")
    assert anonymous.get(file_url).status_code == 401
    assert anonymous.get(f"/api/v1/projects/{own}/regulations").status_code == 404
    db_session.expire_all()
    assert db_session.execute(select(func.count()).select_from(RuleExtractionRun)).scalar_one() == 0
