"""Privater, S3-kompatibler Objektspeicher.

Zugriff von außen nur über kurzlebige signierte URLs (Spez. 10.1).
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def _client(endpoint_url: str | None) -> "S3Client":
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key.get_secret_value() if settings.s3_access_key else None,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


@lru_cache
def client() -> "S3Client":
    return _client(get_settings().s3_endpoint_url)


@lru_cache
def public_client() -> "S3Client":
    settings = get_settings()
    return _client(settings.s3_public_endpoint_url or settings.s3_endpoint_url)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)


def get_bytes(key: str) -> bytes:
    response = client().get_object(Bucket=get_settings().s3_bucket, Key=key)
    body: bytes = response["Body"].read()
    return body


def delete(key: str) -> None:
    client().delete_object(Bucket=get_settings().s3_bucket, Key=key)


def presigned_get_url(key: str, expires_seconds: int = 300) -> str:
    return public_client().generate_presigned_url(
        "get_object", Params={"Bucket": get_settings().s3_bucket, "Key": key}, ExpiresIn=expires_seconds
    )


def roundtrip_check(key: str) -> bool:
    """Schreiben, Lesen, Löschen einer Probe (Betriebsprüfung, Proof of Concept)."""
    probe = b"emprise-storage-check"
    put_bytes(key, probe, "text/plain")
    try:
        return get_bytes(key) == probe
    finally:
        delete(key)
