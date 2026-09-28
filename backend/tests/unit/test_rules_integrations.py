"""Adapter G2 mit aufgezeichneten Antworten: GPU (Treillières, 14.09.2026), OpenRouter (simulierter Strom)."""

import json
from dataclasses import replace
from typing import Any

import httpx
import openai
import pytest

from app.config import Settings
from app.integrations import gpu, openrouter
from app.integrations.http import ExternalServiceError
from app.integrations.openrouter import (
    EXTRACTION_TOOL,
    ExtractionError,
    ExtractionRequest,
    OpenRouterExtractor,
)
from app.rules.domain.extraction import TEXT_INPUT_NOTE
from app.rules.plan_import import choose_partition
from tests.rules_support import DOC_ID, fixture_json, text_pdf, uh_output


def test_features_refuse_truncated_answers() -> None:
    with pytest.raises(ExternalServiceError, match="truncated"):
        gpu._features({"features": [], "numberMatched": 1200, "numberReturned": 1000}, "zone-urba")


def test_regulation_file_and_partition_choice() -> None:
    details = fixture_json(f"document-{DOC_ID}.json")
    doc = gpu.GpuDocument(
        id=details["id"],
        partition=details["name"],
        du_type=details["type"],
        title=details["title"],
        legal_status=details["legalStatus"],
        effective_status=details["effectiveStatus"],
        update_date=details["updateDate"],
        files=[gpu.GpuFile(f["name"], f["title"], f.get("path")) for f in details["files"]],
    )
    assert [f.name for f in gpu.regulation_files(doc)] == ["244400503_reglement_20260304.pdf"]
    volumes = gpu.GpuDocument(
        **{
            **doc.__dict__,
            "files": [*doc.files, gpu.GpuFile("x_reglement_tome2.pdf", "Règlement écrit – Tome 2", None)],
        }
    )
    assert len(gpu.regulation_files(volumes)) == 2  # plan_import wertet mehrere Bände nicht aus
    zones = [
        gpu.GpuFeature("zone-urba", f["properties"], f["geometry"])
        for f in fixture_json("zone-urba-44209.json")["features"]
    ]
    commune = fixture_json("municipality-44209.json")["features"][0]["geometry"]
    # Die Fixture enthält auch Zonen des Nachbarplans Nantes Métropole (DU_244400404)
    assert {z.properties["partition"] for z in zones} == {"DU_244400503", "DU_244400404"}
    assert choose_partition(commune, zones) == ("DU_244400503", DOC_ID)


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------


def _completion(
    arguments: dict[str, Any],
    *,
    finish_reason: str = "tool_calls",
    model: str = "test-model",
    tool_name: str = EXTRACTION_TOOL,
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {
            "prompt_tokens": 91200,
            "completion_tokens": 4000,
            "total_tokens": 95200,
            "prompt_tokens_details": {"cached_tokens": 90000},
        },
    }


def _extractor(handler: Any) -> OpenRouterExtractor:
    settings = Settings(openrouter_api_key="test-key")  # type: ignore[arg-type]
    client = openai.OpenAI(
        api_key="test-key",
        base_url=settings.openrouter_base_url,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    return OpenRouterExtractor(settings, client)


REQUEST = ExtractionRequest(
    chapter_code="Uh",
    sectors=["Uh"],
    chapter_pdf=text_pdf(["page 92", "page 93"]),
    chapter_pages=[92, 93],
    general_pdf=text_pdf(["page 4"]),
    general_pages=[4],
)


def test_openrouter_request_shape_and_response() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion(uh_output()))

    response = _extractor(handler).extract(REQUEST)
    body = seen["body"]
    assert body["model"] == "anthropic/claude-opus-5"
    assert body["tool_choice"] == {"type": "function", "function": {"name": EXTRACTION_TOOL}}
    assert body["tools"][0]["function"]["name"] == EXTRACTION_TOOL
    assert body["reasoning"] == {"effort": "high"}
    files = [b for b in body["messages"][1]["content"] if b["type"] == "file"]
    assert len(files) == 2
    assert all(f["file"]["file_data"].startswith("data:application/pdf;base64,") for f in files)
    assert "Uh" in body["messages"][1]["content"][-1]["text"]
    assert response.output["rules"][0]["kind"] == "setback_street"
    assert response.usage["cache_read_input_tokens"] == 90000 and response.usage["output_tokens"] == 4000
    assert response.usage["input_tokens"] == 1200
    # 1.200 × 5 $ + 4.000 × 25 $ + 90.000 × 0,5 $ (Zwischenspeicher, gemeldet über OpenRouter) je Million
    assert response.cost_usd == pytest.approx(0.151, abs=0.001)


