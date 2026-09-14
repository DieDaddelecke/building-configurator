"""Zufällige Zugangstoken; in der Datenbank steht nur der SHA-256-Hash."""

import hashlib
import hmac
import secrets

STAFF_COOKIE = "emprise_staff"
PROJECT_COOKIE = "emprise_project"
CSRF_COOKIE = "emprise_csrf"
CSRF_HEADER = "x-csrf-token"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii", errors="ignore")).digest()


def keyed_digest(secret: str, value: str) -> str:
    """HMAC für Schlüssel ohne Klartext personenbezogener Werte (z. B. IP im Rate-Limit)."""
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]
