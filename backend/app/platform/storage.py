"""Private Dateien im Verzeichnis `EMPRISE_FILES_DIR` (REFACTORING_PLAN S6).

Ein Host, eine Anwendung: Statt eines S3-Dienstes liegen die Dateien in einem Verzeichnis, das API, Worker und
Migrationsjob einbinden. Die Schlüssel bleiben dieselben wie im früheren Bucket (`regulations/<sha256>.pdf`,
`envelope-sheets/…`) und sind relative Pfade darunter. Schreiben ist atomar (temporäre Datei, dann
`os.replace`); ein Schlüssel, der aus dem Verzeichnis führt, wird abgewiesen. Von außen gibt es nur den Weg
über die API (Spez. 10.1).
"""

import os
import tempfile
from pathlib import Path, PurePosixPath

from app.config import get_settings


class InvalidKey(ValueError):
    """Schlüssel leer, absolut oder mit `..`: Er zeigte aus dem Dateiverzeichnis hinaus."""


def root() -> Path:
    return Path(get_settings().files_dir)


def path_for(key: str) -> Path:
    parts = PurePosixPath(key).parts
    if not parts or key.startswith("/") or "\\" in key or any(p in ("", ".", "..") for p in parts):
        raise InvalidKey(key)
    return root().joinpath(*parts)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """`content_type` bleibt für die Aufrufer gleich; den Typ kennt die Fachtabelle, nicht die Datei."""
    target = path_for(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def get_bytes(key: str) -> bytes:
    """Hebt `FileNotFoundError`, wenn es die Datei nicht gibt."""
    return path_for(key).read_bytes()


def delete(key: str) -> None:
    """Wie beim Bucket: Eine fehlende Datei ist kein Fehler."""
    path_for(key).unlink(missing_ok=True)


def roundtrip_check(key: str) -> bool:
    """Schreiben, Lesen, Löschen einer Probe (Betriebsstatus, `storage-init`)."""
    probe = b"emprise-storage-check"
    put_bytes(key, probe, "text/plain")
    try:
        return get_bytes(key) == probe
    finally:
        delete(key)
