"""Claude API: Regeln aus Seitenauszügen des règlement écrit (Spez. 5.2.3 Schritt 3, 9; Plan 3.4).

Nach den Vorgaben der Skill `claude-api` (Spez. 0 Punkt 6): offizielles Python-SDK, Modell aus der
Konfiguration (Standard `claude-opus-5`), adaptive Denkphase, Streaming wegen langer Ein- und Ausgaben,
strukturierte Ausgabe über JSON-Schema, serverseitiger Rückfall bei Ablehnung (`fallbacks: "default"`).
Gesendet werden nur öffentliche Planunterlagen, keine Kundendaten (L8).

Zwischenspeicher: System-Prompt, allgemeine Bestimmungen und Zonenkapitel tragen je eine Cache-Marke (1 h).
Die allgemeinen Bestimmungen sind für alle Kapitel eines Plans gleich; der zweite Lauf eines Kapitels liest
fast alles aus dem Cache.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic

from app.config import Settings
from app.platform.logging import get_logger
from app.rules.domain.extraction import OUTPUT_SCHEMA, SYSTEM_PROMPT, user_instruction

SERVICE = "claude"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_OUTPUT_TOKENS = 64000

log = get_logger("integrations.claude")


@dataclass(frozen=True)
class ExtractionRequest:
    chapter_code: str
    sectors: list[str]
    chapter_pdf: bytes
    chapter_pages: list[int]
    general_pdf: bytes | None
    general_pages: list[int]


@dataclass(frozen=True)
class ExtractionResponse:
    output: dict[str, Any]
    model: str
    request_id: str | None
    stop_reason: str | None
    usage: dict[str, int]
    served_by_fallback: bool
    duration_ms: int
    cost_usd: float


class ExtractionError(Exception):
    def __init__(self, reason: str, *, retryable: bool, usage: dict[str, int] | None = None) -> None:
        super().__init__(f"{SERVICE}: {reason}")
        self.reason = reason
        self.retryable = retryable
        self.usage = usage or {}


class RuleExtractor(Protocol):
    def extract(self, request: ExtractionRequest) -> ExtractionResponse: ...


@dataclass(frozen=True)
class Prices:
    """US-Dollar je Million Token (Stand der Skill `claude-api`, 2026-06; in der Konfiguration änderbar)."""

    input: float
    output: float
    cache_write_1h: float
    cache_read: float

    def cost(self, usage: dict[str, int]) -> float:
        return round(
            (
                usage.get("input_tokens", 0) * self.input
                + usage.get("output_tokens", 0) * self.output
                + usage.get("cache_creation_input_tokens", 0) * self.cache_write_1h
                + usage.get("cache_read_input_tokens", 0) * self.cache_read
            )
            / 1_000_000,
            4,
        )


def prices(settings: Settings) -> Prices:
    return Prices(
        input=settings.rules_price_input_per_mtok,
        output=settings.rules_price_output_per_mtok,
        cache_write_1h=settings.rules_price_input_per_mtok * 2,
        cache_read=settings.rules_price_input_per_mtok * 0.1,
    )


def _document(data: bytes, title: str) -> dict[str, Any]:
    return {
        "type": "document",
        "title": title,
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.b64encode(data).decode("ascii"),
        },
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }


def build_messages(request: ExtractionRequest) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    if request.general_pdf is not None:
        content.append(_document(request.general_pdf, "general provisions and definitions"))
    content.append(_document(request.chapter_pdf, f"zone chapter {request.chapter_code}"))
    content.append(
        {
            "type": "text",
            "text": user_instruction(
                request.sectors, request.chapter_code, request.general_pages, request.chapter_pages
            ),
        }
    )
    return [{"role": "user", "content": content}]


def _usage(message: Any) -> dict[str, int]:
    usage = getattr(message, "usage", None)
    if usage is None:
        return {}
    return {
        key: int(getattr(usage, key, 0) or 0)
        for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    }


@dataclass
class ClaudeExtractor:
    settings: Settings
    client: anthropic.Anthropic | None = field(default=None)

    def __post_init__(self) -> None:
        if self.client is None:
            key = self.settings.anthropic_api_key
            if key is None:
                raise ExtractionError("not_configured", retryable=False)
            self.client = anthropic.Anthropic(
                api_key=key.get_secret_value(),
                timeout=anthropic.Timeout(self.settings.rules_request_timeout_seconds, connect=15.0),
                max_retries=2,
            )

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        assert self.client is not None
        started = time.perf_counter()
        try:
            with self.client.beta.messages.stream(
                model=self.settings.rules_model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral", "ttl": "1h"},
                    }
                ],
                messages=build_messages(request),  # type: ignore[arg-type]
                thinking={"type": "adaptive"},
                output_config={
                    "effort": self.settings.rules_effort,
                    "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                message = stream.get_final_message()
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise ExtractionError("auth", retryable=False) from exc
        except anthropic.NotFoundError as exc:
            raise ExtractionError("model_not_found", retryable=False) from exc
        except anthropic.RateLimitError as exc:
            raise ExtractionError("rate_limited", retryable=True) from exc
        except anthropic.BadRequestError as exc:
            raise ExtractionError(f"bad_request:{str(exc.message)[:200]}", retryable=False) from exc
        except anthropic.APIStatusError as exc:
            raise ExtractionError(f"http_{exc.status_code}", retryable=exc.status_code >= 500) from exc
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise ExtractionError(f"transport:{type(exc).__name__}", retryable=True) from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = _usage(message)
        request_id = getattr(message, "_request_id", None)
        served_by_fallback = any(getattr(b, "type", None) == "fallback" for b in message.content) or any(
            getattr(i, "type", None) == "fallback_message"
            for i in (getattr(message.usage, "iterations", None) or [])
        )
        log.info(
            "external_call",
            service=SERVICE,
            model=message.model,
            stop_reason=message.stop_reason,
            duration_ms=duration_ms,
            fallback=served_by_fallback,
            **usage,
        )
        if message.stop_reason == "refusal":
            raise ExtractionError("refusal", retryable=False, usage=usage)
        if message.stop_reason == "max_tokens":
            raise ExtractionError("max_tokens", retryable=False, usage=usage)
        text = next(
            (getattr(b, "text", None) for b in message.content if getattr(b, "type", None) == "text"), None
        )
        if text is None:
            raise ExtractionError("no_text", retryable=False, usage=usage)
        try:
            output = json.loads(text)
        except ValueError as exc:
            raise ExtractionError("invalid_json", retryable=False, usage=usage) from exc
        return ExtractionResponse(
            output=output,
            model=str(message.model),
            request_id=request_id,
            stop_reason=message.stop_reason,
            usage=usage,
            served_by_fallback=served_by_fallback,
            duration_ms=duration_ms,
            cost_usd=prices(self.settings).cost(usage),
        )
