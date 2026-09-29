"""Dateien im Verzeichnis (REFACTORING_PLAN S6): Schlüssel wie im früheren Bucket, atomar, nicht hinaus."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings
from app.platform import storage


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("EMPRISE_FILES_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_roundtrip_keeps_the_key_as_relative_path(files: Path) -> None:
    storage.put_bytes("regulations/abc.pdf", b"%PDF-1", "application/pdf")
    assert (files / "regulations" / "abc.pdf").read_bytes() == b"%PDF-1"
    assert storage.get_bytes("regulations/abc.pdf") == b"%PDF-1"
    storage.put_bytes("regulations/abc.pdf", b"%PDF-2")
    assert storage.get_bytes("regulations/abc.pdf") == b"%PDF-2"
    # Keine Reste der atomaren Schreibweise
    assert [p.name for p in (files / "regulations").iterdir()] == ["abc.pdf"]
    storage.delete("regulations/abc.pdf")
    storage.delete("regulations/abc.pdf")  # fehlt schon: kein Fehler, wie beim Bucket
    with pytest.raises(FileNotFoundError):
        storage.get_bytes("regulations/abc.pdf")
    assert storage.roundtrip_check("ops-check/probe") is True


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../x", "a/../../b", "a/..", "a\\b", "."])
def test_keys_outside_the_directory_are_rejected(files: Path, key: str) -> None:
    with pytest.raises(storage.InvalidKey):
        storage.put_bytes(key, b"x")
    with pytest.raises(storage.InvalidKey):
        storage.get_bytes(key)


def test_failed_write_leaves_no_file(files: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(src: str, dst: str) -> None:
        raise OSError("Platte voll")

    monkeypatch.setattr(storage.os, "replace", broken)
    with pytest.raises(OSError):
        storage.put_bytes("envelope-sheets/a.pdf", b"x")
    assert list((files / "envelope-sheets").iterdir()) == []
