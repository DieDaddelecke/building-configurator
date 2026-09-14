"""Rate-Limits in PostgreSQL mit festen Zeitfenstern (Spez. 10.1, Plan 6.7). Kein Redis.

Die Zählung läuft in einer eigenen Transaktion, damit ein Rollback der Anfrage sie nicht aufhebt.
Die IP-Adresse wird nur als HMAC gespeichert.
"""

from datetime import UTC, datetime

from sqlalchemy import text
from starlette.requests import Request

from app.config import get_settings
from app.platform.auth.tokens import keyed_digest
from app.platform.db import get_engine
from app.platform.problems import Problem

_UPSERT = text(
    """
    INSERT INTO rate_limit_counter (key, window_start, count) VALUES (:key, :window_start, 1)
    ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_counter.count + 1
    RETURNING count
    """
)


def client_ip(request: Request) -> str:
    # uvicorn setzt request.client aus X-Forwarded-For, wenn der Proxy vertrauenswürdig ist
    return request.client.host if request.client else "unknown"


def check(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    settings = get_settings()
    now = datetime.now(UTC).timestamp()
    window_start = int(now // window_seconds) * window_seconds
    key = f"{scope}:{keyed_digest(settings.secret_key.get_secret_value(), client_ip(request))}"
    with get_engine().begin() as conn:
        count = conn.execute(
            _UPSERT, {"key": key, "window_start": datetime.fromtimestamp(window_start, UTC)}
        ).scalar_one()
    if count > limit:
        retry_after = max(1, int(window_start + window_seconds - now))
        raise Problem(429, "rate_limited", headers={"Retry-After": str(retry_after)})
