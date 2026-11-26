"""Umfang `collectif` der Regelauswertung (docs/PLAN_REGELDIENST.md 3): eigener Prompt und eigene
Pflichtarten, ohne den Prompt des Einfamilienhauses zu verändern."""

import uuid
from dataclasses import replace
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
    # Status, Zitate und Parameter wie beim Haus, dazu die Abstände vor Fassaden ohne Ansichten (B2)
    house_tail = SYSTEM_PROMPT[SYSTEM_PROMPT.index("status\n- `regulated`") :]
    blind = COLLECTIF_SYSTEM_PROMPT.index("- Facades without views (collectif only)")
    end = COLLECTIF_SYSTEM_PROMPT.index("\n", COLLECTIF_SYSTEM_PROMPT.index("height_basis eave.", blind)) + 1
    assert COLLECTIF_SYSTEM_PROMPT[:blind] + COLLECTIF_SYSTEM_PROMPT[end:] == (
        COLLECTIF_SYSTEM_PROMPT[: COLLECTIF_SYSTEM_PROMPT.index("status\n- `regulated`")] + house_tail
    )
    assert "blind_min_m" in COLLECTIF_SYSTEM_PROMPT and "blind_min_m" not in SYSTEM_PROMPT
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


# ---------------------------------------------------------------------------
# Befunde der Messung Palaiseau UC2 (docs/PLAN_REGELDIENST.md 9)
# ---------------------------------------------------------------------------


def _param_names(schema: dict[str, Any]) -> set[str]:
    params = schema["properties"]["rules"]["items"]["properties"]["params"]
    return set(params["items"]["properties"]["name"]["enum"])


def test_blind_facade_params_only_in_collectif_schemas() -> None:
    from app.rules.domain.extraction import (
        OUTPUT_SCHEMA,
        VERIFICATION_SCHEMA,
        output_schema,
        verification_schema,
    )
    from app.rules.domain.kinds import COLLECTIF_ONLY_PARAMS

    assert not COLLECTIF_ONLY_PARAMS & _param_names(OUTPUT_SCHEMA)
    assert output_schema() is OUTPUT_SCHEMA and verification_schema() is VERIFICATION_SCHEMA
    assert _param_names(output_schema("collectif")) >= COLLECTIF_ONLY_PARAMS
    checks = verification_schema("collectif")["properties"]["checks"]["items"]["properties"]["params"]
    assert set(checks["items"]["properties"]["name"]["enum"]) >= COLLECTIF_ONLY_PARAMS
    gaps = gap_schema("collectif")["properties"]["gaps"]["items"]["properties"]["rules"]
    assert _param_names({"properties": {"rules": gaps}}) >= COLLECTIF_ONLY_PARAMS
    assert not COLLECTIF_ONLY_PARAMS & _param_names(
        {"properties": {"rules": GAP_SCHEMA["properties"]["gaps"]["items"]["properties"]["rules"]}}
    )


def test_setback_with_and_without_views() -> None:
    import pytest

    from app.rules.domain.kinds import ParamProblem, validate_params

    side = validate_params(
        "setback_side",
        {
            "min_m": 8,
            "height_factor": 1,
            "blind_min_m": 2.5,
            "blind_height_factor": 0.5,
            "height_basis": "eave",
            "allow_on_boundary": True,
        },
    )
    assert side["blind_min_m"] == 2.5 and side["blind_height_factor"] == 0.5
    between = validate_params(
        "setback_between_buildings",
        {"min_m": 8, "height_factor": 1, "blind_min_m": 5, "blind_height_factor": 0.5},
    )
    assert between["blind_min_m"] == 5
    with pytest.raises(ParamProblem):
        validate_params("setback_rear", {"min_m": 8, "blind_height_factor": 0.5})
    with pytest.raises(ParamProblem):
        validate_params("setback_rear", {"min_m": 8, "blind_min_m": 80})


