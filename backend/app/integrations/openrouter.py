"""OpenRouter: Regeln aus Seitenauszügen des règlement écrit (Spez. 5.2.3 Schritt 3, 9; Plan 3.4).

Anbindung über die OpenAI-kompatible Chat-Completions-API von OpenRouter (`openai`-SDK mit eigener
`base_url`). Modell frei wählbar über die Konfiguration (Standard `anthropic/claude-opus-5`), strukturierte
Ausgabe über einen erzwungenen Funktionsaufruf (breiter unterstützt als natives `response_format` über
verschiedene Anbieter hinweg), Denkaufwand über den herstellerübergreifenden `reasoning`-Parameter.
Gesendet werden nur öffentliche Planunterlagen, keine Kundendaten (L8).

OpenRouter ist damit ein weiterer Drittanbieter im Datenweg neben der bisherigen Ausnahme der Claude API
(D3/D4, E-D19); die Abwägung gilt unverändert nur für öffentliche Planunterlagen.

Kein explizites Zwischenspeichern des Systemprompts mehr (anbieterabhängig, nicht über alle Modelle
zusichbar): jeder Aufruf sendet den vollständigen Kontext neu.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import openai

from app.config import Settings
from app.platform.logging import get_logger
from app.rules.domain.extraction import (
    OUTPUT_SCHEMA,
    VERIFICATION_SCHEMA,
    DocumentKind,
    system_prompt,
    user_instruction,
    verification_instruction,
)

SERVICE = "openrouter"
MAX_OUTPUT_TOKENS = 64000
EXTRACTION_TOOL = "submit_extraction"
VERIFICATION_TOOL = "submit_verification"

log = get_logger("integrations.openrouter")


@dataclass(frozen=True)
class ExtractionRequest:
    chapter_code: str
    sectors: list[str]
    chapter_pdf: bytes
    chapter_pages: list[int]
    general_pdf: bytes | None
    general_pages: list[int]
    claims: list[dict[str, Any]] | None = None
    """Gegenprüfung: nummerierte Regeln ohne Werte (Sektor, Art, Baukörper, Seite, Zitat).
    None: Auswertung."""
    document_kind: DocumentKind = "plu"
    """`supplement`: Zusatzdokument mit eigenem Prompt, Sektoren sind Lots (AN3)."""


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
    """US-Dollar je Million Token (in der Konfiguration änderbar). Ohne zugesichertes Zwischenspeichern
    zählt nur `input`/`output`; die Cache-Felder bleiben für die Kostenformel bestehen, tragen aber nur bei,
    wenn ein Anbieter über OpenRouter dennoch zwischengespeicherte Token meldet."""

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


def _effort(effort: str) -> str:
    """OpenRouter kennt nur `low`/`medium`/`high` als herstellerübergreifenden Denkaufwand."""
    return "high" if effort in ("xhigh", "max") else effort


def _document(data: bytes, filename: str) -> dict[str, Any]:
    return {
        "type": "file",
        "file": {
            "filename": filename,
            "file_data": f"data:application/pdf;base64,{base64.b64encode(data).decode('ascii')}",
        },
    }


def build_messages(request: ExtractionRequest) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    kind = request.document_kind
    if request.general_pdf is not None:
        content.append(_document(request.general_pdf, "general.pdf"))
    filename = "supplement.pdf" if kind == "supplement" else f"chapter-{request.chapter_code}.pdf"
    content.append(_document(request.chapter_pdf, filename))
    if request.claims is None:
        instruction = user_instruction(
            request.sectors, request.chapter_code, request.general_pages, request.chapter_pages, kind
        )
    else:
        instruction = verification_instruction(
            request.claims, request.chapter_code, request.general_pages, request.chapter_pages, kind
        )
    content.append({"type": "text", "text": instruction})
    return [{"role": "user", "content": content}]


def _tool(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Return the result in exactly this shape.",
            "parameters": schema,
        },
    }


def _usage(message: Any) -> dict[str, int]:
    """`prompt_tokens` zählt zwischengespeicherte Token mit (anders als bei Anthropic); `input_tokens` bleibt
    hier der nicht zwischengespeicherte Anteil, damit die Kostenformel nicht doppelt zählt."""
    usage = getattr(message, "usage", None)
    if usage is None:
        return {}
    details = getattr(usage, "prompt_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    return {
        "input_tokens": max(prompt - cached, 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": cached,
    }


@dataclass
class OpenRouterExtractor:
    settings: Settings
    client: openai.OpenAI | None = field(default=None)

    def __post_init__(self) -> None:
        if self.client is None:
            key = self.settings.openrouter_api_key
            if key is None:
                raise ExtractionError("not_configured", retryable=False)
            self.client = openai.OpenAI(
                base_url=self.settings.openrouter_base_url,
                api_key=key.get_secret_value(),
                timeout=self.settings.rules_request_timeout_seconds,
                # Wiederholung über den Job: erfolgreiche Teile werden dort wiederverwendet, und ein Aufruf
                # bleibt kürzer als das Zeitlimit des Jobs
                max_retries=0,
                default_headers={"HTTP-Referer": "https://emprise.local", "X-Title": "Emprise"},
            )

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        assert self.client is not None
        started = time.perf_counter()
        claims = request.claims
        schema = OUTPUT_SCHEMA if claims is None else VERIFICATION_SCHEMA
        tool_name = EXTRACTION_TOOL if claims is None else VERIFICATION_TOOL
        try:
            message = self.client.chat.completions.create(
                model=self.settings.rules_model,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt(request.document_kind)},
                    *build_messages(request),
                ],
                tools=[_tool(schema, tool_name)],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                extra_body={"reasoning": {"effort": _effort(self.settings.rules_effort)}},
            )  # type: ignore[call-overload]
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise ExtractionError("auth", retryable=False) from exc
        except openai.NotFoundError as exc:
            raise ExtractionError("model_not_found", retryable=False) from exc
        except openai.RateLimitError as exc:
            raise ExtractionError("rate_limited", retryable=True) from exc
        except openai.BadRequestError as exc:
            raise ExtractionError(f"bad_request:{str(exc)[:200]}", retryable=False) from exc
        except openai.APIStatusError as exc:
            status = exc.status_code
            raise ExtractionError(f"http_{status}", retryable=status >= 500) from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise ExtractionError(f"transport:{type(exc).__name__}", retryable=True) from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = _usage(message)
        choice = message.choices[0]
        msg = choice.message
        request_id = getattr(message, "id", None)
        model = str(message.model)
        served_by_fallback = model != self.settings.rules_model
        log.info(
            "external_call",
            service=SERVICE,
            model=model,
            stop_reason=choice.finish_reason,
            duration_ms=duration_ms,
            fallback=served_by_fallback,
            **usage,
        )
        if getattr(msg, "refusal", None):
            raise ExtractionError("refusal", retryable=False, usage=usage)
        if choice.finish_reason == "length":
            raise ExtractionError("max_tokens", retryable=False, usage=usage)
        tool_calls = msg.tool_calls or []
        call = next((c for c in tool_calls if c.function.name == tool_name), None)
        if call is None:
            raise ExtractionError("no_text", retryable=False, usage=usage)
        try:
            output = json.loads(call.function.arguments)
        except ValueError as exc:
            raise ExtractionError("invalid_json", retryable=False, usage=usage) from exc
        return ExtractionResponse(
            output=output,
            model=model,
            request_id=request_id,
            stop_reason=choice.finish_reason,
            usage=usage,
            served_by_fallback=served_by_fallback,
            duration_ms=duration_ms,
            cost_usd=prices(self.settings).cost(usage),
        )
