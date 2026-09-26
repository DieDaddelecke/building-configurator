"""Analyse für den Entwurf und Zusatzdokumente (AN3, docs/PLAN_AN3_ANALYSE.md) gegen PostGIS.

Grundlage wie in AN2: Parzelle 20 × 30 m aus einer DXF-Datei, das Test-Reglement mit Zone Uh und die
aufgezeichnete Modellantwort (GRZ 25 %, Traufe 7 m, First 10 m). Dazu ein kleines règlement de lotissement
mit einer Tabelle je Lot. Die App läuft als Produkt „Emprise Analyse“.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.rules import documents, extract
from app.rules.models import LandUsePlan, RegulationChapter, Rule, RuleSet, RuleSetVersion
from tests.integration import test_rules_upload as an2
from tests.integration.test_rules_upload import (
    choose,
    evaluate,
    extract_jobs,
    new_project,
    read_document,
    sessions,
    upload_regulation,
    uploaded,
)
from tests.rules_support import FakeExtractor, regulation_fixture, rule, text_pdf

# Fixtures aus AN2: Speicher im Arbeitsspeicher, Schlüssel der Claude API, Flags, angemeldeter Architekt und
# sein Projekt mit einer Parzelle aus einer DXF-Datei. Pytest nimmt den Namen der Zuweisung.
memory_storage = an2.memory_storage
settings = an2.settings
flags = an2.flags
architect = an2.architect
upload_project = an2.upload_project

LOT_PAGES = [
    "RÈGLEMENT DU LOTISSEMENT LES CHÊNES\n"
    "Article 1 - Objet. Le présent règlement s'applique aux lots 1 à 20 du lotissement.",
    "Article 7 - Implantation par rapport aux limites séparatives : non réglementé.\n"
    "Article 10 - Hauteur. La hauteur des constructions ne doit pas excéder 8 mètres au faîtage.\n"
    "Article 11 - Clôtures. Les clôtures sur rue seront constituées de haies vives d'essences locales.",
    "Article 14 - Surfaces. Lot 12 : surface de plancher maximale 180 m², emprise au sol maximale 120 m².\n"
    "Lot 7 : surface de plancher maximale 150 m², emprise au sol maximale 100 m².",
]


@pytest.fixture
def app(clean_db: None) -> Any:
    from app.main import create_app

    return create_app(get_settings().model_copy(update={"product": "analyse"}))


def lot_output(sector: str = "Lot-12") -> dict[str, Any]:
    """Antwort des Modells auf das Zusatzdokument; Seiten sind Positionen im PDF (= Originalseiten)."""
    return {
        "remarks": "",
        "rules": [
            rule(
                sector,
                "max_height",
                {"ridge_m": 8},
                "La hauteur des constructions ne doit pas excéder 8 mètres au faîtage.",
                2,
            ),
            rule(
                sector,
                "setback_side",
                {},
                "Article 7 - Implantation par rapport aux limites séparatives : non réglementé.",
                2,
                status="not_regulated",
            ),
            rule(
                sector,
                "max_area",
                {"sdp_m2": 180, "footprint_m2": 120},
                "Lot 12 : surface de plancher maximale 180 m², emprise au sol maximale 120 m².",
                3,
                building_kind="any",
            ),
            rule(
                sector,
                "text_only",
                {"summary": "Clôtures sur rue en haies vives d'essences locales."},
                "Les clôtures sur rue seront constituées de haies vives d'essences locales.",
                2,
                building_kind="any",
                status="text_only",
            ),
        ],
    }


def with_plu(client: Any, project: str, db_session: Any, settings: Any) -> None:
    state = uploaded(client, project)
    assert (
        choose(client, project, state["document"]["id"], zone_code="Uh", chapter_code="Uh").status_code == 200
    )
    assert evaluate(db_session, settings).status == "succeeded"


def upload_lot_document(client: Any, project: str, pages: list[str] = LOT_PAGES, **form: Any) -> str:
    response = upload_regulation(
        client,
        project,
        text_pdf(pages),
        name="lotissement.pdf",
        title=form.pop("title", "Règlement du lotissement Les Chênes"),
        du_type=form.pop("du_type", "lotissement"),
    )
    assert response.status_code == 202, response.json()
    assert response.json()["role"] == "supplement"
    document_id: str = response.json()["document"]["id"]
    assert read_document(document_id, "lotissement.pdf")["status"] == "active"
    return document_id


def choose_lot(client: Any, project: str, document_id: str, **body: Any) -> Any:
    return client.put(f"/api/v1/projects/{project}/regulations/{document_id}/lot", json=body)


def doc_chapter(db_session: Any, document_id: str) -> RegulationChapter:
    db_session.expire_all()
    return db_session.execute(
        select(RegulationChapter).where(
            RegulationChapter.land_use_plan_id == uuid.UUID(document_id),
            RegulationChapter.code == documents.SUPPLEMENT_CHAPTER,
        )
    ).scalar_one()


def evaluate_lots(db_session: Any, settings: Any, document_id: str, extractor: FakeExtractor) -> None:
    outcome = extract.extract_chapter(
        sessions, settings, doc_chapter(db_session, document_id).id, extractor.factory()
    )
    assert outcome.status == "succeeded", outcome
    db_session.expire_all()


# ---------------------------------------------------------------------------
# Zusatzdokumente (3.7)
# ---------------------------------------------------------------------------


def test_supplement_is_read_as_one_document_chapter_without_costs(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    jobs_before = len(extract_jobs(db_session))
    document_id = upload_lot_document(client, upload_project)
    assert doc_chapter(db_session, document_id).sectors == []

    listed = client.get(f"/api/v1/projects/{upload_project}/regulations").json()
    assert [item["role"] for item in listed] == ["plu", "supplement"]
    supplement = listed[1]
    assert supplement["document"]["du_type"] == "lotissement" and supplement["zone_code"] is None
    chapters = supplement["document"]["chapters"]
    assert [(c["code"], c["first_page"], c["last_page"], c["detection"], c["status"]) for c in chapters] == [
        ("DOC", 1, 3, "document", "idle")
    ]
    assert len(extract_jobs(db_session)) == jobs_before
    # Das PLU bleibt die Grundlage von Regeln und Baurahmen
    rules = client.get(f"/api/v1/admin/projects/{upload_project}/rules").json()
    assert [zone["code"] for zone in rules["zones"]] == ["Uh"]


def test_lot_choice_evaluates_with_the_supplement_prompt(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    with_plu(client, upload_project, db_session, settings)
    document_id = upload_lot_document(client, upload_project)
    jobs_before = len(extract_jobs(db_session))

    response = choose_lot(client, upload_project, document_id, lot="12")
    assert response.status_code == 200, response.json()
    assert (response.json()["zone_code"], response.json()["chapter_code"]) == ("Lot-12", "DOC")
    assert len(extract_jobs(db_session)) == jobs_before + 1
    chapter = doc_chapter(db_session, document_id)
    assert (chapter.status, chapter.sectors) == ("pending", ["Lot-12"])

    fake = FakeExtractor([lot_output()])
    evaluate_lots(db_session, settings, document_id, fake)
    assert {request.document_kind for request in fake.requests} == {"supplement"}
    assert fake.requests[0].general_pdf is None and fake.requests[0].sectors == ["Lot-12"]
    # Keine Pflichtarten: nur, was das Dokument regelt (3.7, 7.1 Nr. 4)
    stored = db_session.execute(
        select(Rule.kind, Rule.status)
        .join(RuleSetVersion, RuleSetVersion.id == Rule.rule_set_version_id)
        .join(RuleSet, RuleSet.id == RuleSetVersion.rule_set_id)
        .where(RuleSet.land_use_plan_id == uuid.UUID(document_id), RuleSet.zone_code == "Lot-12")
    ).all()
    assert sorted(stored) == [
        ("max_area", "effective"),
        ("max_height", "effective"),
        ("setback_side", "not_regulated"),
        ("text_only", "text_only"),
    ]
    analysis = client.get(f"/api/v1/projects/{upload_project}/analysis").json()
    supplement = analysis["supplements"][0]
    assert (supplement["lot"], supplement["status"], supplement["du_type"]) == (
        "Lot-12",
        "simulated",
        "lotissement",
    )
    verdicts = {c["kind"]: c["verdict"] for c in supplement["comparisons"]}
    assert verdicts == {
        "max_area": "only_supplement",
        "max_height": "stricter",
        "setback_side": "no_own_rule",
    }
    height = next(c for c in supplement["comparisons"] if c["kind"] == "max_height")
    assert height["supplement"]["params"] == {
        "ridge_m": 8.0,
        "reference": "natural_terrain",
        "measured_at": "highest_point",
        "includes_roof_installations": False,
    }
    assert height["plu"]["params"]["ridge_m"] == 10.0
    assert height["supplement"]["citation"]["source_url"].endswith("#page=2")
    assert [hint["params"]["summary"] for hint in supplement["hints"]] == [
        "Clôtures sur rue en haies vives d'essences locales."
    ]
    assert analysis["supplement_stricter"] == ["max_area", "max_height"]
    assert analysis["warnings"] == ["supplement_stricter"]
    # Nicht verrechnet: die Kennzahlen bleiben die des PLU (E-AN3-2)
    assert analysis["floor_area"]["high_m2"] == 380


def test_second_lot_in_another_project_reevaluates_the_same_document(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    document_id = upload_lot_document(client, upload_project)
    assert choose_lot(client, upload_project, document_id, lot="12").status_code == 200

    other = new_project(client)
    again = upload_regulation(client, other, text_pdf(LOT_PAGES), du_type="lotissement")
    assert again.json()["document"]["id"] == document_id
    assert choose_lot(client, other, document_id, lot="7").status_code == 200
    assert doc_chapter(db_session, document_id).sectors == ["Lot-12", "Lot-7"]
    assert len(extract_jobs(db_session)) == 2
    # Ohne Lot: das Dokument als Ganzes
    third = new_project(client)
    upload_regulation(client, third, text_pdf(LOT_PAGES), du_type="lotissement")
    assert choose_lot(client, third, document_id).json()["zone_code"] == "Ensemble"


def test_supplement_limits_and_type_conflicts(client: Any, upload_project: str, db_session: Any) -> None:
    plu_pdf, _pages = regulation_fixture()
    plu = upload_regulation(client, upload_project, plu_pdf, du_type="PLUi").json()["document"]["id"]
    read_document(plu)
    for number in range(3):
        upload_lot_document(client, upload_project, [f"Cahier des charges numéro {number} du lotissement."])
    fourth = upload_regulation(
        client, upload_project, text_pdf(["Encore un cahier des charges."]), du_type="cahier_des_charges"
    )
    assert fourth.status_code == 422 and fourth.json()["code"] == "too_many_supplements"

    other = new_project(client)
    conflict = upload_regulation(client, other, plu_pdf, du_type="lotissement")
    assert conflict.status_code == 409 and conflict.json()["code"] == "document_type_conflict"

    listed = client.get(f"/api/v1/projects/{upload_project}/regulations").json()
    supplement = listed[1]["document"]["id"]
    wrong_zone = choose(client, upload_project, supplement, zone_code="Uh", chapter_code="Uh")
    assert wrong_zone.status_code == 409 and wrong_zone.json()["code"] == "not_a_plu"
    wrong_lot = choose_lot(client, upload_project, plu, lot="12")
    assert wrong_lot.status_code == 409 and wrong_lot.json()["code"] == "not_a_supplement"
    db_session.expire_all()
    assert db_session.execute(select(func.count()).select_from(LandUsePlan)).scalar_one() == 4


def test_long_supplement_needs_a_page_range(client: Any, upload_project: str, db_session: Any) -> None:
    pages = [f"Cahier des charges, page {n}, dispositions générales du lotissement." for n in range(1, 152)]
    document_id = upload_lot_document(client, upload_project, pages, du_type="cahier_des_charges")
    refused = choose_lot(client, upload_project, document_id, lot="3")
    assert refused.status_code == 422 and refused.json()["code"] == "chapter_too_long"
    assert extract_jobs(db_session) == []
    accepted = choose_lot(client, upload_project, document_id, lot="3", first_page=1, last_page=40)
    assert accepted.status_code == 200
    chapter = doc_chapter(db_session, document_id)
    assert (chapter.first_page, chapter.last_page, chapter.detection) == (1, 40, "manual")


# ---------------------------------------------------------------------------
# Analyse (3.1–3.4, 3.9)
# ---------------------------------------------------------------------------


def test_analysis_of_the_uploaded_parcel(
    client: Any, upload_project: str, db_session: Any, settings: Any
) -> None:
    before = client.get(f"/api/v1/projects/{upload_project}/analysis")
    assert before.status_code == 200
    assert (before.json()["status"], before.json()["reason"], before.json()["parts"]) == (
        "unavailable",
        "upload",
        [],
    )

    with_plu(client, upload_project, db_session, settings)
    analysis = client.get(f"/api/v1/projects/{upload_project}/analysis").json()
    assert analysis["simulation"] is True and analysis["status"] == "ok"
    assert analysis["input_hash"].startswith("sha256:")
    part = analysis["parts"][0]
    assert part["zone_code"] == "Uh"
    strict = part["footprint"]["strict"]
    assert (strict["value_m2"], strict["binding"], strict["complete"]) == (150.0, "ratio", True)
    ratio = next(c for c in strict["candidates"] if c["source"] == "ratio")
    assert ratio["citation"]["page"] is not None
    assert analysis["footprint"]["lenient"] == {"value_m2": 150.0, "complete": True}
    storeys = part["storeys"]
    assert (storeys["full_min"], storeys["full_max"], storeys["top"], storeys["source"]) == (
        2,
        2,
        "attic",
        "eave",
    )
    assert storeys["notes"] == ["attic_possible"]
    assert (analysis["floor_area"]["low_m2"], analysis["floor_area"]["high_m2"]) == (255, 380)
    assert "stairs_lifts" in analysis["not_counted"]
    assert analysis["assumptions"]["custom"] is False
    assert analysis["assumptions"]["values"]["storey_height_m"] == {"low": 2.7, "high": 3.0}

    changed = client.put(
        f"/api/v1/projects/{upload_project}/analysis/parameters",
        json={
            "storey_height_m": {"low": 3.0, "high": 3.0},
            "wall_share": {"low": 0.1, "high": 0.1},
            "attic_share": {"low": 0.6, "high": 0.6},
            "attique_share": {"low": 0.6, "high": 0.8},
        },
    )
    assert changed.status_code == 200, changed.json()
    body = changed.json()
    assert body["assumptions"]["custom"] is True
    # 150 × 2 × 0,9 = 270; oben 150 × 2,6 × 0,9 = 351
    assert (body["floor_area"]["low_m2"], body["floor_area"]["high_m2"]) == (270, 351)
    assert body["input_hash"] != analysis["input_hash"]

    reset = client.delete(f"/api/v1/projects/{upload_project}/analysis/parameters").json()
    assert reset["assumptions"]["custom"] is False and reset["input_hash"] == analysis["input_hash"]


@pytest.mark.parametrize(
    "span",
    [{"low": 3.2, "high": 3.0}, {"low": 1.0, "high": 3.0}],
)
def test_parameters_are_validated(client: Any, upload_project: str, span: dict[str, float]) -> None:
    body = {
        "storey_height_m": span,
        "wall_share": {"low": 0.08, "high": 0.15},
        "attic_share": {"low": 0.5, "high": 0.75},
        "attique_share": {"low": 0.6, "high": 0.8},
    }
    response = client.put(f"/api/v1/projects/{upload_project}/analysis/parameters", json=body)
    assert response.status_code == 422


def test_customers_have_no_analysis(client: Any, flags: None, login_as: Any) -> None:
    customer = new_project(client)
    assert client.get(f"/api/v1/projects/{customer}/analysis").status_code == 404
    login_as("architect")
    assert client.get(f"/api/v1/projects/{customer}/analysis").status_code == 404
