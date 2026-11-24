"""Rangfolge allgemein → Zone → Sektor → Plan, Ergänzungen und Überlagerungen (S9d, Vorgabe Soheyl
24.11.2026)."""

from typing import Any

from app.rules.domain.assess import AssessedRule, DocumentPages, assess_rule, collapse
from app.rules.domain.extraction import parse_output
from app.rules.domain.precedence import stricter
from tests.rules_support import rule

GENERAL_QUOTE = "La hauteur maximale des constructions est fixée à 14 mètres au faîtage."
ZONE_QUOTE = "Dans la zone UD1, la hauteur maximale des constructions est de 9 mètres au faîtage."
SECTOR_QUOTE = "Dans le secteur UD1h, la hauteur maximale des constructions est de 7 mètres au faîtage."
COMPLEMENT_QUOTE = "En outre, la hauteur maximale des constructions est de 16 mètres au faîtage."
FLOOD_QUOTE = "Dans les zones inondables du PPRI, la hauteur maximale est de 6 mètres au faîtage."
PLAN_QUOTE = "La hauteur maximale des constructions est définie au règlement graphique."

PAGES = {
    3: GENERAL_QUOTE + "\n" + COMPLEMENT_QUOTE,
    4: FLOOD_QUOTE,
    10: ZONE_QUOTE + "\n" + PLAN_QUOTE,
    11: SECTOR_QUOTE + "\n" + COMPLEMENT_QUOTE,
}
DOCUMENTS = DocumentPages(general=[3, 4], chapter=[10, 11])


def _assessed(*items: dict[str, Any], sectors: frozenset[str] = frozenset({"UD1h"})) -> list[AssessedRule]:
    answer = parse_output({"remarks": "", "rules": list(items)})
    result = [assess_rule(r, set(sectors), DOCUMENTS, PAGES) for r in answer]
    return [r for r in result if r is not None]


def _height(quote: str, page: int, value: float, sector: str = "UD1h", **kw: Any) -> dict[str, Any]:
    document = "general" if page in DOCUMENTS.general else "chapter"
    params = {"ridge_m": value} if value else {}
    return rule(sector, "max_height", params, quote, DOCUMENTS_POSITION[page], document=document, **kw)


DOCUMENTS_POSITION = {3: 1, 4: 2, 10: 1, 11: 2}
"""Position der Seite im gesendeten PDF (allgemein bzw. Kapitel), wie das Modell sie nennt."""


def test_zone_replaces_general_and_keeps_it_visible() -> None:
    """Allgemein 14 m, Zone 9 m → 9 m; früher `ambiguous`."""
    rules = _assessed(_height(GENERAL_QUOTE, 3, 14), _height(ZONE_QUOTE, 10, 9))
    assert [r.level for r in rules] == ["general", "zone"]
    (height,) = collapse(rules)
    assert height.status == "effective" and height.params["ridge_m"] == 9
    (superseded,) = height.alternatives
    assert superseded["role"] == "superseded" and superseded["level"] == "general"
    assert superseded["params"]["ridge_m"] == 14 and superseded["page"] == 3
    assert superseded["quote"] == GENERAL_QUOTE


def test_sector_replaces_zone_and_general() -> None:
    rules = _assessed(
        _height(GENERAL_QUOTE, 3, 14),
        _height(ZONE_QUOTE, 10, 9),
        _height(SECTOR_QUOTE, 11, 7),
        sectors=frozenset({"UD1", "UD1h"}),
    )
    sector_rules = [r for r in rules if r.sector == "UD1h"]
    assert [r.level for r in sector_rules] == ["general", "zone", "sector"]
    (height,) = collapse(sector_rules)
    assert height.params["ridge_m"] == 7
    assert [a["level"] for a in height.alternatives] == ["general", "zone"]


def test_plan_reference_beats_text_values() -> None:
    rules = _assessed(_height(ZONE_QUOTE, 10, 9), _height(PLAN_QUOTE, 10, 0, status="graphic_reference"))
    (height,) = collapse(rules)
    assert height.status == "unknown" and height.reason == "graphic_reference" and height.level == "plan"
    assert height.alternatives[0]["role"] == "superseded" and height.alternatives[0]["params"]["ridge_m"] == 9


