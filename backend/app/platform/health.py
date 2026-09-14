"""Prüfpunkte für Plattform, Uptime-Überwachung und Rauchtests nach der Auslieferung (Plan 6.5, 6.8)."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.platform.auth.context import public
from app.platform.db import get_engine
from app.platform.jobs import queue
from app.platform.logging import get_logger

router = APIRouter(tags=["health"], dependencies=[Depends(public)])
log = get_logger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


@lru_cache
def _scripts() -> ScriptDirectory:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return ScriptDirectory.from_config(config)


def expected_migration_head() -> str | None:
    return _scripts().get_current_head()


def migration_state(db_revision: str | None) -> str:
    """`current`, `pending` (Image neuer als Datenbank) oder `ahead` (Datenbank neuer als Image).

    `ahead` ist nach einem Rückrollen auf das vorige Image erwartet und gilt als bereit, weil
    Migrationen abwärtskompatibel sind (Plan 6.5). `pending` heißt: Migrationsjob fehlt.
    """
    if db_revision == expected_migration_head():
        return "current"
    known = {rev.revision for rev in _scripts().walk_revisions()}
    return "pending" if db_revision is None or db_revision in known else "ahead"


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "release": get_settings().release}


@router.get("/health/ready")
def ready() -> JSONResponse:
    """Datenbank erreichbar, PostGIS vorhanden, Schema mindestens auf dem Stand dieses Images."""
    checks: dict[str, object] = {}
    healthy = True
    try:
        with get_engine().connect() as conn:
            checks["postgis"] = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
            ).scalar()
            revision: str | None = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            checks["migration"] = revision
    except Exception as exc:
        log.warning("readiness_db_failed", error_type=type(exc).__name__)
        checks["database"] = "unreachable"
        healthy = False
    else:
        checks["database"] = "ok"
        if not checks["postgis"]:
            healthy = False
        state = migration_state(revision)
        checks["migration_state"] = state
        if state == "pending":
            checks["migration_expected"] = expected_migration_head()
            healthy = False
    return JSONResponse(
        {"status": "ok" if healthy else "fail", **checks}, status_code=200 if healthy else 503
    )


@router.get("/health/jobs")
def jobs() -> JSONResponse:
    """503, wenn ein fälliger Job länger als der Schwellwert wartet: Worker steht oder ist überlastet."""
    threshold = get_settings().job_waiting_alarm_minutes * 60
    with get_engine().connect() as conn:
        oldest = queue.oldest_waiting_seconds(conn)
    healthy = oldest is None or oldest < threshold
    return JSONResponse(
        {
            "status": "ok" if healthy else "fail",
            "oldest_waiting_seconds": oldest,
            "threshold_seconds": threshold,
        },
        status_code=200 if healthy else 503,
    )
