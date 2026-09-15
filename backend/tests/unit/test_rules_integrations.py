"""Adapter G2 mit aufgezeichneten Antworten: GPU (Treillières, 14.09.2026), Claude API (simulierter Strom)."""

import json
from dataclasses import replace
from typing import Any

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.integrations import gpu
from app.integrations.claude import FALLBACK_BETA, ClaudeExtractor, ExtractionError, ExtractionRequest
from app.integrations.http import ExternalServiceError
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
# Claude API
# ---------------------------------------------------------------------------


def _sse(events: list[dict[str, Any]]) -> bytes:
    return b"".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n".encode() for e in events)


def _stream(text: str, stop_reason: str = "end_turn") -> bytes:
    return _sse(
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-opus-5",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 1200,
                        "output_tokens": 1,
                        "cache_creation_input_tokens": 90000,
                        "cache_read_input_tokens": 0,
                    },
                },
            },
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 4000},
            },
            {"type": "message_stop"},
        ]
    )


def _extractor(handler: Any) -> ClaudeExtractor:
    settings = Settings(anthropic_api_key="test-key")  # type: ignore[arg-type]
    client = anthropic.Anthropic(
        api_key="test-key", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)), max_retries=0
    )
    return ClaudeExtractor(settings, client)


REQUEST = ExtractionRequest(
    chapter_code="Uh",
    sectors=["Uh"],
    chapter_pdf=text_pdf(["page 92", "page 93"]),
    chapter_pages=[92, 93],
    general_pdf=text_pdf(["page 4"]),
    general_pages=[4],
)


def test_claude_request_shape_and_response() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(
            200,
            content=_stream(json.dumps(uh_output())),
            headers={"content-type": "text/event-stream", "request-id": "req_42"},
        )

    response = _extractor(handler).extract(REQUEST)
    body = seen["body"]
    assert body["model"] == "claude-opus-5" and body["stream"] is True
    assert body["fallbacks"] == "default" and FALLBACK_BETA in seen["beta"]
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["format"]["type"] == "json_schema"
    documents = [b for b in body["messages"][0]["content"] if b["type"] == "document"]
    assert len(documents) == 2 and all(d["cache_control"]["ttl"] == "1h" for d in documents)
    assert "Uh" in body["messages"][0]["content"][-1]["text"]
    assert response.output["rules"][0]["kind"] == "setback_street"
    assert response.usage["cache_creation_input_tokens"] == 90000 and response.usage["output_tokens"] == 4000
    # 1.200 × 5 $ + 4.000 × 25 $ + 90.000 × 10 $ (Cache 1 h) je Million
    assert response.cost_usd == pytest.approx(1.006, abs=0.001)


def test_verification_request_sends_claims_without_values() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        answer = {"checks": [{"claim": 1, "status": "regulated", "params": [], "notes": ""}], "remarks": ""}
        return httpx2.Response(
            200, content=_stream(json.dumps(answer)), headers={"content-type": "text/event-stream"}
        )

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
    assert body["output_config"]["format"]["schema"]["required"] == ["checks", "remarks"]
    text = body["messages"][0]["content"][-1]["text"]
    assert text.startswith("Verification task") and "Claim 1: sector Uh, kind setback_street" in text
    assert response.output["checks"][0]["claim"] == 1


@pytest.mark.parametrize(
    ("status", "stop_reason", "reason", "retryable"),
    [
        (200, "refusal", "refusal", False),
        (200, "max_tokens", "max_tokens", False),
        (401, None, "auth", False),
        (429, None, "rate_limited", True),
        (529, None, "http_529", True),
    ],
)
def test_claude_errors(status: int, stop_reason: str | None, reason: str, retryable: bool) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if status == 200:
            return httpx2.Response(
                200,
                content=_stream("{}", stop_reason or "end_turn"),
                headers={"content-type": "text/event-stream"},
            )
        return httpx2.Response(status, json={"type": "error", "error": {"type": "error", "message": "x"}})

    with pytest.raises(ExtractionError) as error:
        _extractor(handler).extract(REQUEST)
    assert error.value.reason == reason and error.value.retryable is retryable


def test_claude_requires_api_key() -> None:
    with pytest.raises(ExtractionError, match="not_configured"):
        ClaudeExtractor(Settings(anthropic_api_key=None))


def test_empty_api_key_from_compose_counts_as_unset() -> None:
    assert Settings(anthropic_api_key="  ").anthropic_api_key is None  # type: ignore[arg-type]
    assert Settings(anthropic_api_key="sk-test").anthropic_api_key is not None  # type: ignore[arg-type]
