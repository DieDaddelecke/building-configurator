"""Referenzlisten und Messung (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.10), ohne Datenbank."""

import json

import pytest

from app.rules import reference
from app.rules.domain.passages import Passage
from app.rules.domain.reference import (
    FoundRule,
    ReferenceProblem,
    measure,
    parse_entries,
)
from app.rules.domain.text import quotes_overlap

HEIGHT_QUOTE = (
    "La hauteur maximale des constructions est de 9 mètres au faîtage et de 7 mètres à l’acrotère en cas de "
    "toiture terrasse."
)
BAND_QUOTE = (
    "Les constructions implantées sur la limite séparative de fond de parcelle ne doivent pas dépasser une "
    "hauteur de 3 mètres, sur une bande de 3 mètres le long de cette limite."
)
ENTRIES = parse_entries(
    [
        {
            "kind": "max_height",
            "building_kind": "any",
            "expected": "effective",
            "params": {"ridge_m": 9.0, "parapet_m": 7.0},
            "page": 14,
            "quote": HEIGHT_QUOTE,
        },
        {
            "kind": "max_footprint_ratio",
            "building_kind": "any",
            "expected": "not_expressible",
            "page": 14,
            "quote": "l’emprise au sol maximale des constructions est - de 90 % pour les premiers 200 m²",
        },
        {
            "kind": "text_only",
            "building_kind": "any",
            "expected": "text_only",
            "page": 14,
            "quote": BAND_QUOTE,
        },
        {
            "kind": "fence",
            "building_kind": "any",
            "expected": "effective",
            "params": {"max_height_m": 2.0},
            "page": 17,
            "quote": "La hauteur totale d’une clôture ne doit pas excéder 2 mètres.",
        },
    ]
)


def _rule(kind: str, status: str, params: dict[str, object] | None = None, **values: object) -> FoundRule:
    return FoundRule(
        kind=kind,
        building_kind=str(values.get("building_kind", "main")),
        status=status,
        reason=values.get("reason"),  # type: ignore[arg-type]
        params=params or {},
        page=values.get("page", 14),  # type: ignore[arg-type]
        quote=values.get("quote"),  # type: ignore[arg-type]
    )


def test_outcomes_per_entry() -> None:
    """Nur die Parameter der Liste zählen; `any` und `main` sind derselbe Schlüssel; ein Pauschalwert für
    eine Staffel ist falsch; ein Hinweis zählt über die Überdeckung der Zitate."""
    rules = [
        _rule("max_height", "effective", {"ridge_m": 9.0, "parapet_m": 7.0, "reference": "natural_terrain"}),
        _rule("max_footprint_ratio", "effective", {"ratio": 0.9}),
        _rule("text_only", "text_only", {"summary": "…"}, quote=BAND_QUOTE.replace("’", "'")),
        _rule("setback_street", "effective", {"min_m": 2.5}, page=12),
    ]
    result = measure(ENTRIES, rules)
    assert [r.outcome for r in result.results] == ["hit", "wrong_value", "hit", "silent_gap"]
    assert [(r.kind, r.status) for r in result.extra] == [("setback_street", "effective")]
    assert result.counts["hit"] == 2 and result.recall == pytest.approx(0.5)


def test_gaps_that_are_named_or_dismissed() -> None:
    rules = [
        _rule("max_height", "unknown", reason="quote_unverified"),
        _rule("max_footprint_ratio", "unknown", reason="not_expressible"),
        _rule("fence", "unknown", reason="missing"),
    ]
    open_passages = [Passage(14, BAND_QUOTE)]
    result = measure(ENTRIES, rules, open_passages=open_passages)
    assert [r.outcome for r in result.results] == ["named_gap", "hit", "named_gap", "named_gap"]
    dismissed = measure(ENTRIES, rules, dismissed=open_passages)
    assert dismissed.results[2].outcome == "dismissed"


def test_wrong_value_names_the_parameter() -> None:
    result = measure(ENTRIES, [_rule("max_height", "effective", {"ridge_m": 10.0, "parapet_m": 7.0})])
    assert result.results[0].outcome == "wrong_value" and result.results[0].detail == "ridge_m"


def test_quotes_overlap_despite_typography_and_ellipsis() -> None:
    assert quotes_overlap(
        BAND_QUOTE, "… ne doivent pas dépasser une hauteur de 3 mètres, sur une bande de 3 mètres"
    )
    assert not quotes_overlap(BAND_QUOTE, HEIGHT_QUOTE)
    assert not quotes_overlap(None, BAND_QUOTE)


@pytest.mark.parametrize(
    "item",
    [
        {"kind": "roofs", "building_kind": "main", "expected": "effective", "quote": "x"},
        {"kind": "roof", "building_kind": "main", "expected": "text_only", "quote": "x"},
        {
            "kind": "roof",
            "building_kind": "main",
            "expected": "effective",
            "params": {"ratio": 1},
            "quote": "x",
        },
        {"kind": "roof", "building_kind": "main", "expected": "effective", "quote": ""},
    ],
)
def test_invalid_entries_are_rejected(item: dict[str, object]) -> None:
    with pytest.raises(ReferenceProblem):
        parse_entries([item])


def test_seed_list_beyenes_uc_is_valid() -> None:
    """Die mitgelieferte Liste (Entwurf, vom Nutzer zu prüfen) muss sich laden lassen."""
    loaded = reference.load_file(reference.SEED_DIR / "beyenes_uc.json")
    assert loaded.sector == "UC" and len(loaded.sha256) == 64
    kinds = {(e.kind, e.building_kind) for e in loaded.entries if e.expected != "text_only"}
    assert ("max_footprint_ratio", "any") in kinds and ("setback_rear", "pool") in kinds
    assert sum(e.expected == "text_only" for e in loaded.entries) == 8
    with pytest.raises(ReferenceProblem):
        reference.parse_list(json.loads('{"format": "other"}'))


ANNEX_QUOTE = (
    "la distance minimale entre cette construction annexe et la construction principale ou une autre "
    "construction annexe est de 2 mètres"
)


def test_a_rule_that_is_only_visible_as_hint_counts_as_named() -> None:
    """Die Nachsuche fasst die Sonderregel kleiner Nebengebäude als Hinweis: sichtbar, aber nicht wirksam."""
    entry = parse_entries(
        [
            {
                "kind": "setback_between_buildings",
                "building_kind": "annex",
                "expected": "effective",
                "params": {"min_m": 2.0},
                "page": 13,
                "quote": ANNEX_QUOTE,
            }
        ]
    )
    hint = _rule(
        "text_only",
        "text_only",
        page=13,
        quote=ANNEX_QUOTE,
    )
    result = measure(entry, [hint])
    assert (result.results[0].outcome, result.results[0].detail) == ("named_gap", "hint")
    assert result.counts["extra_hints"] == 0
