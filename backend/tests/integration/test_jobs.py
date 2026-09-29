"""Warteschlange in PostgreSQL: transaktionale Anlage, Wiederholung, Zeitlimit, verwaiste Jobs, Zeitplan,
getrennte Warteschlangen für kurze und lange Jobs."""

import time
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, text

import app.registry  # noqa: F401  alle Jobarten der Anwendung
from app.platform.db import get_engine
from app.platform.jobs import LONG, JobContext, enqueue, job
from app.platform.jobs.registry import get_job_spec
from app.platform.jobs.worker import run_one, schedule_periodic
from app.platform.models import Job, Project

CALLS: list[dict[str, Any]] = []


@job("test_ok")
def _ok(ctx: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    CALLS.append(payload)
    return {"echo": payload.get("n")}


@job("test_boom", max_attempts=2)
def _boom(ctx: JobContext, payload: dict[str, Any]) -> None:
    raise RuntimeError("kaputt")


@job("test_slow", timeout_seconds=1, max_attempts=1)
def _slow(ctx: JobContext, payload: dict[str, Any]) -> None:
    time.sleep(3)


@job("test_long", queue=LONG)
def _long(ctx: JobContext, payload: dict[str, Any]) -> None:
    return None


def _job(db_session: Any, job_id: Any) -> Job:
    db_session.expire_all()
    found = db_session.get(Job, job_id)
    assert found is not None
    return found


def test_enqueue_is_part_of_the_transaction(db_session: Any) -> None:
    enqueue(db_session, "test_ok", {"n": 1})
    db_session.rollback()
    assert db_session.execute(select(Job)).first() is None


def test_idempotency_key_returns_same_job(db_session: Any) -> None:
    first = enqueue(db_session, "test_ok", {"n": 1}, idempotency_key="k1")
    second = enqueue(db_session, "test_ok", {"n": 2}, idempotency_key="k1")
    db_session.commit()
    assert first == second


def test_unknown_kind_is_rejected(db_session: Any) -> None:
    with pytest.raises(KeyError):
        enqueue(db_session, "nope")


def test_success(db_session: Any) -> None:
    CALLS.clear()
    job_id = enqueue(db_session, "test_ok", {"n": 7})
    db_session.commit()
    assert run_one("w1", ["default"]) is True
    done = _job(db_session, job_id)
    assert done.status == "succeeded" and done.result == {"echo": 7} and done.attempts == 1
    assert CALLS == [{"n": 7}]
    assert run_one("w1", ["default"]) is False


def test_retry_with_backoff_then_failed(db_session: Any) -> None:
    job_id = enqueue(db_session, "test_boom")
    db_session.commit()
    run_one("w1", ["default"])
    retried = _job(db_session, job_id)
    assert retried.status == "queued" and retried.attempts == 1
    assert "RuntimeError: kaputt" in (retried.last_error or "")
    assert run_one("w1", ["default"]) is False  # Backoff: noch nicht fällig

    db_session.execute(text("UPDATE job SET run_after = now() WHERE id = :id"), {"id": job_id})
    db_session.commit()
    run_one("w1", ["default"])
    assert _job(db_session, job_id).status == "failed"


def test_timeout(db_session: Any) -> None:
    job_id = enqueue(db_session, "test_slow")
    db_session.commit()
    run_one("w1", ["default"])
    failed = _job(db_session, job_id)
    assert failed.status == "failed" and "JobTimeout" in (failed.last_error or "")


def test_stale_running_job_is_requeued(db_session: Any) -> None:
    from app.platform.jobs import queue

    job_id = enqueue(db_session, "test_ok", {"n": 1})
    db_session.commit()
    with get_engine().begin() as conn:
        assert queue.claim(conn, "crashed-worker", ["default"]) is not None
        conn.execute(
            text("UPDATE job SET locked_at = now() - interval '10 minutes' WHERE id = :id"), {"id": job_id}
        )
        assert queue.requeue_stale(conn) == 1
    assert _job(db_session, job_id).status == "queued"
    assert run_one("w2", ["default"]) is True
    assert _job(db_session, job_id).status == "succeeded"


def test_periodic_jobs_are_enqueued_once_per_slot(db_session: Any) -> None:
    created = schedule_periodic()
    assert created >= 2  # retention_cleanup, housekeeping
    assert schedule_periodic() == 0
    kinds = set(db_session.execute(select(Job.kind)).scalars())
    assert {"retention_cleanup", "housekeeping"} <= kinds


def test_retention_deletes_only_inactive_draft_projects(db_session: Any) -> None:
    old = Project(access_token_hash=b"old")
    recent = Project(access_token_hash=b"new")
    db_session.add_all([old, recent])
    db_session.commit()
    db_session.execute(
        text("UPDATE project SET last_activity_at = now() - make_interval(days => 91) WHERE id = :id"),
        {"id": old.id},
    )
    enqueue(db_session, "retention_cleanup")
    db_session.commit()
    run_one("w1", ["default"])
    db_session.expire_all()
    remaining = set(db_session.execute(select(Project.id)).scalars())
    assert remaining == {recent.id}


def test_mail_job_sends_via_adapter(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.integrations import smtp
    from app.platform.mail import queue_mail

    sent: list[dict[str, Any]] = []

    def fake_send(settings: Any, **kwargs: Any) -> str:
        sent.append(kwargs)
        return "<id@test>"

    monkeypatch.setattr(smtp, "send", fake_send)
    job_id = queue_mail(
        db_session, to="ops@buero.test", template="platform_test", locale="de", params={"env": "test"}
    )
    db_session.commit()
    run_one("w1", ["default"])
    assert _job(db_session, job_id).status == "succeeded"
    assert sent[0]["subject"] == "Emprise – Testmail"
    assert sent[0]["message_id_key"] == f"job-{job_id}"


def test_job_status_api_access(client: Any, login_as: Any, db_session: Any, app: Any) -> None:
    from fastapi.testclient import TestClient

    project_id = uuid.UUID(client.post("/api/v1/projects").json()["id"])
    own = enqueue(db_session, "test_ok", project_id=project_id)
    other = enqueue(db_session, "test_ok")
    db_session.commit()

    assert client.get(f"/api/v1/jobs/{own}").json()["status"] == "queued"
    assert client.get(f"/api/v1/jobs/{other}").status_code == 404
    with TestClient(app) as stranger:
        assert stranger.get(f"/api/v1/jobs/{own}").status_code == 404
    login_as("ops")
    assert client.get(f"/api/v1/jobs/{other}").status_code == 200


def test_jobs_health_alarms_on_old_waiting_job(client: Any, db_session: Any) -> None:
    assert client.get("/api/health/jobs").status_code == 200
    job_id = enqueue(db_session, "test_ok")
    db_session.execute(
        text("UPDATE job SET run_after = now() - :age WHERE id = :id"),
        {"age": timedelta(minutes=16), "id": job_id},
    )
    db_session.commit()
    response = client.get("/api/health/jobs")
    assert response.status_code == 503
    assert response.json()["queues"]["default"]["oldest_waiting_seconds"] > 900


def test_long_jobs_wait_in_their_own_queue(client: Any, db_session: Any) -> None:
    """Ein Worker für `default` nimmt keinen langen Job; eine Auswertung hält so keine Mail auf (B-10)."""
    for kind in (
        "rules_extract",
        "rules_document_read",
        "rules_document_ocr",
        "plu_import",
        "cadastre_import",
    ):
        assert get_job_spec(kind).queue == LONG
    assert get_job_spec("mail_send").queue == "default"

    job_id = enqueue(db_session, "test_long")
    db_session.execute(
        text("UPDATE job SET run_after = now() - :age WHERE id = :id"),
        {"age": timedelta(minutes=30), "id": job_id},
    )
    db_session.commit()
    # 30 Minuten sind in `long` normal (hinter einer Auswertung), in `default` wären sie ein Alarm
    health = client.get("/api/health/jobs")
    assert health.status_code == 200 and health.json()["queues"]["long"]["oldest_waiting_seconds"] > 1700
    assert run_one("w-default", ["default"]) is False
    assert _job(db_session, job_id).status == "queued"
    assert run_one("w-long", [LONG]) is True
    assert _job(db_session, job_id).status == "succeeded"
