"""Fachlogik G2 ohne Datenbank: Regelarten, Zitatprüfung, Kapitelsuche, Schranken, Abgleich zweier Läufe.

Texte stammen aus dem règlement écrit des PLUi Erdre et Gesvres (Stand 04.03.2026, Treillières).
"""

from typing import Any

import pytest

from app.rules.domain.assess import AssessedRule, DocumentPages, assess_rule, consensus, coverage
from app.rules.domain.chapters import Chapter, chapter_for_zone, detect_structure
from app.rules.domain.extraction import OUTPUT_SCHEMA, parse_output
from app.rules.domain.kinds import MANDATORY_KINDS, ParamProblem, params_equal, validate_params
from app.rules.domain.text import normalize, values_in_quote, verify_quote
from tests.rules_support import fixture_json, rule, uh_output

FIXTURE = fixture_json("reglement-pages.json")
ORIGINAL_PAGES: dict[int, str] = dict(zip(FIXTURE["original_pages"], FIXTURE["pages"], strict=True))
CHAPTER = list(range(92, 113))
DOCS = DocumentPages(general=[], chapter=CHAPTER)


# ---------------------------------------------------------------------------
# Regelarten
# ---------------------------------------------------------------------------


def test_params_are_normalized_with_defaults() -> None:
    assert validate_params("setback_side", {"min_m": 3.0, "allow_on_boundary": True}) == {
        "min_m": 3.0,
        "allow_on_boundary": True,
        "measured_from": "facade",
    }
    assert validate_params("facade", {"materials_allowed": ("wood", "render")})["materials_allowed"] == [
        "render",
        "wood",
    ]


@pytest.mark.parametrize(
    ("kind", "params", "reason"),
    [
        ("max_footprint_ratio", {"ratio": 40}, "implausible"),
        ("max_height", {"ridge_m": 90.0}, "implausible"),
        ("setback_street", {"mode": "min"}, "invalid_params"),
        ("setback_street", {"mode": "range", "min_m": 20.0, "max_m": 5.0}, "invalid_params"),
        ("setback_side", {"height_factor": 0.5}, "invalid_params"),
        ("max_height", {"storeys": "R+12"}, "invalid_params"),
        ("max_height", {"eave_m": 9.0, "ridge_m": 7.0}, "invalid_params"),
        ("facade", {"materials_allowed": ("enduit",)}, "invalid_params"),
        ("roof", {}, "invalid_params"),
        ("max_footprint_ratio", {"ratio": 0.4, "colour": "red"}, "invalid_params"),
    ],
)
def test_invalid_or_implausible_params(kind: str, params: dict[str, Any], reason: str) -> None:
    with pytest.raises(ParamProblem) as problem:
        validate_params(kind, params)
    assert problem.value.reason == reason


def test_storeys_and_equality() -> None:
    assert validate_params("max_height", {"storeys": "R+1+C"})["storeys"] == "R+1+C"
    assert params_equal({"min_m": 3.0}, {"min_m": 3.004})
    assert not params_equal({"min_m": 3.0}, {"min_m": 3.5})
    assert not params_equal({"min_m": 3.0}, {"min_m": 3.0, "allow_on_boundary": True})


# ---------------------------------------------------------------------------
# Zitate
# ---------------------------------------------------------------------------


def test_quote_found_despite_split_words_and_typography() -> None:
    check = verify_quote(
        "L'emprise au sol totale des constructions est limitée à 25 % "
        "de la surface totale de l'unité foncière",
        ORIGINAL_PAGES,
        99,
    )
    assert check.verified and check.page == 99
    assert normalize("La zone U h") == normalize("la zoneUh")


def test_quote_with_wrong_number_is_rejected() -> None:
    """Ein einzelnes Zeichen hält die Ähnlichkeit über 0,9; die Zahlenprüfung verhindert den Beleg."""
    check = verify_quote(
        "L’emprise au sol totale des constructions est limitée à 35% "
        "de la surface totale de l’unité foncière",
        ORIGINAL_PAGES,
        99,
    )
    assert not check.verified


