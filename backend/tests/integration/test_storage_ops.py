"""Betriebsstatus mit Probe des Dateiverzeichnisses und Testmail."""

from typing import Any

from sqlalchemy import select

from app.platform.models import Job


def test_ops_status_and_test_mail(client: Any, login_as: Any, db_session: Any) -> None:
    login_as("ops", email="ops@buero.test")
    status = client.get("/api/v1/admin/ops/status")
    assert status.status_code == 200
    assert status.json()["storage_ok"] is True

    queued = client.post("/api/v1/admin/ops/test-mail", headers={"Accept-Language": "de"})
    assert queued.status_code == 202
    job = db_session.execute(select(Job)).scalar_one()
    assert job.kind == "mail_send"
    assert job.payload["to"] == "ops@buero.test" and job.payload["locale"] == "de"