def test_text_input_replaces_the_pdfs_and_explains_the_page_marks() -> None:
    """PU12: Modelle ohne PDF-Eingabe bekommen die Textschicht, benannt wie die PDFs."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion(uh_output()))

    request = replace(
        REQUEST,
        chapter_pdf=b"",
        general_pdf=None,
        chapter_text="=== page 1 ===\nArticle Uh 6",
        general_text="=== page 1 ===\nDéfinitions",
    )
    _extractor(handler).extract(request)
    content = seen["body"]["messages"][1]["content"]
    assert [block["type"] for block in content] == ["text", "text", "text"]
    assert content[0]["text"] == '<document name="general.pdf">\n=== page 1 ===\nDéfinitions\n</document>'
    assert content[1]["text"].startswith('<document name="chapter-Uh.pdf">\n=== page 1 ===')
    assert content[2]["text"].startswith(TEXT_INPUT_NOTE) and "Uh" in content[2]["text"]


def test_a_model_without_forced_tool_call_gets_the_choice_and_a_hint() -> None:
    """Opus 5.5 lehnt den erzwungenen Funktionsaufruf ab (bei allen Anbietern); einmal abgelehnt, fragt der
    Prozess das Modell gleich mit `auto` (PLAN_G2_VOLLSTAENDIGKEIT 3.2)."""
    openrouter._WITHOUT_FORCED_TOOL.clear()
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if body["tool_choice"] != "auto":
            message = 'tool_choice: type "tool" and "any" are not supported for this model.'
            raw = json.dumps(
                {"type": "error", "error": {"type": "invalid_request_error", "message": message}}
            )
            return httpx.Response(
                400, json={"error": {"message": "Provider returned error", "metadata": {"raw": raw}}}
            )
        return httpx.Response(200, json=_completion(uh_output()))

    extractor = _extractor(handler)
    assert extractor.extract(REQUEST).output["rules"][0]["kind"] == "setback_street"
    assert [b["tool_choice"] for b in bodies] == [
        {"type": "function", "function": {"name": EXTRACTION_TOOL}},
        "auto",
    ]
    assert bodies[1]["messages"][0]["content"].endswith(
        f"Return your result only by calling the tool {EXTRACTION_TOOL}."
    )
    extractor.extract(REQUEST)
    assert [b["tool_choice"] for b in bodies[2:]] == ["auto"]
    openrouter._WITHOUT_FORCED_TOOL.clear()


def test_other_bad_requests_are_not_retried() -> None:
    openrouter._WITHOUT_FORCED_TOOL.clear()
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "context length exceeded"}})

    with pytest.raises(ExtractionError, match="bad_request"):
        _extractor(handler).extract(REQUEST)
    assert len(calls) == 1


def test_verification_request_sends_claims_without_values() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        answer = {"checks": [{"claim": 1, "status": "regulated", "params": [], "notes": ""}], "remarks": ""}
        return httpx.Response(200, json=_completion(answer, tool_name="submit_verification"))

    claims = [
        {
            "claim": 1,
            "sector": "Uh",
            "kind": "setback_street",
            "building_kind": "main",
            "document": "chapter",
            "page": 6,
            "quote": "Les constructions principales … entre 5 m et 20m",
        }
    ]
    response = _extractor(handler).extract(replace(REQUEST, claims=claims))
    body = seen["body"]
    assert body["tools"][0]["function"]["parameters"]["required"] == ["checks", "remarks"]
    text = body["messages"][1]["content"][-1]["text"]
    assert text.startswith("Verification task") and "Claim 1: sector Uh, kind setback_street" in text
    assert response.output["checks"][0]["claim"] == 1


@pytest.mark.parametrize(
    ("status", "finish_reason", "reason", "retryable"),
    [
        (200, "length", "max_tokens", False),
        (401, None, "auth", False),
        (429, None, "rate_limited", True),
        (503, None, "http_503", True),
    ],
)
def test_openrouter_errors(status: int, finish_reason: str | None, reason: str, retryable: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if status == 200:
            return httpx.Response(200, json=_completion({}, finish_reason=finish_reason or "stop"))
        return httpx.Response(status, json={"error": {"message": "x", "type": "error"}})

    with pytest.raises(ExtractionError) as error:
        _extractor(handler).extract(REQUEST)
    assert error.value.reason == reason and error.value.retryable is retryable


def test_openrouter_requires_api_key() -> None:
    with pytest.raises(ExtractionError, match="not_configured"):
        OpenRouterExtractor(Settings(openrouter_api_key=None))


def test_empty_api_key_from_compose_counts_as_unset() -> None:
    assert Settings(openrouter_api_key="  ").openrouter_api_key is None  # type: ignore[arg-type]
    assert Settings(openrouter_api_key="sk-test").openrouter_api_key is not None  # type: ignore[arg-type]