def test_quote_on_neighbour_page_corrects_page_and_short_quote_proves_nothing() -> None:
    check = verify_quote(
        "La hauteur des constructions ne doit pas excéder 7 mètres à l’égout du toit", ORIGINAL_PAGES, 99
    )
    assert check.verified and check.page == 100
    assert verify_quote("5 m minimum", ORIGINAL_PAGES, 96).reason == "quote_too_short"
    assert (
        verify_quote("Texte qui ne figure nulle part dans ce document", ORIGINAL_PAGES, 99).reason
        == "quote_not_found"
    )


def test_values_in_quote_accepts_percent_and_inverse() -> None:
    assert values_in_quote([0.25], "limitée à 25% de la surface") == []
    assert values_in_quote([0.5, 3.0], "au moins égal à H/2 sans être inférieur à 3 m") == []
    assert values_in_quote([0.02], "1 place par tranche de 50 m² de surface de plancher") == []
    assert values_in_quote([7.0, 12.0], "ne doit pas excéder 7 mètres à l’égout") == [12.0]


# ---------------------------------------------------------------------------
# Kapitel
# ---------------------------------------------------------------------------


def test_chapters_from_table_of_contents_with_offset() -> None:
    pages = {n: ORIGINAL_PAGES.get(n, "") for n in range(1, 113)}
    structure = detect_structure(pages)
    assert structure.method == "toc"
    uh = next(c for c in structure.chapters if c.code == "Uh")
    assert (uh.first_page, uh.last_page) == (92, 112)
    assert [c.code for c in structure.chapters][:4] == ["Ua", "Ub", "Uc", "Uh"]
    assert structure.general_pages[:8] == [4, 5, 6, 7, 8, 9, 10, 11]


def test_chapters_from_headings_when_toc_pages_are_missing() -> None:
    pages = dict(enumerate(FIXTURE["pages"], start=1))
    structure = detect_structure(pages)
    assert structure.method == "headings"
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [("Uh", 4, 24)]


@pytest.mark.parametrize(
    ("zone", "expected"),
    [
        ("Uh", "Uh"),
        ("Uba", "Ub"),
        ("Ubz1", "Ub"),
        ("1AUz1", "1AUz"),
        ("2AUl", "2AU"),
        ("AU", None),
        ("UMe", None),
    ],
)
def test_chapter_for_zone(zone: str, expected: str | None) -> None:
    chapters = [Chapter(code, code, 1, 1) for code in ("A", "Ub", "Uh", "1AU", "1AUz", "2AU")]
    found = chapter_for_zone(zone, chapters)
    assert (found.code if found else None) == expected


# ---------------------------------------------------------------------------
# Ausgabeschema und Schranken
# ---------------------------------------------------------------------------


