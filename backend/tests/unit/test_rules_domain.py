"""Fachlogik G2 ohne Datenbank: Regelarten, Zitatprüfung, Kapitelsuche, Schranken, Gegenprüfung.

Texte stammen aus dem règlement écrit des PLUi Erdre et Gesvres (Stand 04.03.2026, Treillières).
"""

from dataclasses import replace
from typing import Any

import pytest

from app.rules.domain.assess import (
    AssessedRule,
    DocumentPages,
    assess_rule,
    claim_for,
    collapse,
    complete,
    coverage,
    match_sector,
    verify,
)
from app.rules.domain.chapters import Chapter, chapter_for_zone, detect_structure
from app.rules.domain.extraction import (
    OUTPUT_SCHEMA,
    VERIFICATION_SCHEMA,
    ExtractedRule,
    parse_output,
    parse_verification,
    prompt_fingerprint,
)
from app.rules.domain.kinds import MANDATORY_KINDS, ParamProblem, params_equal, validate_params
from app.rules.domain.text import normalize, states_not_regulated, values_in_quote, verify_quote
from tests.rules_support import fixture_json, rule, uh_output, verification_output

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


def test_minimum_with_upper_limit_is_a_band() -> None:
    """Sonst ginge die Obergrenze des Baubands in der Anzeige und später im Baurahmen verloren."""
    assert validate_params("setback_street", {"mode": "min", "min_m": 5.0, "max_m": 20.0})["mode"] == "range"
    assert validate_params("setback_street", {"min_m": 5.0, "max_m": 20.0})["mode"] == "range"


def test_band_only_for_a_band() -> None:
    """`band` sagt, ob der ganze Baukörper im Band liegt (G3 3.3); ohne Band ist die Angabe gegenstandslos
    und entfällt, statt die Regel ungültig zu machen."""
    band = validate_params("setback_street", {"min_m": 5.0, "max_m": 20.0, "band": "building"})
    assert band["band"] == "building"
    assert "band" not in validate_params("setback_street", {"mode": "min", "min_m": 5.0, "band": "facade"})
    with pytest.raises(ParamProblem):
        validate_params("setback_street", {"min_m": 5.0, "max_m": 20.0, "band": "bande"})


