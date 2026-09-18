"""Modul A gegen PostGIS: Kontakt, Codebestätigung, Anfrage, Büro-Sicht, Export und Löschung.

`REGULAR` hat kein importiertes Planwerk: Regeln und Baurahmen bleiben `unavailable`/`not_imported`, was für
diese Tests reicht – die Richtigkeit von G2/G3 selbst ist dort schon getestet. `manual_project` prüft den
Weg ohne Baurahmen (G18/D13, Plan A 3.6) eigenständig.
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.inquiry.texts import PROVISIONAL_TEXTS
from app.integrations.etalab_cadastre import DirectoryCadastre
from app.integrations.ign_bdtopo import DirectoryRoads
from app.platform import legal
from app.platform.models import FeatureFlag, Job, Project
from app.site.cadastre_import import import_commune

FIXTURES = Path(__file__).parents[1] / "fixtures" / "site"
RELEASE = "2026-06-01"
REGULAR = "44209000AD0065"
RECTANGLE_EDGES = [
    {"length_m": 10, "angle_deg": 90},
    {"length_m": 20, "angle_deg": 180},
    {"length_m": 10, "angle_deg": 270},
]
CONTACT_BODY = {"name": "Camille Martin", "email": "camille.martin@example.fr", "lotissement": "no"}


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
    for key in ("site_selection", "inquiry"):
        db_session.add(FeatureFlag(key=key, enabled_for_all=True))
    db_session.commit()


@pytest.fixture
def legal_texts(db_session: Any) -> None:
    for key, locale, title, body in PROVISIONAL_TEXTS:
        legal.publish(
            db_session,
            key=key,
            locale=locale,
            title=title,
            body=body,
            actor_type="system",
            actor_id="test",
        )
    db_session.commit()


@pytest.fixture
def project(client: Any, imported: Any, enabled: None) -> str:
    project_id = str(client.post("/api/v1/projects").json()["id"])
    site = client.put(f"/api/v1/projects/{project_id}/site", json={"parcel_idus": [REGULAR]})
    assert site.status_code == 200
    return project_id


@pytest.fixture
def manual_project(client: Any, enabled: None) -> str:
    project_id = str(client.post("/api/v1/projects").json()["id"])
    body = {"edges": RECTANGLE_EDGES, "address_label": "12 rue imaginaire"}
    assert client.put(f"/api/v1/projects/{project_id}/site", json=body).status_code == 200
    return project_id


def mail_jobs(db_session: Any, template: str) -> list[Any]:
    jobs = db_session.execute(select(Job).where(Job.kind == "mail_send")).scalars().all()
    return [j for j in jobs if j.payload["template"] == template]


def latest_code(db_session: Any) -> str:
    matching = mail_jobs(db_session, "inquiry_code")
    assert matching, "keine passende Mail vorgemerkt"
    return str(matching[-1].payload["params"]["code"])


# ---------------------------------------------------------------------------
# Kontakt und Codebestätigung
# ---------------------------------------------------------------------------


def test_contact_then_confirm_creates_inquiry(
    client: Any, project: str, db_session: Any, legal_texts: None
) -> None:
    contact = client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    assert contact.status_code == 202, contact.json()
    assert contact.json()["code_expires_in_minutes"] == 10

    code = latest_code(db_session)
    confirm = client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    )
    assert confirm.status_code == 201, confirm.json()
    number = confirm.json()["number"]
    assert number.startswith("EMP-") and confirm.json()["status"] == "submitted"

    mine = client.get(f"/api/v1/projects/{project}/inquiry").json()
    assert mine == {"exists": True, "number": number, "status": "neu"}

    db_session.expire_all()
    project_row = db_session.get(Project, project)
    assert project_row.status == "submitted"

    office_mail = mail_jobs(db_session, "inquiry_office")
    customer_mail = mail_jobs(db_session, "inquiry_customer_copy")
    assert office_mail and office_mail[0].payload["to"] == get_settings().office_email
    assert customer_mail and customer_mail[0].payload["to"] == "camille.martin@example.fr"
    assert office_mail[0].payload["params"]["envelope_status"] == "unavailable"


def test_confirm_requires_both_consents(
    client: Any, project: str, db_session: Any, legal_texts: None
) -> None:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    code = latest_code(db_session)
    confirm = client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": False},
    )
    assert confirm.status_code == 400 and confirm.json()["code"] == "consent_required"


def test_confirm_without_contact_fails(client: Any, project: str) -> None:
    confirm = client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": "123456", "simulation_confirmation": True, "transmission_office": True},
    )
    assert confirm.status_code == 409 and confirm.json()["code"] == "inquiry_contact_missing"


def test_confirm_without_legal_texts_fails(client: Any, project: str, db_session: Any) -> None:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    code = latest_code(db_session)
    confirm = client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    )
    assert confirm.status_code == 503 and confirm.json()["code"] == "legal_text_missing"


def test_wrong_code_counts_attempts_then_blocks(
    client: Any, project: str, db_session: Any, legal_texts: None
) -> None:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    body = {"code": "000000", "simulation_confirmation": True, "transmission_office": True}
    for _ in range(get_settings().inquiry_code_max_attempts):
        wrong = client.post(f"/api/v1/projects/{project}/inquiry/confirm", json=body)
        assert wrong.status_code == 400 and wrong.json()["code"] == "inquiry_code_invalid"
    blocked = client.post(f"/api/v1/projects/{project}/inquiry/confirm", json=body)
    assert blocked.status_code == 429 and blocked.json()["code"] == "inquiry_code_too_many_attempts"


def test_second_contact_after_inquiry_is_rejected(
    client: Any, project: str, db_session: Any, legal_texts: None
) -> None:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    code = latest_code(db_session)
    client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    )
    again = client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    assert again.status_code == 409 and again.json()["code"] == "inquiry_already_exists"


def test_contact_rate_limited_by_email(client: Any, project: str) -> None:
    url = f"/api/v1/projects/{project}/inquiry/contact"
    limit = get_settings().inquiry_contact_limit_per_hour_email
    for _ in range(limit):
        assert client.post(url, json=CONTACT_BODY).status_code == 202
    assert client.post(url, json=CONTACT_BODY).status_code == 429


def test_inquiry_without_baurahmen(
    client: Any, manual_project: str, db_session: Any, legal_texts: None
) -> None:
    """G18/D13: Anfrage auch ohne Baurahmen (hier Weg E) möglich (Plan A 3.6)."""
    contact = client.post(f"/api/v1/projects/{manual_project}/inquiry/contact", json=CONTACT_BODY)
    assert contact.status_code == 202
    code = latest_code(db_session)
    confirm = client.post(
        f"/api/v1/projects/{manual_project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    )
    assert confirm.status_code == 201, confirm.json()


# ---------------------------------------------------------------------------
# Export und Löschung (Spez. 10.2)
# ---------------------------------------------------------------------------


def test_export_and_delete_before_inquiry(client: Any, project: str) -> None:
    export = client.get(f"/api/v1/projects/{project}/export").json()
    assert export["customer"] is None and export["inquiry_number"] is None
    assert client.delete(f"/api/v1/projects/{project}").status_code == 204
    assert client.get(f"/api/v1/projects/{project}/export").status_code == 404


def test_delete_after_inquiry_requires_office(
    client: Any, project: str, db_session: Any, legal_texts: None
) -> None:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    code = latest_code(db_session)
    client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    )
    export = client.get(f"/api/v1/projects/{project}/export").json()
    assert export["customer"]["email"] == "camille.martin@example.fr"
    assert export["inquiry_number"] is not None and export["snapshot"] is not None

    deletion = client.delete(f"/api/v1/projects/{project}")
    assert deletion.status_code == 409 and deletion.json()["code"] == "deletion_requires_office"


# ---------------------------------------------------------------------------
# Büro
# ---------------------------------------------------------------------------


def submit_and_confirm(client: Any, project: str, db_session: Any) -> str:
    client.post(f"/api/v1/projects/{project}/inquiry/contact", json=CONTACT_BODY)
    code = latest_code(db_session)
    number = client.post(
        f"/api/v1/projects/{project}/inquiry/confirm",
        json={"code": code, "simulation_confirmation": True, "transmission_office": True},
    ).json()["number"]
    return number


def test_office_list_detail_and_status_patch(
    client: Any, project: str, db_session: Any, legal_texts: None, login_as: Any
) -> None:
    number = submit_and_confirm(client, project, db_session)

    login_as("architect")
    listed = client.get("/api/v1/admin/inquiries").json()
    assert [i["number"] for i in listed] == [number]
    assert listed[0]["has_envelope"] is False and listed[0]["lotissement"] == "no"

    detail = client.get(f"/api/v1/admin/projects/{project}/inquiry").json()
    assert detail["number"] == number and detail["status"] == "neu"
    assert detail["customer"]["name"] == "Camille Martin"
    assert {c["kind"] for c in detail["consents"]} == {"simulation_confirmation", "transmission_office"}

    patched = client.patch(f"/api/v1/admin/projects/{project}/inquiry", json={"status": "in_bearbeitung"})
    assert patched.status_code == 200 and patched.json()["status"] == "in_bearbeitung"
    filtered = client.get("/api/v1/admin/inquiries?status=in_bearbeitung").json()
    assert [i["number"] for i in filtered] == [number]
    assert client.get("/api/v1/admin/inquiries?status=neu").json() == []


def test_office_routes_require_role(
    client: Any, project: str, db_session: Any, legal_texts: None, login_as: Any
) -> None:
    submit_and_confirm(client, project, db_session)
    login_as("catalog_admin")
    assert client.get("/api/v1/admin/inquiries").status_code == 403
    assert client.get(f"/api/v1/admin/projects/{project}/inquiry").status_code == 403
