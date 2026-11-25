"""Umfang `collectif` der Regelauswertung (docs/PLAN_REGELDIENST.md 3): eigener Prompt und eigene
Pflichtarten, ohne den Prompt des Einfamilienhauses zu verändern."""

import uuid
from typing import Any

from app.config import Settings
from app.rules.domain import PROMPT_VERSION
from app.rules.domain.assess import AssessedRule, complete, coverage
from app.rules.domain.extraction import (
    COLLECTIF_SYSTEM_PROMPT,
    GAP_SCHEMA,
    GAP_TASK,
    SUPPLEMENT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    gap_instruction,
    gap_schema,
    gap_task,
    parse_gaps,
    prompt_fingerprint,
    prompt_version,
    system_prompt,
)
from app.rules.domain.kinds import MANDATORY_BY_SCOPE, MANDATORY_KINDS
from app.rules.domain.resolve import feed_state
from app.rules.models import RegulationChapter
from app.rules.runs import input_hash

HOUSE_FINGERPRINT = "a7ad548f037be25e"
SUPPLEMENT_FINGERPRINT = "dc4e752f99503cef"
"""Prüfsummen vom 25.11.2026, vor dem Umfang `collectif`. Ändern sie sich, wertet jede Instanz alle Kapitel
neu aus (bezahlt, RW26): Eine Änderung am Hausprompt braucht eine eigene Entscheidung, nicht diesen Umbau."""


def test_house_prompt_is_unchanged() -> None:
    assert prompt_fingerprint("plu") == HOUSE_FINGERPRINT
    assert prompt_fingerprint("plu", "house") == HOUSE_FINGERPRINT
    assert prompt_fingerprint("supplement") == SUPPLEMENT_FINGERPRINT
    assert system_prompt("plu") == SYSTEM_PROMPT and gap_task() == GAP_TASK and gap_schema() == GAP_SCHEMA
    assert prompt_version() == PROMPT_VERSION


def test_collectif_prompt_is_about_collective_housing() -> None:
    assert system_prompt("plu", "collectif") == COLLECTIF_SYSTEM_PROMPT
    assert prompt_fingerprint("plu", "collectif") not in (HOUSE_FINGERPRINT, SUPPLEMENT_FINGERPRINT)
    assert "single-family" not in COLLECTIF_SYSTEM_PROMPT
    assert (
        "habitat collectif" in COLLECTIF_SYSTEM_PROMPT
        and "setback_between_buildings" in COLLECTIF_SYSTEM_PROMPT
    )
    # Status, Zitate und Parameter wie beim Haus
    assert COLLECTIF_SYSTEM_PROMPT.endswith(SYSTEM_PROMPT[SYSTEM_PROMPT.index("status\n- `regulated`") :])
    # Zusatzdokumente gibt es nur für das Haus
    assert system_prompt("supplement", "collectif") == SUPPLEMENT_SYSTEM_PROMPT
    assert prompt_version("collectif") == f"{PROMPT_VERSION}+collectif"


def test_collectif_gap_search_dismisses_single_house_passages() -> None:
    task = gap_task("collectif")
    assert "multi_dwelling" not in task and "single_house" in task and "single-family" not in task
    instruction = gap_instruction({"gaps": [], "passages": []}, "UA", [1], [2, 3], [], "collectif")
    assert instruction.startswith(task)
    reasons = gap_schema("collectif")["properties"]["passages"]["items"]["properties"]["reason"]["enum"]
    assert "single_house" in reasons and "multi_dwelling" not in reasons

    answer = {
        "gaps": [],
        "passages": [
            {"passage": 1, "verdict": "out_of_scope", "rules": [], "reason": "single_house", "note": ""},
            {"passage": 2, "verdict": "out_of_scope", "rules": [], "reason": "multi_dwelling", "note": ""},
        ],
        "remarks": "",
    }
    assert set(parse_gaps(answer, "collectif").passages) == {1}
    assert set(parse_gaps(answer).passages) == {2}


def _rule(kind: str) -> AssessedRule:
    return AssessedRule(
        sector="UA",
        kind=kind,
        building_kind="main",
        status="effective",
        reason=None,
        params={},
        page=3,
        quote="…",
        quote_verified=True,
        similarity=1.0,
        confidence=0.9,
        notes="",
    )


def test_collectif_needs_distance_between_buildings_not_roof() -> None:
    collectif = MANDATORY_BY_SCOPE["collectif"]
    assert MANDATORY_BY_SCOPE["house"] == MANDATORY_KINDS
    assert "setback_between_buildings" in collectif and "roof" not in collectif and "facade" not in collectif
    rules = complete([_rule("setback_street")], ["UA"], collectif)
    missing = {r.kind for r in rules if r.reason == "missing"}
    assert missing == set(collectif) - {"setback_street"}
    assert coverage(rules, collectif)["mandatory_unknown"] == len(collectif) - 1
    # Standard bleibt das Haus
    assert {r.kind for r in complete([], ["UA"]) if r.reason == "missing"} == set(MANDATORY_KINDS)


def test_input_hash_of_house_is_unchanged_and_collectif_differs() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    chapter = RegulationChapter(
        id=uuid.uuid4(), code="UA", first_page=4, last_page=9, general_pages=[1, 2], sectors=["UA", "UAa"]
    )
    house = input_hash(settings, "a" * 64, chapter)
    assert input_hash(settings, "a" * 64, chapter, scope="house") == house
    assert input_hash(settings, "a" * 64, chapter, scope="collectif") != house


def test_feed_state() -> None:
    cases: list[tuple[dict[str, Any], tuple[str, str | None]]] = [
        (
            {"version_status": "simulated", "state_status": "succeeded", "chapter_known": True},
            ("simulated", None),
        ),
        ({"version_status": None, "state_status": None, "chapter_known": True}, ("not_extracted", None)),
        (
            {"version_status": None, "state_status": "pending", "chapter_known": True},
            ("not_extracted", "pending"),
        ),
        (
            {"version_status": None, "state_status": "extracting", "chapter_known": True},
            ("in_progress", None),
        ),
        (
            {
                "version_status": None,
                "state_status": "failed",
                "chapter_known": True,
                "state_error": "refusal",
            },
            ("unavailable", "refusal"),
        ),
        (
            {"version_status": None, "state_status": None, "chapter_known": False},
            ("unavailable", "chapter_not_found"),
        ),
    ]
    for kwargs, expected in cases:
        state = feed_state(kwargs.pop("version_status"), kwargs.pop("state_status"), **kwargs)
        assert (state.status, state.reason) == expected
    assert feed_state("simulated", "extracting", chapter_known=True).updating
