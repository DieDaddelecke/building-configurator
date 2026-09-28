"""Nachsuche ohne Datenbank: Antwort lesen, Aufgabe, Lücken bestimmen, Funde einarbeiten
(docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.5–3.7)."""

import json
from typing import Any

import httpx
import openai
import pytest

from app.config import Settings
from app.integrations.openrouter import GAP_TOOL, ExtractionError, ExtractionRequest, OpenRouterExtractor
from app.rules.domain.assess import AssessedRule, DocumentPages, fill_gaps, rule_key
from app.rules.domain.extraction import gap_instruction, parse_gaps
from app.rules.extract import find_gaps
from tests.rules_support import rule


def _assessed(kind: str, status: str, building_kind: str = "main", **values: Any) -> AssessedRule:
    return AssessedRule(
        sector="UC",
        kind=kind,
        building_kind=building_kind,
        status=status,  # type: ignore[arg-type]
        reason=values.get("reason"),
        params=values.get("params", {}),
        page=values.get("page"),
        quote=values.get("quote"),
        quote_verified=status == "effective",
        similarity=1.0,
        confidence=0.9,
        notes="",
    )


def test_parse_gaps_keeps_valid_verdicts_and_rules() -> None:
    roof = rule("UC", "roof", {"pitch_min_deg": 30, "pitch_max_deg": 45}, "Les toitures …", 7)
    data = {
        "gaps": [
            {"gap": 1, "verdict": "found", "rules": [roof], "searched": ""},
            {"gap": 2, "verdict": "maybe", "rules": [], "searched": ""},
            {"gap": 3, "verdict": "absent", "rules": [], "searched": "Art. 11"},
        ],
        "passages": [
            {"passage": 1, "verdict": "out_of_scope", "rules": [], "reason": "networks", "note": ""},
            {"passage": 2, "verdict": "out_of_scope", "rules": [], "reason": "weather", "note": ""},
        ],
        "remarks": "",
    }
    result = parse_gaps(data)
    assert sorted(result.gaps) == [1, 3] and result.gaps[1].rules[0].kind == "roof"
    assert result.gaps[3].searched == "Art. 11"
    assert list(result.passages) == [1] and result.passages[1].reason == "networks"


def test_gap_instruction_names_terms_previous_finding_and_pages() -> None:
    payload = {
        "gaps": [
            {
                "gap": 1,
                "sector": "UC",
                "kind": "max_height",
                "building_kind": "main",
                "terms": ["hauteur", "faitage"],
                "article": "10",
                "previous": {
                    "reason": "quote_unverified",
                    "quote": "La hauteur …",
                    "params": {"ridge_m": 9.0},
                },
            }
        ],
        "passages": [{"passage": 1, "page": 6, "text": "Les débords de toit sont interdits."}],
    }
    text = gap_instruction(payload, "UC", [5, 6], list(range(9, 21)), [3])
    assert text.startswith("Gap search.")
    assert "the third PDF pages 3." in text and "Usual article in older PLU: 10." in text
    assert 'Previous finding: quote_unverified; quote "La hauteur …"; values {"ridge_m": 9.0}.' in text
    assert 'Passage 1 (page 6): "Les débords de toit sont interdits."' in text
    assert "there is no third PDF" in gap_instruction(payload, "UC", [], [9], [])


