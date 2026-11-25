"""Regeldienst (docs/PLAN_REGELDIENST.md): Auswertung im Umfang `collectif` neben dem Einfamilienhaus und die
Leseroute mit Service-Token. Planstand und Kapitel Uh wie in `test_rules.py` (Treillières)."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.platform import service_tokens
from app.platform.db import utcnow
from app.platform.models import AuditLog, ServiceToken
from app.platform.problems import Problem
from app.rules import extract
from app.rules.models import (
    RegulationChapter,
    RegulationChapterScope,
    Rule,
    RuleExtractionRun,
    RuleSet,
    RuleSetVersion,
)
from tests.integration import test_rules
from tests.rules_support import FakeExtractor, uh_output

# Fixtures aus test_rules per Zuweisung (README, Stolperstellen Backend)
memory_storage = test_rules.memory_storage
settings = test_rules.settings
plan = test_rules.plan
site_project = test_rules.site_project

COMMUNE = "/api/v1/service/rules/communes/44209"


def run(db_session: Any, settings: Any, extractor: FakeExtractor, **kwargs: Any) -> extract.ChapterOutcome:
    return test_rules.run_extraction(db_session, settings, extractor, **kwargs)


@pytest.fixture
def token(db_session: Any) -> str:
    return service_tokens.create(db_session, "mass-study", ["rules:read"], days=30).token


@pytest.fixture
def service(app: Any) -> Any:
    """Ein Client ohne Cookies wie der Server der Massenstudie."""
    with TestClient(app, base_url="http://testserver") as client:
        yield client


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auswertung im Umfang `collectif`
# ---------------------------------------------------------------------------


def test_collectif_extraction_stands_beside_the_house(db_session: Any, plan: Any, settings: Any) -> None:
    extractor = FakeExtractor([uh_output(), uh_output()])
    outcome = run(db_session, settings, extractor, scope="collectif")
    assert outcome.status == "succeeded"
    assert {r.scope for r in extractor.requests} == {"collectif"}

    chapter = db_session.get(RegulationChapter, test_rules.chapter_id(db_session))
    assert chapter.status == "pending"  # Der Stand des Hauses bleibt unberührt
    state = db_session.get(RegulationChapterScope, (chapter.id, "collectif"))
    assert state.status == "succeeded" and state.input_hash and state.engine_version

    rule_set = db_session.execute(select(RuleSet)).scalar_one()
    assert rule_set.scope == "collectif" and rule_set.zone_code == "Uh"
    version = db_session.get(RuleSetVersion, rule_set.current_version_id)
    assert version.prompt_version.endswith("+collectif")
    rules = {(r.kind, r.building_kind): r for r in db_session.execute(select(Rule)).scalars()}
    assert rules[("setback_between_buildings", "main")].reason == "missing"
    assert ("roof", "main") not in rules  # keine Pflichtart im Wohnungsbau
    runs = db_session.execute(select(RuleExtractionRun)).scalars().all()
    assert {r.scope for r in runs} == {"collectif"}
    assert {r.prompt_version for r in runs} == {version.prompt_version}

    # Unverändert: kein weiterer Aufruf; das Haus wertet getrennt aus und nutzt die Läufe nicht
    assert run(db_session, settings, extractor, scope="collectif").status == "skipped"
    house = FakeExtractor([uh_output(), uh_output()])
    assert run(db_session, settings, house).status == "succeeded"
    assert len(house.requests) == 2 and {r.scope for r in house.requests} == {"house"}
    scopes = sorted(s.scope for s in db_session.execute(select(RuleSet)).scalars())
    assert scopes == ["collectif", "house"]
    assert db_session.get(RegulationChapter, chapter.id).status == "succeeded"


def test_customer_never_sees_collectif_rules(
    client: Any, db_session: Any, site_project: str, plan: Any, settings: Any
) -> None:
    run(db_session, settings, FakeExtractor([uh_output(), uh_output()]), scope="collectif")
    body = client.get(f"/api/v1/projects/{site_project}/rules").json()
    assert body["status"] == "in_progress" and body["zones"][0]["version"] is None

    run(db_session, settings, FakeExtractor([uh_output(), uh_output(footprint=0.3)]))
    zone = client.get(f"/api/v1/projects/{site_project}/rules").json()["zones"][0]
    house = db_session.execute(select(RuleSet).where(RuleSet.scope == "house")).scalar_one()
    assert zone["rule_set_id"] == str(house.id)


# ---------------------------------------------------------------------------
# Service-Token
# ---------------------------------------------------------------------------


def test_route_needs_a_valid_service_token(
    service: Any, client: Any, login_as: Any, db_session: Any, plan: Any, token: str
) -> None:
    missing = service.get(COMMUNE)
    assert missing.status_code == 401 and missing.json()["code"] == "service_token_required"
    assert service.get(COMMUNE, headers=_auth("emps_falsch")).json()["code"] == "service_token_invalid"
    assert service.get(COMMUNE, headers=_auth("nicht-einmal-praefix")).status_code == 401
    # Eine Sitzung des Büros öffnet den Dienst nicht
    login_as("architect", "ops")
    assert client.get(COMMUNE).status_code == 401

    assert service.get(COMMUNE, headers=_auth(token)).status_code == 200
    row = db_session.execute(select(ServiceToken)).scalar_one()
    db_session.refresh(row)
    assert row.last_used_at is not None and row.token_hash != token.encode()

    assert service_tokens.revoke(db_session, "mass-study")
    assert service.get(COMMUNE, headers=_auth(token)).json()["code"] == "service_token_invalid"
    actions = set(db_session.execute(select(AuditLog.action)).scalars())
    assert {"service_token.create", "service_token.revoke"} <= actions


def test_expired_token_and_duplicate_name(service: Any, db_session: Any, plan: Any, token: str) -> None:
    with pytest.raises(Problem) as duplicate:
        service_tokens.create(db_session, "mass-study", ["rules:read"], days=None)
    assert duplicate.value.code == "service_token_exists"
    with pytest.raises(Problem):
        service_tokens.create(db_session, "anderer", ["projects:write"], days=None)
    row = db_session.execute(select(ServiceToken)).scalar_one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert service.get(COMMUNE, headers=_auth(token)).status_code == 401


# ---------------------------------------------------------------------------
# Leseroute
# ---------------------------------------------------------------------------


def test_commune_overview_lists_zones_with_state_per_scope(
    service: Any, db_session: Any, plan: Any, settings: Any, token: str
) -> None:
    body = service.get(COMMUNE, headers=_auth(token)).json()
    assert body["format"] == "emprise-rules/1" and body["status"] == "ok"
    assert body["plan"]["du_type"] == "PLUi"
    zones = {z["code"]: z for z in body["zones"]}
    assert set(zones) == {"A", "N", "Ue", "Uec", "Uh"}
    uh = {s["scope"]: s for s in zones["Uh"]["states"]}
    assert uh["house"]["status"] == "in_progress" and uh["collectif"]["status"] == "not_extracted"
    assert {s["status"] for s in zones["A"]["states"]} == {"unavailable"}

    run(db_session, settings, FakeExtractor([uh_output(), uh_output()]), scope="collectif")
    body = service.get(COMMUNE, headers=_auth(token)).json()
    uh = {s["scope"]: s for s in next(z for z in body["zones"] if z["code"] == "Uh")["states"]}
    assert uh["collectif"]["status"] == "simulated" and uh["collectif"]["updated_at"]

    assert service.get("/api/v1/service/rules/communes/91477", headers=_auth(token)).status_code == 404
    assert service.get("/api/v1/service/rules/communes/abc", headers=_auth(token)).status_code == 422


def test_zone_rules_in_format_for_the_massing_study(
    service: Any, db_session: Any, plan: Any, settings: Any, token: str
) -> None:
    url = f"{COMMUNE}/zones/Uh"
    before = service.get(url, headers=_auth(token)).json()
    assert before["status"] == "not_extracted" and before["rules"] == [] and before["version"] is None

    run(db_session, settings, FakeExtractor([uh_output(), uh_output()]), scope="collectif")
    body = service.get(url, headers=_auth(token)).json()
    assert body["format"] == "emprise-rules/1" and body["simulation"] is True
    assert body["scope"] == "collectif" and body["status"] == "simulated"
    assert body["zone"] == {"code": "Uh", "label": body["zone"]["label"], "chapter_code": "Uh"}
    assert body["version"]["prompt_version"].endswith("+collectif")
    street = next(r for r in body["rules"] if r["kind"] == "setback_street" and r["building_kind"] == "main")
    assert street["status"] == "effective" and street["quote_verified"] and street["page"] == 9
    assert street["params"]["min_m"] == 5.0 and street["params"]["band"] == "building"
    assert street["source_url"].endswith("#page=9")
    assert [h["kind"] for h in body["hints"]] == ["text_only"]
    assert "notice.rules_feed_suggestion" in body["notices"]

    house = service.get(f"{url}?scope=house", headers=_auth(token)).json()
    assert house["scope"] == "house" and house["status"] == "in_progress" and house["rules"] == []
    unknown = service.get(f"{COMMUNE}/zones/UX", headers=_auth(token))
    assert unknown.status_code == 404 and unknown.json()["code"] == "commune_zone_unknown"
    assert service.get(f"{url}?scope=bureau", headers=_auth(token)).status_code == 422


def test_reading_never_starts_an_extraction(service: Any, db_session: Any, plan: Any, token: str) -> None:
    from app.platform.models import Job

    jobs = set(db_session.execute(select(Job.id)).scalars())
    service.get(f"{COMMUNE}/zones/Uh", headers=_auth(token))
    service.get(COMMUNE, headers=_auth(token))
    db_session.expire_all()
    assert set(db_session.execute(select(Job.id)).scalars()) == jobs
    assert db_session.execute(select(RegulationChapterScope)).first() is None
    assert uuid.UUID(str(db_session.execute(select(ServiceToken.id)).scalar_one()))
