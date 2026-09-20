"""Modul V gegen PostGIS: Übergabe mit Neuprüfung, Fassungen, Dossier, Nachrichten, Zugangslink
(docs/PLAN_V_VORENTWURF_UEBERGABE.md 6).

Grundstück AD 65 (Zone Uh) mit dem Katalog des H3-Tests (`preisig` 12 × 8 m, Linien `base`/`confort`,
Optionen mit Preisen, veröffentlichter Preiskatalog).
"""

import io
import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.inquiry.models import Consent, Inquiry
from app.inquiry.texts import PROVISIONAL_TEXTS as INQUIRY_TEXTS
from app.platform import legal
from app.platform.jobs.registry import JobContext
from app.platform.models import FeatureFlag, Job
from app.submission.jobs import dossier_generate
from app.submission.models import Submission
from app.submission.texts import PROVISIONAL_TEXTS as DESIGN_TEXTS
from tests.integration import test_configuration_options as _options
from tests.integration.test_configuration import url
from tests.integration.test_inquiry import CONTACT_BODY, latest_code, mail_jobs

# Fixtures des H3-Tests (Grundstück AD 65, Typen, Linien, Optionen, Preiskatalog)
catalog = _options.catalog
configurator = _options.configurator
memory_storage = _options.memory_storage
offers = _options.offers
project = _options.project
sessions = _options.sessions
settings = _options.settings