def test_complement_applies_both_and_the_stricter_wins() -> None:
    """„en outre“ in der Zone: beide gelten; 9 m allgemein ist strenger als 16 m."""
    general = AssessedRule(
        sector="UD1h",
        kind="max_height",
        building_kind="main",
        status="effective",
        reason=None,
        params={"ridge_m": 9.0},
        page=3,
        quote="La hauteur maximale est de 9 mètres au faîtage.",
        quote_verified=True,
        similarity=1.0,
        confidence=1.0,
        notes="",
        level="general",
    )
    zone = AssessedRule(
        **{**general.__dict__, "params": {"ridge_m": 16.0}, "page": 11, "quote": COMPLEMENT_QUOTE}
    )
    zone = AssessedRule(**{**zone.__dict__, "level": "zone"})
    (height,) = collapse([general, zone])
    assert height.params["ridge_m"] == 9 and height.level == "general"
    assert (
        height.alternatives[0]["role"] == "also_applies" and height.alternatives[0]["params"]["ridge_m"] == 16
    )


def test_overlay_applies_when_stricter_and_shows_the_other() -> None:
    rules = _assessed(_height(ZONE_QUOTE, 10, 9), _height(FLOOD_QUOTE, 4, 6))
    assert rules[1].level == "overlay"
    (height,) = collapse(rules)
    assert height.params["ridge_m"] == 6 and height.level == "overlay"
    assert height.alternatives[0]["role"] == "overlaid" and height.alternatives[0]["params"]["ridge_m"] == 9

    looser = _assessed(_height(ZONE_QUOTE, 10, 9), _height(FLOOD_QUOTE, 4, 6))
    looser[1] = AssessedRule(**{**looser[1].__dict__, "params": {**looser[1].params, "ridge_m": 12.0}})
    (height,) = collapse(looser)
    assert height.params["ridge_m"] == 9 and height.alternatives[0]["role"] == "overlay"


def test_same_level_conflict_stays_ambiguous() -> None:
    rules = _assessed(_height(ZONE_QUOTE, 10, 9), _height(SECTOR_QUOTE, 11, 7))
    # Ohne angefragte Zone über dem Sektor ist „UD1h“ im Zitat kein Sektor einer Zone: beide Zone
    assert {r.level for r in rules} == {"zone"}
    (height,) = collapse(rules)
    assert height.status == "unknown" and height.reason == "ambiguous" and len(height.alternatives) == 2


def test_overlay_without_clear_strictness_stays_ambiguous() -> None:
    rules = _assessed(_height(ZONE_QUOTE, 10, 9), _height(FLOOD_QUOTE, 4, 6))
    # Zone: First niedriger, Überlagerung: Traufe niedriger – keine Fassung ist in allem strenger
    rules[0] = AssessedRule(**{**rules[0].__dict__, "params": {**rules[0].params, "eave_m": 6.0}})
    rules[1] = AssessedRule(
        **{**rules[1].__dict__, "params": {**rules[1].params, "ridge_m": 12.0, "eave_m": 4.0}}
    )
    (height,) = collapse(rules)
    assert height.reason == "ambiguous"


def test_stricter() -> None:
    assert stricter("max_height", "effective", {"ridge_m": 9}, "effective", {"ridge_m": 14}) == "a"
    assert stricter("setback_side", "effective", {"min_m": 3}, "effective", {"min_m": 4}) == "b"
    assert stricter("unsealed_min", "effective", {"ratio": 0.3}, "effective", {"ratio": 0.2}) == "a"
    assert stricter("max_footprint_ratio", "effective", {"ratio": 0.3}, "effective", {"ratio": 0.2}) == "b"
    assert stricter("max_height", "effective", {"ridge_m": 9}, "effective", {"ridge_m": 9.0}) == "equal"
    assert stricter("max_height", "effective", {"ridge_m": 9}, "not_regulated", {}) == "a"
    assert stricter("max_height", "unknown", {}, "effective", {"ridge_m": 9}) is None
    assert (
        stricter(
            "setback_side",
            "effective",
            {"min_m": 3, "allow_on_boundary": True},
            "effective",
            {"min_m": 4, "allow_on_boundary": False},
        )
        is None
    )
