"""Hochgeladene Dateien lesen, ohne eine zu große Datei erst vollständig anzunehmen."""

from fastapi import UploadFile

from app.platform.problems import Problem

UPLOAD_CHUNK_BYTES = 1024 * 1024


async def read_limited(file: UploadFile, limit: int) -> bytes:
    """Datei stückweise lesen und bei Überschreiten der Grenze abbrechen, nicht erst danach."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise Problem(413, "upload_too_large")
        chunks.append(chunk)
    return b"".join(chunks)