def _strict(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        for value in node.values():
            _strict(value)
    elif isinstance(node, list):
        for value in node:
            _strict(value)


def test_output_schema_is_strict() -> None:
    _strict(OUTPUT_SCHEMA)


def _assess(output: dict[str, Any]) -> list[AssessedRule]:
    result = [assess_rule(r, {"Uh"}, DOCS, ORIGINAL_PAGES) for r in parse_output(output)]
    return [r for r in result if r is not None]


def test_assess_realistic_output() -> None:
    rules = {(r.kind, r.building_kind): r for r in _assess(uh_output())}
    street = rules[("setback_street", "main")]
    assert street.status == "effective" and street.page == 97
    assert street.params == {"mode": "range", "min_m": 5.0, "max_m": 20.0, "measured_from": "facade"}
    assert rules[("max_footprint_ratio", "main")].params["ratio"] == 0.25
    assert rules[("max_height", "main")].status == "effective"
    assert rules[("text_only", "main")].status == "text_only"
    assert ("max_footprint_ratio", "main") in rules and all(r.sector == "Uh" for r in rules.values())


def test_value_not_in_quote_and_unverified_quote_are_unknown() -> None:
    output = uh_output(footprint=0.3)
    output["rules"].append(
        rule(
            "Uh",
            "unsealed_min",
            {"ratio": 0.3},
            "Au moins 30 % de la surface doit rester en pleine terre.",
            8,
        )
    )
    rules = {r.kind: r for r in _assess(output)}
    assert rules["max_footprint_ratio"].reason == "value_not_in_quote"
    assert rules["unsealed_min"].reason == "quote_unverified"


def test_status_variants() -> None:
    quote = "Les annexes s’implantent soit en limite séparative, soit en retrait."
    output = {
        "remarks": "",
        "rules": [
            rule("Uh", "roof", {}, "Toitures : non réglementé pour les annexes.", 9, status="not_regulated"),
            rule("Uh", "fence", {}, quote, 7, status="not_regulated"),
            rule("Uh", "parking", {}, quote, 7, status="graphic_reference"),
            rule(
                "Uh", "text_only", {"summary": "invented"}, "Phrase inventée sans rapport avec le texte.", 7
            ),
            rule(
                "Uh", "max_height", {"ridge_m": 10}, "10 mètres au point le plus haut de la construction", 100
            ),
        ],
    }
    rules = {r.kind: r for r in _assess(output)}
    assert rules["roof"].reason == "not_regulated_unproven"
    assert rules["fence"].status == "not_regulated"
    assert rules["parking"].reason == "graphic_reference"
    assert "text_only" not in rules
    # Modell nennt die gedruckte Seitenzahl statt der Position im PDF
    assert rules["max_height"].status == "effective" and rules["max_height"].page == 100


def test_consensus_agreement_disagreement_and_missing() -> None:
    first = _assess(uh_output())
    second = _assess(uh_output(footprint=0.3))
    final = {(r.kind, r.building_kind): r for r in consensus([first, second], ["Uh"])}
    assert final[("setback_street", "main")].status == "effective"
    footprint = final[("max_footprint_ratio", "main")]
    assert footprint.status == "unknown" and footprint.reason == "runs_disagree"
    assert len(footprint.alternatives) == 2
    for kind in ("roof", "facade", "unsealed_min"):
        assert final[(kind, "main")].reason == "missing"
    counts = coverage(final.values())
    assert counts["mandatory_unknown"] == 4 and counts["text_only"] == 1
    assert {k for k, b in final if b == "main"} >= set(MANDATORY_KINDS)


def test_consensus_merges_any_with_main_and_flags_ambiguity() -> None:
    quote = (
        "Les constructions principales s’implantent soit en limite séparative, soit en retrait. "
        "En cas d’implantation en retrait, il doit être d’au moins 3 mètres."
    )
    run_a = _assess(
        {"remarks": "", "rules": [rule("Uh", "setback_side", {"min_m": 3}, quote, 7, building_kind="any")]}
    )
    run_b = _assess({"remarks": "", "rules": [rule("Uh", "setback_side", {"min_m": 3}, quote, 7)]})
    merged = {r.kind: r for r in consensus([run_a, run_b], ["Uh"])}
    assert merged["setback_side"].status == "effective" and merged["setback_side"].building_kind == "main"

    two = _assess(
        {
            "remarks": "",
            "rules": [
                rule("Uh", "setback_side", {"min_m": 3}, quote, 7),
                rule("Uh", "setback_side", {"min_m": 3, "allow_on_boundary": True}, quote, 7),
            ],
        }
    )
    single = {r.kind: r for r in consensus([two], ["Uh"])}
    assert single["setback_side"].reason == "ambiguous"


def test_parse_output_skips_malformed_entries() -> None:
    output = {
        "remarks": "",
        "rules": [
            {"kind": "unknown_kind"},
            rule("Uh", "max_height", {"ridge_m": 10}, "x", 1) | {"building_kind": "garage"},
            rule("Uh", "setback_side", {"min_m": 3}, "x", 1)
            | {"params": [{"name": "min_m", "number": 3, "text": None, "flag": None, "items": []}] * 2},
        ],
    }
    parsed = parse_output(output)
    assert len(parsed) == 1 and parsed[0].duplicate_params == ["min_m"]
    with pytest.raises(ValueError):
        parse_output({"remarks": ""})
