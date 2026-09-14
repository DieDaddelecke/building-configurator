"""Übersetzungsschlüssel für Texte der API (Spez. 13). Französisch führt (D7)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from starlette.requests import Request

Locale = Literal["fr", "de"]
SUPPORTED: tuple[Locale, ...] = ("fr", "de")
DEFAULT_LOCALE: Locale = "fr"

_DIR = Path(__file__).parent / "locales"


@lru_cache
def _catalog(locale: Locale) -> dict[str, str]:
    data: dict[str, str] = json.loads((_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    return data


def parse_accept_language(header: str | None) -> Locale:
    """Wählt die bestunterstützte Sprache aus `Accept-Language`, sonst Französisch."""
    if not header:
        return DEFAULT_LOCALE
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        pieces = part.strip().split(";")
        tag = pieces[0].strip().lower()
        quality = 1.0
        for param in pieces[1:]:
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        candidates.append((-quality, index, tag))
    for _, _, tag in sorted(candidates):
        primary = tag.split("-")[0]
        if primary in SUPPORTED:
            return primary
    return DEFAULT_LOCALE


def request_locale(request: Request) -> Locale:
    return parse_accept_language(request.headers.get("accept-language"))


def translate(key: str, locale: Locale, **params: object) -> str:
    text = _catalog(locale).get(key) or _catalog(DEFAULT_LOCALE).get(key) or key
    return text.format(**params) if params else text