@pytest.mark.parametrize(
    ("kind", "params", "reason"),
    [
        ("max_footprint_ratio", {"ratio": 40}, "implausible"),
        ("max_height", {"ridge_m": 90.0}, "implausible"),
        ("setback_street", {"mode": "min"}, "invalid_params"),
        ("setback_street", {"mode": "range", "min_m": 20.0, "max_m": 5.0}, "invalid_params"),
        ("setback_street", {"mode": "fixed", "min_m": 5.0, "max_m": 20.0}, "invalid_params"),
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


STREET_PAGE = {
    10: "Les constructions principales doivent être implantées avec un recul minimum de 5 mètres "
    "par rapport à l'alignement des voies. Les annexes sont implantées librement."
}


def test_number_after_ellipsis_must_be_found() -> None:
    """Ein zu kurzer Abschnitt nach „…“ ließ vorher jede Zahl zu (Text 5 m, Zitat „… 2 m“)."""
    invented = "Les constructions principales doivent être implantées avec un recul minimum de … 2 m"
    assert not verify_quote(invented, STREET_PAGE, 10).verified
    shortened = "Les constructions principales doivent être implantées … par rapport à l'alignement des voies"
    assert verify_quote(shortened, STREET_PAGE, 10).verified
    reordered = "par rapport à l'alignement des voies … Les constructions principales doivent être implantées"
    assert not verify_quote(reordered, STREET_PAGE, 10).verified


def test_missing_negation_is_rejected() -> None:
    page = {
        10: "Les constructions ne sont pas autorisées en limite séparative. Elles doivent respecter un "
        "retrait d'au moins 3 mètres par rapport aux limites séparatives."
    }
    without = (
        "Les constructions sont autorisées en limite séparative. Elles doivent respecter un retrait "
        "d'au moins 3 mètres par rapport aux limites séparatives."
    )
    assert not verify_quote(without, page, 10).verified
    assert verify_quote(page[10], page, 10).verified


def test_values_in_quote_accepts_percent_and_inverse_only_where_meaningful() -> None:
    assert values_in_quote({"ratio": 0.25}, "limitée à 25% de la surface") == []
    assert (
        values_in_quote({"height_factor": 0.5, "min_m": 3.0}, "au moins égal à H/2 sans être inférieur à 3 m")
        == []
    )
    assert (
        values_in_quote({"spaces_per_m2_sdp": 0.02}, "1 place par tranche de 50 m² de surface de plancher")
        == []
    )
    assert values_in_quote({"eave_m": 7.0, "ridge_m": 12.0}, "ne doit pas excéder 7 mètres à l’égout") == [
        "ridge_m"
    ]
    # Kehrwert gilt nicht für Längen: „H/2“ belegt keinen Mindestabstand von 0,5 m
    assert values_in_quote({"min_m": 0.5}, "au moins égal à H/2 sans être inférieur à 3 m") == ["min_m"]


def test_not_regulated_markers() -> None:
    assert states_not_regulated("Article 9 – Emprise au sol : Non règlementé.")
    assert states_not_regulated("Il n’est pas fixé de règle.")
    assert states_not_regulated("Sans objet")
    assert not states_not_regulated("Les annexes s’implantent soit en limite séparative, soit en retrait.")


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


def test_articles_in_table_of_contents_do_not_end_the_chapter() -> None:
    toc = "\n".join(
        [
            "SOMMAIRE",
            "CHAPITRE 1 : LA ZONE Ua .......................... 3",
            "Article Ua 1 – Destinations ....................... 4",
            "Article Ua 2 – Implantation ....................... 5",
            "CHAPITRE 2 : LA ZONE Ub .......................... 7",
            "Section 1 – Implantation .......................... 8",
            "ANNEXES ........................................... 9",
        ]
    )
    pages = dict.fromkeys(range(1, 11), "")
    pages[1] = toc
    pages[3] = "CHAPITRE 1 : LA ZONE Ua\nDispositions"
    pages[7] = "CHAPITRE 2 : LA ZONE Ub\nDispositions"
    structure = detect_structure(pages)
    assert [(c.code, c.first_page, c.last_page) for c in structure.chapters] == [("Ua", 3, 6), ("Ub", 7, 8)]


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


def test_output_schemas_are_strict() -> None:
    _strict(OUTPUT_SCHEMA)
    _strict(VERIFICATION_SCHEMA)
    assert len(prompt_fingerprint()) == 16


def _assess(output: dict[str, Any], sectors: frozenset[str] = frozenset({"Uh"})) -> list[AssessedRule]:
    result = [
        replace(a, sources=(n,))
        for n, r in enumerate(parse_output(output), start=1)
        if (a := assess_rule(r, set(sectors), DOCS, ORIGINAL_PAGES)) is not None
    ]
    return result


def test_assess_realistic_output() -> None:
    rules = {(r.kind, r.building_kind): r for r in _assess(uh_output())}
    street = rules[("setback_street", "main")]
    assert street.status == "effective" and street.page == 97
    assert street.params == {
        "mode": "range",
        "min_m": 5.0,
        "max_m": 20.0,
        "band": "building",
        "measured_from": "facade",
    }
    assert rules[("max_footprint_ratio", "main")].params["ratio"] == 0.25
    assert rules[("max_height", "main")].status == "effective"
    assert rules[("setback_side", "main")].status == "effective"
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
    # Ein echter Satz ohne „non réglementé“ belegt nicht, dass nichts geregelt ist
    assert rules["fence"].status == "unknown" and rules["fence"].detail == "no_marker"
    assert rules["parking"].reason == "graphic_reference"
    assert "text_only" not in rules
    # Modell nennt die gedruckte Seitenzahl statt der Position im PDF
    assert rules["max_height"].status == "effective" and rules["max_height"].page == 100


def _single(
    sector: str, kind: str, params: dict[str, Any], quote: str, text: str, **kwargs: Any
) -> AssessedRule:
    extracted = ExtractedRule(
        sector=sector,
        kind=kind,
        building_kind="main",
        status=kwargs.get("status", "regulated"),
        params=params,
        document="chapter",
        page=1,
        quote=quote,
        confidence=0.9,
        notes="",
    )
    result = assess_rule(extracted, set(kwargs.get("sectors", {sector})), DocumentPages([], [10]), {10: text})
    assert result is not None
    return result


def test_not_regulated_with_marker_is_accepted() -> None:
    text = "Article Uh 11 – Clôtures : non réglementé. Article Uh 12 – Stationnement."
    result = _single(
        "Uh", "fence", {}, "Article Uh 11 – Clôtures : non réglementé.", text, status="not_regulated"
    )
    assert result.status == "not_regulated"


def test_value_of_another_sector_is_rejected() -> None:
    text = (
        "Le recul par rapport à l'alignement est de 5 mètres en zone Ub et de 3 mètres dans le secteur Uba."
    )
    sectors = {"Ub", "Uba"}
    wrong = _single("Ub", "setback_street", {"mode": "min", "min_m": 3.0}, text, text, sectors=sectors)
    assert wrong.status == "unknown" and wrong.reason == "sector_mismatch" and wrong.detail == "Uba"
    assert _single(
        "Ub", "setback_street", {"mode": "min", "min_m": 5.0}, text, text, sectors=sectors
    ).status == ("effective")
    assert _single(
        "Uba", "setback_street", {"mode": "min", "min_m": 3.0}, text, text, sectors=sectors
    ).status == ("effective")
    before = "En zone Ub, le recul est de 5 mètres, sauf dans le secteur Uba où il est de 3 mètres."
    assert _single("Ub", "setback_street", {"min_m": 3.0}, before, before, sectors=sectors).reason == (
        "sector_mismatch"
    )
    assert (
        _single("Ub", "setback_street", {"min_m": 5.0}, before, before, sectors=sectors).status == "effective"
    )
    listed = "Dans les secteurs Ub et Uba, le recul est de 5 mètres minimum par rapport à l'alignement."
    for sector in sectors:
        assert _single(sector, "setback_street", {"min_m": 5.0}, listed, listed, sectors=sectors).status == (
            "effective"
        )


def test_reciprocal_is_no_proof_for_a_distance() -> None:
    text = (
        "La distance aux limites séparatives est au moins égale à la moitié de la hauteur (H/2) "
        "sans pouvoir être inférieure à 3 mètres."
    )
    params = {"min_m": 0.5, "height_factor": 0.5, "height_basis": "eave"}
    result = _single("Uh", "setback_side", params, text, text)
    assert result.reason == "value_not_in_quote" and result.detail == "min_m"


def test_sector_names_are_matched_without_case_and_prefix() -> None:
    assert match_sector("secteur UH", ["Uh", "Uha"]) == "Uh"
    assert match_sector("Uba", ["Ub", "Uba"]) == "Uba"
    assert match_sector("uB", ["Ub", "UB"]) is None  # nicht eindeutig


def test_verification_agreement_disagreement_and_missing() -> None:
    output = uh_output()
    extracted = parse_output(output)
    rules = collapse(_assess(output))
    claims = [c for n, r in enumerate(extracted, start=1) if (c := claim_for(n, r, ["Uh"])) is not None]
    assert all("min_m" not in str(c) and c["sector"] == "Uh" for c in claims)  # ohne Werte, ohne Fremdsektor
    checks = parse_verification(verification_output(uh_output(footprint=0.3), claims))
    final = {(r.kind, r.building_kind): r for r in complete(verify(rules, checks), ["Uh"])}
    assert final[("setback_street", "main")].status == "effective"
    footprint = final[("max_footprint_ratio", "main")]
    assert footprint.status == "unknown" and footprint.reason == "runs_disagree"
    assert len(footprint.alternatives) == 2
    for kind in ("roof", "facade", "unsealed_min"):
        assert final[(kind, "main")].reason == "missing"
    counts = coverage(final.values())
    assert counts["mandatory_unknown"] == 4 and counts["text_only"] == 1
    assert {k for k, b in final if b == "main"} >= set(MANDATORY_KINDS)

    unanswered = {(r.kind, r.building_kind): r for r in verify(rules, {})}
    assert unanswered[("setback_street", "main")].alternatives[-1] == {"status": "absent"}


def test_collapse_merges_any_with_main_and_flags_ambiguity() -> None:
    quote = (
        "Les constructions principales s’implantent soit en limite séparative, soit en retrait. "
        "En cas d’implantation en retrait, il doit être d’au moins 3 mètres."
    )
    merged = collapse(
        _assess(
            {
                "remarks": "",
                "rules": [
                    rule("Uh", "setback_side", {"min_m": 3}, quote, 7, building_kind="any"),
                    rule("Uh", "setback_side", {"min_m": 3}, quote, 7),
                ],
            }
        )
    )
    assert len(merged) == 1 and merged[0].status == "effective" and merged[0].sources == (1, 2)

    two = _assess(
        {
            "remarks": "",
            "rules": [
                rule("Uh", "setback_side", {"min_m": 3}, quote, 7),
                rule("Uh", "setback_side", {"min_m": 3, "allow_on_boundary": True}, quote, 7),
            ],
        }
    )
    single = {r.kind: r for r in collapse(two)}
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
    with pytest.raises(ValueError):
        parse_verification({"remarks": ""})
