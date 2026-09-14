"""Objektspeicher und Betriebsstatus. Braucht einen S3-Dienst (lokal MinIO): TEST_S3=1."""

import os
from typing import Any

import pytest
from sqlalchemy import select

from app.platform import storage
from app.platform.models import Job

requires_s3 = pytest.mark.skipif(os.environ.get("TEST_S3") != "1", reason="TEST_S3=1 fehlt")


@requires_s3
def test_storage_roundtrip_and_presigned_url() -> None:
    assert storage.roundtrip_check("test/roundtrip.txt") is True
    storage.put_bytes("test/signed.txt", b"x", "text/plain")
    try:
        url = storage.presigned_get_url("test/signed.txt", expires_seconds=60)
        assert "X-Amz-Signature=" in url
    finally:
        storage.delete("test/signed.txt")


@requires_s3
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
