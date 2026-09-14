"""Worker-Prozess: periodische Aufgaben einplanen, verwaiste Jobs zurückstellen, Jobs ausführen."""

import os
import signal
import socket
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import FrameType

import sentry_sdk
import structlog
from sqlalchemy import text

from app.config import Settings
from app.platform.db import get_engine, get_sessionmaker
from app.platform.jobs import queue
from app.platform.jobs.registry import JobContext, get_job_spec, periodic_specs
from app.platform.logging import get_logger

log = get_logger("worker")
MAINTENANCE_INTERVAL_SECONDS = 30


class JobTimeout(Exception):
    pass


@contextmanager
def time_limit(seconds: int) -> Iterator[None]:
    """Zeitlimit über SIGALRM (Linux-Container). Ohne SIGALRM greift nur `requeue_stale`."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _raise(signum: int, frame: FrameType | None) -> None:
        raise JobTimeout(f"timeout after {seconds}s")

    previous = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def schedule_periodic() -> int:
    """Legt fällige periodische Jobs genau einmal an, auch bei mehreren Workern."""
    specs = {spec.name: spec for spec in periodic_specs()}
    if not specs:
        return 0
    created = 0
    with get_sessionmaker()() as session:
        for name in specs:
            session.execute(
                text(
                    "INSERT INTO periodic_schedule (name, next_run_at) VALUES (:name, now()) "
                    "ON CONFLICT (name) DO NOTHING"
                ),
                {"name": name},
            )
        due = session.execute(
            text(
                "SELECT name, next_run_at, now() AS db_now FROM periodic_schedule "
                "WHERE next_run_at <= now() FOR UPDATE SKIP LOCKED"
            )
        ).all()
        for row in due:
            spec = specs.get(row.name)
            if spec is None:
                continue
            queue.enqueue(
                session,
                spec.kind,
                {},
                idempotency_key=f"periodic:{spec.name}:{row.next_run_at.isoformat()}",
                created_by="system:scheduler",
            )
            next_run: datetime = row.next_run_at + spec.every
            if next_run <= row.db_now:
                next_run = row.db_now + spec.every
            session.execute(
                text(
                    "UPDATE periodic_schedule SET next_run_at = :next, last_enqueued_at = now() "
                    "WHERE name = :name"
                ),
                {"next": next_run, "name": spec.name},
            )
            created += 1
        session.commit()
    return created


def run_one(worker_name: str, queues: list[str]) -> bool:
    """Holt einen fälligen Job und führt ihn aus. Liefert False, wenn keiner wartete."""
    engine = get_engine()
    with engine.begin() as conn:
        claimed = queue.claim(conn, worker_name, queues)
    if claimed is None:
        return False

    structlog.contextvars.bind_contextvars(job_id=str(claimed.id), job_kind=claimed.kind)
    started = time.perf_counter()
    try:
        spec = get_job_spec(claimed.kind)
        context = JobContext(job_id=claimed.id, attempt=claimed.attempts, project_id=claimed.project_id)
        with time_limit(claimed.timeout_seconds):
            result = spec.handler(context, claimed.payload)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        with engine.begin() as conn:
            status = queue.fail(conn, claimed, worker_name, error)
        log.warning(
            "job_failed",
            attempt=claimed.attempts,
            status=status,
            error_type=type(exc).__name__,
            trace=traceback.format_exc(limit=5),
        )
        if status == "failed":
            sentry_sdk.capture_exception(exc)
    else:
        with engine.begin() as conn:
            queue.complete(conn, claimed.id, worker_name, result)
        log.info(
            "job_succeeded",
            attempt=claimed.attempts,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
    finally:
        structlog.contextvars.unbind_contextvars("job_id", "job_kind")
    return True


def maintenance() -> None:
    created = schedule_periodic()
    with get_engine().begin() as conn:
        stale = queue.requeue_stale(conn)
    if created or stale:
        log.info("worker_maintenance", periodic_enqueued=created, stale_requeued=stale)


def run_worker(settings: Settings) -> None:
    worker_name = f"{socket.gethostname()}:{os.getpid()}"
    stopping = False

    def _stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True
        log.info("worker_stopping", signal=signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker_started", worker=worker_name, queues=settings.worker_queues)

    next_maintenance = datetime.min
    while not stopping:
        try:
            if datetime.now() >= next_maintenance:
                maintenance()
                next_maintenance = datetime.now() + timedelta(seconds=MAINTENANCE_INTERVAL_SECONDS)
            if not run_one(worker_name, settings.worker_queues):
                time.sleep(settings.worker_poll_seconds)
        except Exception as exc:  # Datenbank kurz nicht erreichbar: weiterlaufen
            log.exception("worker_loop_error")
            sentry_sdk.capture_exception(exc)
            time.sleep(5)
    log.info("worker_stopped", worker=worker_name)
