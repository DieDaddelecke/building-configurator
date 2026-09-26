"""FastAPI-Anwendung. Welche Fachmodule ihre Router unter `/api/v1` einhängen, sagt `app.products`."""

from importlib import import_module

import sentry_sdk
from fastapi import APIRouter, FastAPI
from starlette.middleware.sessions import SessionMiddleware

import app.registry  # noqa: F401  Jobs registrieren, damit enqueue sie kennt
from app.config import Settings, get_settings
from app.platform import health
from app.platform.logging import configure_logging
from app.platform.middleware import CsrfMiddleware, RequestContextMiddleware
from app.platform.problems import install_problem_handlers
from app.products import ALL_ROUTERS, spec_for

API_V1 = "/api/v1"


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            release=settings.release,
            send_default_pii=False,
            traces_sample_rate=0.0,
        )


def create_app(settings: Settings | None = None, *, routers: tuple[str, ...] | None = None) -> FastAPI:
    """App eines Produkts; `routers` ersetzt dessen Liste (nur für das volle Profil von `openapi.json`)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.env != "local")
    init_sentry(settings)

    app = FastAPI(
        title="Emprise API",
        version="0.1.0",
        openapi_url=f"{API_V1}/openapi.json",
        docs_url=f"{API_V1}/docs" if settings.env in ("local", "test", "staging") else None,
        redoc_url=None,
    )
    install_problem_handlers(app)

    v1 = APIRouter(prefix=API_V1)
    for name in routers or spec_for(settings.product).routers:
        v1.include_router(import_module(name).router)
    app.include_router(v1)
    app.include_router(health.router, prefix="/api")

    # Reihenfolge: die zuletzt hinzugefügte Middleware liegt außen
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key.get_secret_value(),
        session_cookie="emprise_oidc",
        max_age=600,
        path="/api/v1/auth/staff",
        same_site="lax",
        https_only=settings.cookie_secure,
    )
    app.add_middleware(RequestContextMiddleware)
    return app


def create_full_app() -> FastAPI:
    """Vollständiges Profil für `openapi.json`: eine Datei mit allen Routen, unabhängig vom Produkt
    dieser Instanz (PLAN_ANALYSE 8.1 Nr. 5). Sonst müsste das Frontend zwei Typdateien pflegen. Seit AN3
    hat das Analyse-Produkt eigene Routen; sie stehen hinter denen des Konfigurators."""
    return create_app(get_settings().model_copy(update={"product": "configurator"}), routers=ALL_ROUTERS)
