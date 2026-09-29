"""Nachsuche nach Auswertung und Gegenprüfung gegen PostGIS (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.5–3.7).

Kapitel Uh des PLUi Erdre et Gesvres (Treillières): Die Auswertung (`uh_output`) findet weder Dach noch
Fassade noch unversiegelte Fläche. Die Nachsuche findet das Dach, meldet die Fassade als nicht geregelt und
die Freifläche als nicht abbildbar. Seiten: Positionen im Kapitel-PDF (Originalseite 4 = Position 1).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.platform import storage
from app.platform.db import get_sessionmaker
from app.rules import extract
from app.rules.domain.extraction import ExtractionError, ExtractionRequest
from app.rules.models import LandUsePlan, RegulationChapter, Rule, RuleSet, RuleSetVersion
from app.rules.plan_import import DirectoryGpu, import_commune
from tests.rules_support import DOC_ID, FakeExtractor, gpu_directory, rule, uh_output

ROOF = rule(
    "Uh",
    "roof",
    {"allowed_forms": ["gable"], "pitch_min_deg": 30, "pitch_max_deg": 45},
    "Les toitures des constructions traditionnelles à usage d’habitation, hors extension et annexe, "
    "présenteront 2 versants principaux dont la pente est comprise entre 30° et 45°",
    11,
)
GREEN = rule(
    "Uh",
    "text_only",
    {"summary": "Pleine terre à privilégier, selon le schéma de gestion des eaux pluviales."},
    "Les espaces de pleine terre seront privilégiées et doivent respecter le schéma de gestion des eaux "
    "pluviales.",
    13,
    status="text_only",
)
POOL_AS_MAIN = rule(
    "Uh",
    "setback_side",
    {"min_m": 1},
    "Les piscines (margelles comprises) s’implantent en retrait de 1 mètre minimum.",
    7,
)


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
    monkeypatch.setenv("EMPRISE_RULES_GAP_SEARCH", "true")
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


def _chapter_id(db_session: Any) -> uuid.UUID:
    return db_session.execute(
        select(RegulationChapter.id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(RegulationChapter.code == "Uh", LandUsePlan.gpu_doc_id == DOC_ID)
    ).scalar_one()


def _run(db_session: Any, settings: Any, extractor: FakeExtractor) -> extract.ChapterOutcome:
    outcome = extract.extract_chapter(sessions, settings, _chapter_id(db_session), extractor.factory())
    db_session.expire_all()
    return outcome


def _answer(request: ExtractionRequest) -> dict[str, Any]:
    """Nachsuche: Dach gefunden, Fassade nicht geregelt, Freifläche nicht abbildbar; die erste offene
    Textstelle betrifft kein Einfamilienhaus."""
    assert request.gaps is not None
    verdicts = {
        "roof": ("found", [ROOF], ""),
        "facade": ("absent", [], "Article Uh 11 (aspect extérieur), façades, enduits, teintes"),
        "unsealed_min": ("not_expressible", [GREEN], ""),
    }
    gaps = [
        {
            "gap": gap["gap"],
            "verdict": verdicts[gap["kind"]][0],
            "rules": verdicts[gap["kind"]][1],
            "searched": verdicts[gap["kind"]][2],
        }
        for gap in request.gaps["gaps"]
        if gap["kind"] in verdicts and gap["building_kind"] == "main"
    ]
    passages = [
        {"passage": p["passage"], "verdict": "out_of_scope", "rules": [], "reason": "networks", "note": ""}
        for p in request.gaps["passages"][:1]
    ]
    return {"gaps": gaps, "passages": passages, "remarks": ""}


def _current_rules(db_session: Any) -> tuple[RuleSetVersion, list[Rule]]:
    rule_set = db_session.execute(select(RuleSet)).scalar_one()
    version = db_session.get(RuleSetVersion, rule_set.current_version_id)
    rules = list(db_session.execute(select(Rule).where(Rule.rule_set_version_id == version.id)).scalars())
    return version, rules


def test_gap_search_finds_marks_and_classifies(db_session: Any, plan: Any, settings: Any) -> None:
    extractor = FakeExtractor([uh_output(), uh_output(), _answer, {"rules": [ROOF], "remarks": ""}])
    outcome = _run(db_session, settings, extractor)
    assert outcome.status == "succeeded" and len(extractor.requests) == 4

    search = extractor.requests[2]
    assert search.gaps is not None and search.claims is None
    asked = {(g["kind"], g["building_kind"]) for g in search.gaps["gaps"]}
    assert {("roof", "main"), ("facade", "main"), ("unsealed_min", "main")} <= asked
    assert ("max_height", "main") not in asked  # wirksam: keine Lücke
    roof_gap = next(g for g in search.gaps["gaps"] if g["kind"] == "roof")
    assert "toiture" in roof_gap["terms"] and roof_gap["article"] == "11" and "previous" not in roof_gap
    assert search.gaps["passages"] and all(1 <= p["page"] <= 21 for p in search.gaps["passages"])
    # Nur der neue Fund geht in die Gegenprüfung, mit Nummer hinter denen der Auswertung
    claims = extractor.requests[3].claims
    assert claims is not None and [c["kind"] for c in claims] == ["roof"] and claims[0]["claim"] > 8

    version, rules = _current_rules(db_session)
    by_kind = {(r.kind, r.building_kind): r for r in rules if r.kind != "text_only"}
    roof = by_kind[("roof", "main")]
    assert roof.status == "effective" and roof.page == 14 and roof.quote_verified
    assert roof.params["pitch_min_deg"] == 30 and roof.params["allowed_forms"] == ["gable"]
    facade = by_kind[("facade", "main")]
    assert (facade.status, facade.reason) == ("unknown", "not_found_after_search")
    assert "Article Uh 11" in (facade.detail or "")
    unsealed = by_kind[("unsealed_min", "main")]
    assert (unsealed.status, unsealed.reason, unsealed.detail) == ("unknown", "not_expressible", "16")
    assert any(r.kind == "text_only" and r.page == 16 for r in rules)

    coverage = version.coverage
    assert coverage["gap_search"] == 1 and coverage["passages_out_of_scope"] == 1
    assert coverage["passages_total"] == (
        coverage["passages_assigned"] + coverage["passages_open"] + coverage["passages_out_of_scope"]
    )
    assert version.out_of_scope_passages[0]["reason"] == "networks"
    assert len(version.open_passages) == coverage["passages_open"] > 0
    assert {"page", "text"} <= set(version.open_passages[0])


def test_confirmed_finding_against_an_effective_rule_is_ambiguous(
    db_session: Any, plan: Any, settings: Any
) -> None:
    """Zwei belegte, verschiedene Aussagen zum selben Schlüssel: der Architekt entscheidet (3.6)."""

    def answer(request: ExtractionRequest) -> dict[str, Any]:
        assert request.gaps is not None
        first = request.gaps["passages"][0]
        passages = [
            {
                "passage": first["passage"],
                "verdict": "assigned",
                "rules": [POOL_AS_MAIN],
                "reason": "none",
                "note": "",
            }
        ]
        return {"gaps": [], "passages": passages, "remarks": ""}

    extractor = FakeExtractor([uh_output(), uh_output(), answer, {"rules": [POOL_AS_MAIN], "remarks": ""}])
    assert _run(db_session, settings, extractor).status == "succeeded"
    _version, rules = _current_rules(db_session)
    side = next(r for r in rules if r.kind == "setback_side" and r.building_kind == "main")
    assert (side.status, side.reason) == ("unknown", "ambiguous")
    assert sorted(a["params"].get("min_m") for a in side.alternatives) == [1.0, 3.0]


def test_unconfirmed_finding_leaves_an_effective_rule_alone(
    db_session: Any, plan: Any, settings: Any
) -> None:
    def answer(request: ExtractionRequest) -> dict[str, Any]:
        assert request.gaps is not None
        wrong = {**POOL_AS_MAIN, "quote": "Ce texte ne figure pas dans le règlement de la zone."}
        first = request.gaps["passages"][0]
        passages = [
            {
                "passage": first["passage"],
                "verdict": "assigned",
                "rules": [wrong],
                "reason": "none",
                "note": "",
            }
        ]
        return {"gaps": [], "passages": passages, "remarks": ""}

    extractor = FakeExtractor([uh_output(), uh_output(), answer, {"rules": [], "remarks": ""}])
    assert _run(db_session, settings, extractor).status == "succeeded"
    _version, rules = _current_rules(db_session)
    side = next(r for r in rules if r.kind == "setback_side" and r.building_kind == "main")
    assert side.status == "effective" and side.params["min_m"] == 3.0


def test_too_long_gap_answer_is_split(db_session: Any, plan: Any, settings: Any) -> None:
    too_long = ExtractionError("max_tokens", retryable=False)
    extractor = FakeExtractor(
        [uh_output(), uh_output(), too_long, _answer, _answer, {"rules": [ROOF], "remarks": ""}]
    )
    assert _run(db_session, settings, extractor).status == "succeeded"
    whole, first, second = (r.gaps for r in extractor.requests[2:5])
    assert whole is not None and first is not None and second is not None
    assert len(first["gaps"]) + len(second["gaps"]) == len(whole["gaps"])
    assert len(first["passages"]) + len(second["passages"]) == len(whole["passages"])
    _version, rules = _current_rules(db_session)
    assert next(r for r in rules if r.kind == "roof").status == "effective"


def test_without_gap_search_the_coverage_is_still_counted(
    db_session: Any, plan: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMPRISE_RULES_GAP_SEARCH", "false")
    get_settings.cache_clear()
    extractor = FakeExtractor([uh_output(), uh_output()])
    assert _run(db_session, get_settings(), extractor).status == "succeeded"
    assert len(extractor.requests) == 2
    version, _rules = _current_rules(db_session)
    assert version.coverage["gap_search"] == 0 and version.coverage["passages_total"] > 0
    assert len(version.open_passages) == version.coverage["passages_open"]
