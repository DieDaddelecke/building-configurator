"""Gemeinsamer HTTP-Zugriff auf externe Dienste (Spez. 9, Plan 4.1 Kriterium 3).

Zeitlimit, begrenzte Wiederholung bei Netzfehlern und 5xx, eigene Kennung. Adressen und andere
Eingaben der Kunden stehen nie im Log; geloggt werden Dienst, Status und Dauer.
"""

import time
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import httpx2

from app.config import Settings, get_settings
from app.platform.logging import get_logger

log = get_logger("integrations")
RETRY_PAUSE_SECONDS = 0.5


class ExternalServiceError(Exception):
    """Ein externer Dienst ist nicht erreichbar oder antwortet unbrauchbar."""

    def __init__(self, service: str, reason: str) -> None:
        super().__init__(f"{service}: {reason}")
        self.service = service
        self.reason = reason


@lru_cache
def shared_client() -> httpx2.Client:
    """Ein Client je Prozess für Anfragen aus der API (Verbindungen werden wiederverwendet).
    Tests ersetzen die FastAPI-Abhängigkeit `shared_client`."""
    return new_client(get_settings())


def new_client(settings: Settings, transport: httpx2.BaseTransport | None = None) -> httpx2.Client:
    return httpx2.Client(
        timeout=settings.external_timeout_seconds,
        headers={"User-Agent": settings.http_user_agent},
        follow_redirects=True,
        transport=transport,
    )


def get(
    client: httpx2.Client,
    service: str,
    url: str,
    *,
    params: Mapping[str, str | int | float] | None = None,
    headers: Mapping[str, str] | None = None,
    attempts: int = 2,
    timeout: float | None = None,
) -> httpx2.Response:
    """GET mit Wiederholung bei Zeitüberschreitung, Verbindungsfehler und 5xx. 4xx wird nicht wiederholt."""
    return _request(
        client, service, "GET", url, params=params, headers=headers, attempts=attempts, timeout=timeout
    )


def post_json(
    client: httpx2.Client,
    service: str,
    url: str,
    body: Any,
    *,
    attempts: int = 2,
    timeout: float | None = None,
) -> Any:
    """POST mit JSON-Körper (z. B. Geometrien, die für eine URL zu lang sind); Antwort als JSON."""
    response = _request(client, service, "POST", url, json=body, attempts=attempts, timeout=timeout)
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError(service, "invalid_json") from exc


def _request(
    client: httpx2.Client,
    service: str,
    method: str,
    url: str,
    *,
    params: Mapping[str, str | int | float] | None = None,
    headers: Mapping[str, str] | None = None,
    json: Any = None,
    attempts: int = 2,
    timeout: float | None = None,
) -> httpx2.Response:
    last_reason = "no_attempt"
    extra: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            response = client.request(method, url, params=params, headers=headers, json=json, **extra)
        except httpx2.TimeoutException:
            last_reason = "timeout"
        except httpx2.TransportError as exc:
            last_reason = f"transport:{type(exc).__name__}"
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            if response.status_code < 500:
                log.info(
                    "external_call", service=service, status=response.status_code, duration_ms=duration_ms
                )
                if response.status_code >= 400:
                    raise ExternalServiceError(service, f"http_{response.status_code}")
                return response
            last_reason = f"http_{response.status_code}"
        log.warning("external_call_failed", service=service, reason=last_reason, attempt=attempt)
        if attempt < attempts:
            time.sleep(RETRY_PAUSE_SECONDS * attempt)
    raise ExternalServiceError(service, last_reason)


def get_json(client: httpx2.Client, service: str, url: str, **kwargs: Any) -> Any:
    response = get(client, service, url, **kwargs)
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError(service, "invalid_json") from exc
