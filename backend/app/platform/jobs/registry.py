"""Verzeichnis der Jobarten und periodischen Aufgaben.

Fachmodule melden ihre Jobs in `jobs.py` mit `@job(...)` an; `app.registry` importiert alle.
"""

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.platform.db import get_sessionmaker

DEFAULT = "default"
LONG = "long"
"""Warteschlange für Jobs, die Minuten bis eine Stunde laufen (Auswertung, Lesen, Texterkennung, Importe).
Ein eigener Worker bedient sie, damit Mails, Steckbriefe und Berichte nicht dahinter warten (REFACTORING_PLAN
S5, Befund B-10)."""
QUEUES = (DEFAULT, LONG)


@dataclass(frozen=True)
class JobContext:
    job_id: uuid.UUID
    attempt: int
    project_id: uuid.UUID | None

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = get_sessionmaker()()
        try:
            yield session
        finally:
            session.rollback()
            session.close()


Handler = Callable[[JobContext, dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class JobSpec:
    kind: str
    handler: Handler
    queue: str
    max_attempts: int
    timeout_seconds: int


@dataclass(frozen=True)
class PeriodicSpec:
    name: str
    kind: str
    every: timedelta


_JOBS: dict[str, JobSpec] = {}
_PERIODIC: dict[str, PeriodicSpec] = {}


def job(
    kind: str, *, queue: str = DEFAULT, max_attempts: int = 3, timeout_seconds: int = 60
) -> Callable[[Handler], Handler]:
    """Handler MÜSSEN idempotent sein: Nach einem Absturz wird ein Job erneut ausgeführt (Spez. 7)."""

    if queue not in QUEUES:
        raise ValueError(f"Unbekannte Warteschlange {queue}")

    def register(handler: Handler) -> Handler:
        if kind in _JOBS and _JOBS[kind].handler is not handler:
            raise ValueError(f"Jobart {kind} doppelt registriert")
        _JOBS[kind] = JobSpec(kind, handler, queue, max_attempts, timeout_seconds)
        return handler

    return register


def periodic(name: str, *, kind: str, every: timedelta) -> None:
    _PERIODIC[name] = PeriodicSpec(name, kind, every)


def get_job_spec(kind: str) -> JobSpec:
    try:
        return _JOBS[kind]
    except KeyError:
        raise KeyError(f"Unbekannte Jobart: {kind}") from None


def periodic_specs() -> list[PeriodicSpec]:
    return list(_PERIODIC.values())
