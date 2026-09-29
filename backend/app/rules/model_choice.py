"""KI-Modell der Regelauswertung wählen (docs/PLAN_AN2_PLU.md 8, ANNAHMEN PU11).

Eine Einstellung für Konfigurator und Analyse (`app_setting`, VA09). Ohne Eintrag gelten Modell und Preise
der Umgebung (Vorgabe). Wählbar
sind nur Modelle aus der öffentlichen Liste von OpenRouter, die ein Werkzeug erzwingen können; die Preise
kommen aus derselben Liste, damit Kostenzählung und Monatsbudget stimmen. Wer kein PDF
liest, bekommt die Textschicht mit Seitenmarken (PU12). Jede Auswertung liest die Einstellung beim Start
einmal (`effective_settings`) und mischt so keine Modelle.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import httpx2
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations import http
from app.platform import audit
from app.platform.db import utcnow
from app.platform.logging import get_logger
from app.platform.models import AppSetting

log = get_logger("rules_model")

SETTING_KEY = "rules_model"
SERVICE = "openrouter_models"
LIST_TTL_SECONDS = 3600.0
MODEL_ID_MAX = 60
"""Länge von `rule_extraction_run.model`; längere Kennungen ließen sich nicht protokollieren."""
PER_MTOK = 1_000_000


class ModelNotAvailable(ValueError):
    """Die Kennung steht nicht (mehr) in der Liste der wählbaren Modelle."""


@dataclass(frozen=True)
class ModelOption:
    id: str
    name: str
    price_input_per_mtok: float
    price_output_per_mtok: float
    price_cache_read_per_mtok: float | None
    price_cache_write_per_mtok: float | None
    context_length: int | None
    reads_pdf: bool
    """Eingabeart `file`: bekommt die Seitenauszüge als PDF, sonst ihre Textschicht (PU12)."""


@dataclass(frozen=True)
class CurrentModel:
    model: str
    source: Literal["setting", "default"]
    default_model: str
    price_input_per_mtok: float
    price_output_per_mtok: float
    updated_at: datetime | None
    input: Literal["pdf", "text"]
    updated_by_name: str | None = None


def _price(pricing: dict[str, Any], key: str) -> float | None:
    """Preis je Token (Zeichenkette) → je Million Token; negativ heißt bei OpenRouter „veränderlich“."""
    raw = pricing.get(key)
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return round(value * PER_MTOK, 6) if value >= 0 else None


def parse_models(payload: Any) -> list[ModelOption]:
    """Wählbare Modelle aus `GET /models`: Texteingabe, erzwungenes Werkzeug, fester Name und fester Preis."""
    items = payload.get("data") if isinstance(payload, dict) else None
    options: list[ModelOption] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "")
        # Varianten (`:batch`, `:free`) und gleitende Namen (`~…-latest`) wechseln Abrechnung oder Modell
        if not model_id or ":" in model_id or model_id.startswith("~") or len(model_id) > MODEL_ID_MAX:
            continue
        architecture = item.get("architecture") or {}
        parameters = item.get("supported_parameters") or []
        modalities = architecture.get("input_modalities") or []
        if "text" not in modalities:
            continue
        if "tools" not in parameters or "tool_choice" not in parameters:
            continue
        pricing = item.get("pricing") or {}
        price_input, price_output = _price(pricing, "prompt"), _price(pricing, "completion")
        if price_input is None or price_output is None:
            continue
        context = item.get("context_length")
        options.append(
            ModelOption(
                id=model_id,
                name=str(item.get("name") or model_id)[:120],
                price_input_per_mtok=price_input,
                price_output_per_mtok=price_output,
                price_cache_read_per_mtok=_price(pricing, "input_cache_read"),
                price_cache_write_per_mtok=_price(pricing, "input_cache_write"),
                context_length=int(context) if isinstance(context, int | float) else None,
                reads_pdf="file" in modalities,
            )
        )
    return sorted(options, key=lambda o: (o.id.split("/", 1)[0], o.name.lower(), o.id))


_cache: tuple[float, list[ModelOption]] | None = None
_lock = threading.Lock()


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def available_models(
    client: httpx2.Client, settings: Settings, now: Callable[[], float] = time.monotonic
) -> list[ModelOption]:
    """Liste von OpenRouter ohne Schlüssel, eine Stunde vorgehalten. Hebt `ExternalServiceError`."""
    global _cache
    with _lock:
        if _cache is not None and now() - _cache[0] < LIST_TTL_SECONDS:
            return _cache[1]
    payload = http.get_json(client, SERVICE, f"{settings.openrouter_base_url}/models")
    options = parse_models(payload)
    if not options:
        raise http.ExternalServiceError(SERVICE, "no_usable_model")
    with _lock:
        _cache = (now(), options)
    return options


def effective_settings(session: Session, settings: Settings) -> Settings:
    """Einstellungen mit dem gewählten Modell und seinen Preisen; ohne Wahl die der Umgebung."""
    row = session.get(AppSetting, SETTING_KEY)
    if row is None:
        return settings
    value = row.value or {}
    try:
        return settings.model_copy(
            update={
                "rules_model": str(value["model"]),
                "rules_price_input_per_mtok": float(value["price_input_per_mtok"]),
                "rules_price_output_per_mtok": float(value["price_output_per_mtok"]),
                "rules_price_cache_read_per_mtok": value.get("price_cache_read_per_mtok"),
                "rules_price_cache_write_per_mtok": value.get("price_cache_write_per_mtok"),
                "rules_input": "text" if value.get("input") == "text" else "pdf",
            }
        )
    except (KeyError, TypeError, ValueError):
        log.error("rules_model_setting_invalid", value=value)
        return settings


def current(session: Session, settings: Settings) -> CurrentModel:
    row = session.get(AppSetting, SETTING_KEY)
    effective = effective_settings(session, settings)
    chosen = row is not None and effective is not settings
    return CurrentModel(
        model=effective.rules_model,
        source="setting" if chosen else "default",
        default_model=settings.rules_model,
        price_input_per_mtok=effective.rules_price_input_per_mtok,
        price_output_per_mtok=effective.rules_price_output_per_mtok,
        updated_at=row.updated_at if chosen and row is not None else None,
        input=effective.rules_input,
        updated_by_name=row.updated_by_name if chosen and row is not None else None,
    )


def choose(
    session: Session,
    settings: Settings,
    options: list[ModelOption],
    model_id: str,
    actor_id: str,
    actor_name: str | None = None,
) -> None:
    """Modell für alle künftigen Auswertungen einstellen. Die Vorgabe der Umgebung löscht den Eintrag."""
    before = effective_settings(session, settings).rules_model
    row = session.get(AppSetting, SETTING_KEY)
    if model_id == settings.rules_model:
        if row is not None:
            session.delete(row)
    else:
        option = next((o for o in options if o.id == model_id), None)
        if option is None:
            raise ModelNotAvailable(model_id)
        value = {
            "model": option.id,
            "price_input_per_mtok": option.price_input_per_mtok,
            "price_output_per_mtok": option.price_output_per_mtok,
            "price_cache_read_per_mtok": option.price_cache_read_per_mtok,
            "price_cache_write_per_mtok": option.price_cache_write_per_mtok,
            "input": "pdf" if option.reads_pdf else "text",
        }
        if row is None:
            session.add(
                AppSetting(key=SETTING_KEY, value=value, updated_by=actor_id, updated_by_name=actor_name)
            )
        else:
            row.value, row.updated_at, row.updated_by = value, utcnow(), actor_id
            row.updated_by_name = actor_name
    audit.record(
        session,
        actor_type="staff",
        actor_id=actor_id,
        action="rules_model_changed",
        entity_type="app_setting",
        entity_id=SETTING_KEY,
        before={"model": before},
        after={"model": model_id},
    )
    session.commit()