def test_gap_request_sends_a_third_document_and_its_own_tool() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(400, json={"error": {"message": "stop here"}})

    settings = Settings(openrouter_api_key="test-key")  # type: ignore[arg-type]
    client = openai.OpenAI(
        api_key="k",
        base_url=settings.openrouter_base_url,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    request = ExtractionRequest(
        chapter_code="UC",
        sectors=["UC"],
        chapter_pdf=b"",
        chapter_pages=[9],
        general_pdf=None,
        general_pages=[],
        chapter_text="=== page 1 ===\nArticle UC 9",
        gaps={"gaps": [], "passages": []},
        extra_pages=[3],
        extra_text="=== page 1 ===\nLexique",
    )
    with pytest.raises(ExtractionError):  # nur die Anfrage zählt
        OpenRouterExtractor(settings, client).extract(request)
    body = seen["body"]
    content = body["messages"][1]["content"]
    assert [block["text"].split("\n")[0] for block in content[:2]] == [
        '<document name="chapter-UC.pdf">',
        '<document name="extra.pdf">',
    ]
    assert body["tools"][0]["function"]["name"] == GAP_TOOL and "the third PDF pages 3" in content[-1]["text"]


CHAPTER_TEXT = "Les clôtures ne doivent pas excéder 2 mètres. Les piscines doivent respecter un retrait."


def test_find_gaps_lists_open_mandatory_kinds_mentioned_kinds_and_building_kinds() -> None:
    rules = [
        _assessed("setback_rear", "effective", "any", params={"min_m": 5.0}),
        _assessed("setback_side", "effective", "main", params={"min_m": 3.0}),
        _assessed("max_height", "unknown", reason="quote_unverified", quote="La hauteur", params={}),
        _assessed("max_footprint_ratio", "unknown", reason="graphic_reference", quote="voir plan"),
    ]
    gaps = {(g.kind, g.building_kind): g for g in find_gaps(rules, ["UC"], CHAPTER_TEXT)}
    assert ("setback_rear", "main") not in gaps and ("setback_side", "main") not in gaps
    assert ("max_footprint_ratio", "main") not in gaps  # Wert im Plan: die Nachsuche klärt das nicht
    assert gaps[("max_height", "main")].request()["previous"]["reason"] == "quote_unverified"
    assert {("roof", "main"), ("facade", "main"), ("fence", "any"), ("setback_side", "pool")} <= set(gaps)
    # Die hintere Regel gilt für alle Baukörper, die seitliche nur für das Hauptgebäude
    assert ("setback_rear", "pool") not in gaps and ("setback_street", "main") in gaps
    assert [g.number for g in find_gaps(rules, ["UC"], CHAPTER_TEXT)] == list(range(1, len(gaps) + 1))


def test_fill_gaps_replaces_marks_and_keeps() -> None:
    key = rule_key("UC", "roof", "main")
    height = _assessed("max_height", "unknown", reason="runs_disagree", quote="La hauteur maximale …")
    rules = [_assessed("setback_side", "effective", params={"min_m": 3.0}), height]
    found = [
        _assessed("roof", "effective", params={"pitch_min_deg": 30.0}, page=15),
        _assessed("max_height", "unknown", reason="quote_unverified", quote="autre"),
        _assessed("text_only", "text_only", "any", params={"summary": "Staffel"}, page=14, quote="Si la …"),
    ]
    gap_keys = {
        key,
        rule_key("UC", "facade", "main"),
        rule_key("UC", "max_footprint_ratio", "main"),
        rule_key("UC", "fence", "any"),
        rule_key("UC", "max_height", "main"),
    }
    merged = fill_gaps(
        rules,
        found,
        gap_keys,
        absent={rule_key("UC", "facade", "main"): "Art. 11", rule_key("UC", "fence", "any"): "Art. 11"},
        not_expressible={rule_key("UC", "max_footprint_ratio", "main"): "14"},
    )
    result = {(r.kind, r.building_kind): r for r in merged}
    assert result[("roof", "main")].status == "effective"
    assert (result[("facade", "main")].reason, result[("facade", "main")].detail) == (
        "not_found_after_search",
        "Art. 11",
    )
    assert (
        result[("max_footprint_ratio", "main")].reason,
        result[("max_footprint_ratio", "main")].detail,
    ) == (
        "not_expressible",
        "14",
    )
    assert ("fence", "main") not in result  # keine Pflichtart: nicht gefunden heißt keine Regel
    assert result[("max_height", "main")] == height  # der frühere Befund mit Zitat bleibt
    assert result[("text_only", "any")].params == {"summary": "Staffel"}


def test_extra_pages_map_back_to_original_pages() -> None:
    documents = DocumentPages(general=[5, 6], chapter=list(range(9, 21)), extra=[2, 31])
    assert documents.original_page("extra", 2) == 31
    assert documents.original_page("general", 1) == 5 and documents.original_page("chapter", 3) == 11


def test_fill_gaps_drops_a_hint_that_repeats_a_known_one() -> None:
    known = _assessed(
        "text_only",
        "text_only",
        "any",
        params={"summary": "Staffel"},
        page=14,
        quote="Si la surface du terrain est supérieure à 200 m², l’emprise au sol maximale des constructions "
        "est - de 90 %",
    )
    again = _assessed(
        "text_only",
        "text_only",
        "any",
        params={"summary": "Emprise dégressive"},
        page=14,
        quote="l'emprise au sol maximale des constructions est - de 90 % pour les premiers 200 m²",
    )
    other = _assessed(
        "text_only",
        "text_only",
        "any",
        params={"summary": "Débords"},
        page=15,
        quote="Les débords de toit sont interdits.",
    )
    merged = fill_gaps([known], [again, other], set(), {}, {})
    assert sorted(r.params["summary"] for r in merged) == ["Débords", "Staffel"]