def test_runs_agree_on_values_not_on_wording() -> None:
    from app.rules.domain.kinds import agreed_params, validate_params

    def norm(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
        return validate_params(kind, raw)

    # Freitext wird nicht verglichen
    first = norm("unsealed_min", {"full_soil_ratio": 0.3, "counting": "coefficient 1 pour 4 m de terre"})
    second = norm("unsealed_min", {"full_soil_ratio": 0.3, "counting": "coefficient 1 (≥ 4 m)"})
    assert agreed_params("unsealed_min", first, second) == first
    # Dieselbe Zahl, nur einmal zusätzlich als Attika gelesen
    height = norm("max_height", {"ridge_m": 16, "parapet_m": 16, "measured_at": "highest_point"})
    checked = norm("max_height", {"ridge_m": 16, "measured_at": "highest_point"})
    assert agreed_params("max_height", height, checked) == height
    # Ein Grenzwert, den nur ein Lauf liest und der sonst nirgends steht: Widerspruch
    eave = norm("max_height", {"ridge_m": 16, "eave_m": 12})
    assert agreed_params("max_height", eave, checked) is None
    # Eine Angabe ohne Grenzwert, die nur ein Lauf nennt, entfällt
    footprint = norm("max_footprint_ratio", {"ratio": 0.5, "counts_overhangs": "yes"})
    plain = norm("max_footprint_ratio", {"ratio": 0.5})
    assert agreed_params("max_footprint_ratio", footprint, plain) == plain
    # Verschiedene Werte bleiben ein Widerspruch
    assert agreed_params("max_footprint_ratio", plain, norm("max_footprint_ratio", {"ratio": 0.4})) is None


def test_verification_keeps_confirmed_values() -> None:
    from app.rules.domain.assess import verify
    from app.rules.domain.extraction import VerificationCheck

    rule = _rule("max_footprint_ratio")
    rule = replace(rule, params={"ratio": 0.5, "counts_overhangs": "yes"}, sources=(1,))
    check = VerificationCheck(claim=1, status="regulated", params={"ratio": 0.5}, notes="")
    [result] = verify([rule], {1: [check]})
    assert result.status == "effective" and result.params == {"ratio": 0.5}
    other = VerificationCheck(claim=1, status="regulated", params={"ratio": 0.4}, notes="")
    [result] = verify([rule], {1: [other]})
    assert (result.status, result.reason) == ("unknown", "runs_disagree")


def test_height_factor_in_words_is_in_the_quote() -> None:
    from app.rules.domain.text import values_in_quote

    quote = (
        "la distance doit être au moins égale à : - la hauteur à l’égout du toit le plus haut "
        "avec un minimum de 8 mètres si la façade comporte des vues - la moitié de la hauteur "
        "à l'égout du toit le plus haut, avec un minimum de 2,5 mètres"
    )
    values = {"min_m": 8.0, "height_factor": 1.0, "blind_min_m": 2.5, "blind_height_factor": 0.5}
    assert values_in_quote(values, quote) == []
    assert values_in_quote({"height_factor": 1.0}, "égale à la moitié de la hauteur") == ["height_factor"]
    assert values_in_quote({"height_factor": 0.5}, "au moins égale à la hauteur") == ["height_factor"]
    assert values_in_quote({"min_m": 0.5}, "la moitié de la hauteur") == ["min_m"]


def test_height_factor_one_as_second_item_of_the_list() -> None:
    from app.rules.domain.text import values_in_quote

    # Palaiseau UC2, Abstand zwischen Gebäuden: „la hauteur“ steht als zweiter Punkt nach „égale à :“
    quote = (
        "séparant les façades en vis à vis de ces deux constructions doit être au moins égale à : "
        "- la moitié de la hauteur à l'égout du toit le plus haut, avec un minimum de 5m si aucune des "
        "façades en vis-à-vis ne comporte des ouvertures créant des vues directes, - la hauteur à l'égout "
        "du toit le plus haut, avec un minimum de 8m"
    )
    values = {"min_m": 8.0, "height_factor": 1.0, "blind_min_m": 5.0, "blind_height_factor": 0.5}
    assert values_in_quote(values, quote) == []
    # Ohne „égale à :“ ist „- la hauteur“ kein Beleg für den Faktor 1
    factor = {"height_factor": 1.0}
    assert values_in_quote(factor, "- la hauteur à l'égout du toit, avec un minimum de 8m") == [
        "height_factor"
    ]
    assert values_in_quote(factor, "au moins égale à : - la moitié de la hauteur") == ["height_factor"]


def test_setback_between_takes_height_basis() -> None:
    from app.rules.domain.kinds import validate_params

    params = validate_params(
        "setback_between_buildings",
        {
            "min_m": 8,
            "height_factor": 1,
            "height_basis": "eave",
            "blind_min_m": 5,
            "blind_height_factor": 0.5,
        },
    )
    assert params["height_basis"] == "eave"