@pytest.fixture
def flags(db_session: Any) -> None:
    for key in ("inquiry", "submission"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def texts(db_session: Any) -> None:
    for key, locale, title, body in [*INQUIRY_TEXTS, *DESIGN_TEXTS]:
        legal.publish(
            db_session, key=key, locale=locale, title=title, body=body, actor_type="system", actor_id="test"
        )
    db_session.commit()


@pytest.fixture
def ready(client: Any, project: str, offers: None, configurator: None, flags: None, texts: None) -> str:
    """Typ `preisig` mit Linie `base` und Terrasse, gespeichert."""
    response = _options.select(client, project, package_slug="base", option_slugs=["terrasse"])
    assert response.status_code == 200, response.text
    return project


def stamp(client: Any, project: str) -> str:
    body = client.get(url(project, "configuration")).json()
    assert body["review_stamp"], body
    return str(body["review_stamp"])


def submit(client: Any, project: str, review_stamp: str, **extra: Any) -> Any:
    body = {"review_stamp": review_stamp, "design_confirmation": True, "transmission_design": True, **extra}
    return client.post(url(project, "submission"), json=body)


def first_submission(client: Any, project: str, db_session: Any) -> dict[str, Any]:
    assert client.post(url(project, "inquiry/contact"), json=CONTACT_BODY).status_code == 202
    response = submit(client, project, stamp(client, project), code=latest_code(db_session))
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def run_dossier(db_session: Any, project: str, sequence: int = 1) -> Submission:
    db_session.expire_all()
    row = db_session.execute(
        select(Submission).where(Submission.project_id == uuid.UUID(project), Submission.sequence == sequence)
    ).scalar_one()
    dossier_generate(
        JobContext(job_id=uuid.uuid4(), attempt=1, project_id=row.project_id), {"submission_id": str(row.id)}
    )
    db_session.expire_all()
    return db_session.get(Submission, row.id)


def override(db_session: Any, project: str, kind: str, params: dict[str, Any]) -> None:
    from app.rules import service as rules_service
    from app.rules.schemas import ProjectOverrideIn

    rules_service.set_override(
        db_session,
        uuid.UUID(project),
        ProjectOverrideIn(zone_code="Uh", kind=kind, status="effective", params=params, note="Test"),
        "tester",
    )
    db_session.commit()


# ---------------------------------------------------------------------------
# Prüfstempel
# ---------------------------------------------------------------------------


def test_review_stamp_is_stable_and_names_its_parts(client: Any, ready: str) -> None:
    first, second = stamp(client, ready), stamp(client, ready)
    assert first == second and first.startswith("v1:")
    assert [part.split("=")[0] for part in first.removeprefix("v1:").split(".")] == [
        "site",
        "rules",
        "catalog",
        "configuration",
        "result",
        "engine",
    ]
    # Die Antwort auf PATCH trägt denselben Stempel wie der nächste Abruf (ohne `dropped`)
    patched = _options.select(client, ready, option_slugs=["terrasse", "pv"]).json()
    assert patched["review_stamp"] == stamp(client, ready)


def test_submission_needs_type_placement_and_line(
    client: Any, project: str, offers: None, configurator: None, flags: None, texts: None
) -> None:
    empty = submit(client, project, "v1:egal")
    assert empty.status_code == 409 and set(empty.json()["missing"]) == {"type", "placement"}
    typed = _options.select(client, project).json()
    no_line = submit(client, project, typed["review_stamp"])
    assert no_line.status_code == 409 and no_line.json()["missing"] == ["package"], no_line.text


def test_submission_needs_both_confirmations(client: Any, ready: str) -> None:
    body = {"review_stamp": stamp(client, ready), "design_confirmation": True, "transmission_design": False}
    response = client.post(url(ready, "submission"), json=body)
    assert response.status_code == 400 and response.json()["code"] == "consent_required"


def test_submission_is_behind_its_flag(
    client: Any, project: str, offers: None, configurator: None, texts: None
) -> None:
    response = submit(client, project, "v1:egal")
    assert response.status_code == 403 and response.json()["code"] == "feature_disabled"


# ---------------------------------------------------------------------------
# Übergabe
# ---------------------------------------------------------------------------


def test_new_customer_submits_with_code_and_gets_case_version_and_mails(
    client: Any, ready: str, db_session: Any
) -> None:
    assert client.post(url(ready, "inquiry/contact"), json=CONTACT_BODY).status_code == 202
    seen = stamp(client, ready)
    without_code = submit(client, ready, seen)
    assert without_code.status_code == 400 and without_code.json()["code"] == "inquiry_code_invalid"
    response = submit(client, ready, seen, code=latest_code(db_session))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["number"].startswith("EMP-") and body["sequence"] == 1

    mine = client.get(url(ready, "inquiry")).json()
    assert mine["exists"] is True and mine["status"] == "neu" and mine["number"] == body["number"]
    assert [s["sequence"] for s in mine["submissions"]] == [1]
    assert mine["submissions"][0]["dossier_status"] == "pending" and mine["can_withdraw"] is True

    db_session.expire_all()
    row = db_session.execute(select(Submission)).scalar_one()
    assert row.status == "current" and row.review_stamp == seen and row.deviation_count == 0
    snapshot = row.snapshot
    assert snapshot["schema_version"] == 2 and snapshot["configuration"]["review_stamp"] == seen
    assert snapshot["catalog"]["type"]["slug"] == "preisig"
    assert snapshot["catalog"]["package"]["slug"] == "base"
    assert [o["slug"] for o in snapshot["catalog"]["options"]] == ["terrasse"]
    assert snapshot["customer"]["email"] == CONTACT_BODY["email"]
    assert snapshot["site"]["origin"] == "parcel" and snapshot["envelope"]["status"] in ("ok", "partial")
    # L1: kein Feld, das als Gesamtpreis gelesen werden kann
    assert "total" not in str(snapshot["configuration"]["costs"])
    consents = db_session.execute(select(Consent).where(Consent.submission_id == row.id)).scalars().all()
    assert {c.kind for c in consents} == {"design_confirmation", "transmission_design"}

    office = mail_jobs(db_session, "submission_office")
    customer = mail_jobs(db_session, "submission_customer")
    assert len(office) == 1 and len(customer) == 1
    assert office[0].payload["params"]["number"] == body["number"]
    assert "/zugang#t=" in customer[0].payload["params"]["access_url"]
    jobs = db_session.execute(select(Job).where(Job.kind == "dossier_generate")).scalars().all()
    assert len(jobs) == 1 and jobs[0].payload == {"submission_id": str(row.id)}


def test_rule_change_between_viewing_and_submitting_is_detected(
    client: Any, ready: str, db_session: Any
) -> None:
    assert client.post(url(ready, "inquiry/contact"), json=CONTACT_BODY).status_code == 202
    seen = stamp(client, ready)
    override(db_session, ready, "max_footprint_ratio", {"ratio": 0.9})
    code = latest_code(db_session)
    changed = submit(client, ready, seen, code=code)
    assert changed.status_code == 409, changed.text
    problem = changed.json()
    assert problem["code"] == "review_changed" and "rules" in problem["changes"]
    assert problem["review_stamp"] == stamp(client, ready)
    # Die Ablehnung hat den Code nicht verbraucht (Plan V 9.1 Nr. 3)
    again = submit(client, ready, problem["review_stamp"], code=code)
    assert again.status_code == 201, again.text


def test_double_submit_returns_the_same_version(client: Any, ready: str, db_session: Any) -> None:
    first = first_submission(client, ready, db_session)
    repeated = submit(client, ready, stamp(client, ready))
    assert repeated.status_code == 201 and repeated.json() == first
    db_session.expire_all()
    assert len(db_session.execute(select(Submission)).scalars().all()) == 1
    assert len(mail_jobs(db_session, "submission_office")) == 1


def test_resubmission_supersedes_the_previous_version(client: Any, ready: str, db_session: Any) -> None:
    first = first_submission(client, ready, db_session)
    assert _options.select(client, ready, option_slugs=["terrasse", "pv"]).status_code == 200
    second = submit(client, ready, stamp(client, ready))
    assert second.status_code == 201, second.text
    assert second.json() == {"number": first["number"], "sequence": 2, "status": "submitted"}
    db_session.expire_all()
    rows = {s.sequence: s for s in db_session.execute(select(Submission)).scalars()}
    assert rows[1].status == "superseded" and rows[2].status == "current"
    assert rows[2].supersedes_id == rows[1].id
    assert (
        len(db_session.execute(select(Consent).where(Consent.submission_id.is_not(None))).scalars().all())
        == 4
    )
    assert len(mail_jobs(db_session, "submission_office")) == 2


def test_deviations_need_an_explicit_acknowledgement(client: Any, ready: str, db_session: Any) -> None:
    assert client.post(url(ready, "inquiry/contact"), json=CONTACT_BODY).status_code == 202
    override(db_session, ready, "max_footprint_ratio", {"ratio": 0.001})
    configuration = client.get(url(ready, "configuration")).json()
    assert configuration["fit"]["allowed"] is False
    code = latest_code(db_session)
    refused = submit(client, ready, configuration["review_stamp"], code=code)
    assert refused.status_code == 409 and refused.json()["code"] == "deviations_not_acknowledged"
    assert "footprint" in {c["code"] for c in refused.json()["checks"]}
    accepted = submit(client, ready, configuration["review_stamp"], code=code, deviations_acknowledged=True)
    assert accepted.status_code == 201, accepted.text
    db_session.expire_all()
    row = db_session.execute(select(Submission)).scalar_one()
    assert row.deviations_acknowledged is True and row.deviation_count >= 1
    assert row.snapshot["deviations"]


def test_case_from_the_quick_inquiry_gets_a_version_without_code(
    client: Any, ready: str, db_session: Any
) -> None:
    assert client.post(url(ready, "inquiry/contact"), json=CONTACT_BODY).status_code == 202
    confirm = {"code": latest_code(db_session), "simulation_confirmation": True, "transmission_office": True}
    number = client.post(url(ready, "inquiry/confirm"), json=confirm).json()["number"]
    db_session.execute(select(Inquiry)).scalar_one().status = "beantwortet"
    db_session.commit()
    response = submit(client, ready, stamp(client, ready))
    assert response.status_code == 201, response.text
    assert response.json()["number"] == number and response.json()["sequence"] == 1
    assert client.get(url(ready, "inquiry")).json()["status"] == "neu"


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------


def test_dossier_job_writes_pdfs_and_dxf_in_both_systems(
    client: Any, ready: str, db_session: Any, memory_storage: dict[str, bytes], login_as: Any
) -> None:
    import ezdxf

    first_submission(client, ready, db_session)
    row = run_dossier(db_session, ready)
    assert row.dossier_status == "ready"
    names = {f["name"]: f for f in row.dossier_files}
    number = row.snapshot["number"]
    assert set(names) == {
        f"{number}_F1_fr.pdf",
        f"{number}_F1_de.pdf",
        f"{number}_F1_L93.dxf",
        f"{number}_F1_local.dxf",
    }
    for entry in names.values():
        assert memory_storage[entry["storage_key"]]
    assert memory_storage[names[f"{number}_F1_fr.pdf"]["storage_key"]].startswith(b"%PDF")

    origin = row.snapshot["site"]["local_origin"]
    facade = row.snapshot["configuration"]["evaluation"]["facade_local"]
    l93 = ezdxf.read(io.StringIO(memory_storage[names[f"{number}_F1_L93.dxf"]["storage_key"]].decode()))
    local = ezdxf.read(io.StringIO(memory_storage[names[f"{number}_F1_local.dxf"]["storage_key"]].decode()))
    for doc in (l93, local):
        assert {"PARCELLE", "MAISON_FACADE", "TERRASSE", "LIMITE_VOIE"} <= {
            layer.dxf.name for layer in doc.layers
        }
    house_l93 = next(iter(l93.modelspace().query('LWPOLYLINE[layer=="MAISON_FACADE"]')))
    house_local = next(iter(local.modelspace().query('LWPOLYLINE[layer=="MAISON_FACADE"]')))
    first_l93, first_local = house_l93.get_points("xy")[0], house_local.get_points("xy")[0]
    assert first_local == pytest.approx(tuple(facade[0]), abs=0.001)
    assert first_l93 == pytest.approx((first_local[0] + origin["e"], first_local[1] + origin["n"]), abs=0.001)

    # Kunde: nur PDFs; Büro: alles
    pdf = client.get(url(ready, f"submissions/1/files/{number}_F1_de.pdf"))
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert client.get(url(ready, f"submissions/1/files/{number}_F1_L93.dxf")).status_code == 404
    login_as("architect")
    dxf = client.get(f"/api/v1/admin/projects/{ready}/submissions/1/files/{number}_F1_L93.dxf")
    assert dxf.status_code == 200
    detail = client.get(f"/api/v1/admin/projects/{ready}/inquiry").json()
    current = detail["submissions"][0]
    assert current["dossier_status"] == "ready" and len(current["files"]) == 4
    assert current["summary"]["type_name"] and current["summary"]["costs_display"]
    assert detail["configuration_revision"] == current["configuration_revision"]


def test_failed_dossier_can_be_regenerated_by_the_office(
    client: Any, ready: str, db_session: Any, memory_storage: dict[str, bytes], login_as: Any
) -> None:
    first_submission(client, ready, db_session)
    db_session.expire_all()
    row = db_session.execute(select(Submission)).scalar_one()
    login_as("architect")
    not_failed = client.post(f"/api/v1/admin/projects/{ready}/submissions/1/dossier")
    assert not_failed.status_code == 409
    row.dossier_status, row.dossier_error = "failed", "RuntimeError: Test"
    db_session.commit()
    response = client.post(f"/api/v1/admin/projects/{ready}/submissions/1/dossier")
    assert response.status_code == 202
    assert response.json()["submissions"][0]["dossier_status"] == "pending"
    jobs = db_session.execute(select(Job).where(Job.kind == "dossier_generate")).scalars().all()
    assert len(jobs) == 2


# ---------------------------------------------------------------------------
# Nachrichten, Zustände, Zurückziehen
# ---------------------------------------------------------------------------


def test_messages_move_the_case_between_states(
    client: Any, ready: str, db_session: Any, login_as: Any
) -> None:
    first_submission(client, ready, db_session)
    login_as("architect")
    office = client.post(
        f"/api/v1/admin/projects/{ready}/inquiry/messages", json={"body": "Wie breit ist die Zufahrt?"}
    )
    assert office.status_code == 201 and office.json()["status"] == "rueckfrage"
    mail = mail_jobs(db_session, "message_customer")[-1]
    assert mail.payload["params"]["body"] == "Wie breit ist die Zufahrt?"
    assert "/zugang#t=" in mail.payload["params"]["access_url"]

    answer = client.post(url(ready, "inquiry/messages"), json={"body": "Etwa 3 Meter."})
    assert answer.status_code == 201
    body = answer.json()
    assert body["status"] == "in_bearbeitung"
    assert [m["author"] for m in body["messages"]] == ["office", "customer"]
    assert mail_jobs(db_session, "message_office")

    refused = client.patch(f"/api/v1/admin/projects/{ready}/inquiry", json={"status": "zurueckgezogen"})
    assert refused.status_code == 422
    withdrawn = client.post(url(ready, "inquiry/withdraw"))
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "zurueckgezogen"
    assert withdrawn.json()["can_withdraw"] is False
    assert mail_jobs(db_session, "withdrawn_office")
    late = client.post(url(ready, "inquiry/messages"), json={"body": "Doch noch?"})
    assert late.status_code == 409 and late.json()["code"] == "inquiry_withdrawn"
    # Eine neue Fassung öffnet den Vorgang wieder
    assert _options.select(client, ready, option_slugs=["terrasse", "pv"]).status_code == 200
    assert submit(client, ready, stamp(client, ready)).status_code == 201
    assert client.get(url(ready, "inquiry")).json()["status"] == "neu"


def test_office_list_shows_versions_and_deviations(
    client: Any, ready: str, db_session: Any, login_as: Any
) -> None:
    first_submission(client, ready, db_session)
    login_as("architect")
    items = client.get("/api/v1/admin/inquiries").json()
    assert len(items) == 1
    assert items[0]["submissions"] == 1 and items[0]["deviation_count"] == 0
    assert items[0]["dossier_status"] == "pending"
    assert client.get("/api/v1/admin/inquiries", params={"status": "rueckfrage"}).json() == []


def test_export_contains_versions_and_messages(client: Any, ready: str, db_session: Any) -> None:
    first_submission(client, ready, db_session)
    assert client.post(url(ready, "inquiry/messages"), json={"body": "Frage"}).status_code == 201
    exported = client.get(url(ready, "export")).json()
    assert [s["sequence"] for s in exported["submissions"]] == [1]
    assert exported["submissions"][0]["snapshot"]["schema_version"] == 2
    assert [m["body"] for m in exported["messages"]] == ["Frage"]
    assert {c["kind"] for c in exported["consents"]} == {"design_confirmation", "transmission_design"}
    assert client.delete(f"/api/v1/projects/{ready}").status_code == 409


# ---------------------------------------------------------------------------
# Zugangslink
# ---------------------------------------------------------------------------


def _token(db_session: Any) -> str:
    access_url = mail_jobs(db_session, "submission_customer")[-1].payload["params"]["access_url"]
    return str(access_url.split("#t=", 1)[1])


def test_access_link_replaces_the_project_cookie(app: Any, client: Any, ready: str, db_session: Any) -> None:
    from fastapi.testclient import TestClient

    first_submission(client, ready, db_session)
    token = _token(db_session)
    with TestClient(app, base_url="http://testserver") as other:
        other.get("/api/v1/session")
        other.headers["X-CSRF-Token"] = other.cookies["emprise_csrf"]
        assert other.get(url(ready, "inquiry")).status_code == 404
        redeemed = other.post("/api/v1/access/redeem", json={"token": token})
        assert redeemed.status_code == 200 and redeemed.json()["project_id"] == ready
        assert other.get(url(ready, "inquiry")).json()["exists"] is True
        forged = other.post("/api/v1/access/redeem", json={"token": token[:-2] + "AA"})
        assert forged.status_code == 400 and forged.json()["code"] == "access_link_invalid"
    # Das bisherige Cookie gilt nicht mehr (E-V5)
    assert client.get(url(ready, "inquiry")).status_code == 404


def test_expired_access_link_is_refused(client: Any, ready: str, db_session: Any, monkeypatch: Any) -> None:
    from app.inquiry import access

    first_submission(client, ready, db_session)
    monkeypatch.setattr(access.get_settings(), "access_link_days", -1)
    expired = access.make_token(uuid.UUID(ready))
    response = client.post("/api/v1/access/redeem", json={"token": expired})
    assert response.status_code == 400 and response.json()["reason"] == "expired"


def test_requesting_a_link_does_not_reveal_the_address(client: Any, ready: str, db_session: Any) -> None:
    unknown = client.post("/api/v1/access/request", json={"email": "niemand@example.fr"})
    assert unknown.status_code == 202 and unknown.json() == {"status": "accepted"}
    assert mail_jobs(db_session, "access_link") == []
    first_submission(client, ready, db_session)
    known = client.post("/api/v1/access/request", json={"email": CONTACT_BODY["email"].upper()})
    assert known.status_code == 202 and known.json() == unknown.json()
    links = mail_jobs(db_session, "access_link")
    assert len(links) == 1 and "/zugang#t=" in links[0].payload["params"]["access_url"]
