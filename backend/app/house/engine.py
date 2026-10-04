"""Aufrufe des Rechendienstes `engine` (docs/PLAN_HAUSMODELL.md 3.3, E-HM-36).

Die API prüft den Inhalt einer Anfrage vorher mit den Vertragsmodellen und jede Antwort danach (3.4). Lehnt
der Kern eine Anfrage ab (422 `{code, detail}`, z. B. ein Ring mit Rücklauf, E-HM-27), ist das ein Befund
der Dokumente. Nicht erreichbar, Zeitüberschreitung, 5xx oder eine Antwort außerhalb des Vertrags ist ein
Ausfall: `503 engine_unavailable`.
"""

import re
import time
from functools import lru_cache
from typing import Any

import httpx2
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.house.contract import (
    HouseCatalog,
    HouseCompatibility,
    HouseCompatibilityIssue,
    HouseCompatibilityRequest,
    HouseTemplate,
)
from app.platform.logging import get_logger
from app.platform.problems import Problem

log = get_logger("engine")
_ID = re.compile(r"[A-Za-z0-9_$.\-]{1,64}")
"""`Id` des Vertrags; andere Angaben des Kerns gehen nur als Text in `ref_id`."""


class EngineRejected(Exception):
    """Der Kern lehnt die Anfrage ab (422)."""

    def __init__(self, code: str, detail: dict[str, str]) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class _Rejection(BaseModel):
    code: str
    detail: dict[str, str]


class _Health(BaseModel):
    status: str
    domain: str


@lru_cache
def _shared_client() -> httpx2.Client:
    settings = get_settings()
    return httpx2.Client(base_url=settings.engine_url, timeout=settings.engine_timeout_seconds)


def engine_client() -> httpx2.Client:
    """FastAPI-Abhängigkeit, ein Client je Prozess; Tests ersetzen sie durch einen Client mit
    `MockTransport`."""
    return _shared_client()


def _unavailable(reason: str) -> Problem:
    log.warning("engine_unavailable", reason=reason)
    return Problem(503, "engine_unavailable")


def _call(client: httpx2.Client, method: str, path: str, body: Any = None) -> Any:
    started = time.perf_counter()
    try:
        response = client.request(method, path, json=body)
    except httpx2.TimeoutException:
        raise _unavailable("timeout") from None
    except httpx2.TransportError as exc:
        raise _unavailable(f"transport:{type(exc).__name__}") from None
    log.info(
        "engine_call",
        path=path,
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    try:
        data = response.json()
    except ValueError:
        raise _unavailable("invalid_json") from None
    if response.status_code == 422:
        try:
            rejection = _Rejection.model_validate(data)
        except ValidationError:
            raise _unavailable("invalid_rejection") from None
        raise EngineRejected(rejection.code, rejection.detail)
    if response.status_code != 200:
        raise _unavailable(f"http_{response.status_code}")
    return data


def _parse[T: BaseModel](model: type[T], data: Any) -> T:
    try:
        return model.model_validate(data)
    except ValidationError:
        raise _unavailable(f"contract:{model.__name__}") from None


def domain_version(client: httpx2.Client) -> str:
    return _parse(_Health, _call(client, "GET", "/health")).domain


def compatibility(
    client: httpx2.Client, template: HouseTemplate, catalog: HouseCatalog
) -> HouseCompatibility:
    """Prüfung Template ↔ Katalog (P 2.1 Nr. 5). Lehnt der Kern die Dokumente ab, sind sie nicht
    kompatibel; der Code des Kerns wird zum Befund."""
    body = HouseCompatibilityRequest(template=template, catalog=catalog).model_dump(mode="json")
    try:
        return _parse(HouseCompatibility, _call(client, "POST", "/compatibility", body))
    except EngineRejected as exc:
        issue = HouseCompatibilityIssue(
            code=exc.code,
            slot_id=_id(exc.detail.get("slot")),
            element_id=_id(exc.detail.get("element") or exc.detail.get("id")),
            ref_id=", ".join(f"{key}={value}" for key, value in sorted(exc.detail.items())) or None,
        )
        return HouseCompatibility(domain_version=domain_version(client), supported=False, issues=[issue])


def _id(value: str | None) -> str | None:
    return value if value is not None and _ID.fullmatch(value) else None
