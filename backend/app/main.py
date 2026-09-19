"""FastAPI-Anwendung. Fachmodule hängen ihre Router in `create_app` unter `/api/v1` ein."""

import sentry_sdk
from fastapi import APIRouter, FastAPI
from starlette.middleware.sessions import SessionMiddleware

import app.registry  # noqa: F401  Jobs registrieren, damit enqueue sie kennt
from app.catalog import api as catalog_api
from app.config import Settings, get_settings
from app.configuration import api as configuration_api
from app.envelope import api as envelope_api
from app.inquiry import api as inquiry_api
from app.platform import flags, health, legal, ops, projects
from app.platform.auth import staff
from app.platform.jobs import api as jobs_api
from app.platform.logging import configure_logging
from app.platform.middleware import CsrfMiddleware, RequestContextMiddleware
from app.platform.problems import install_problem_handlers
from app.rules import api as rules_api
from app.site import api as site_api

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


def create_app(settings: Settings | None = None) -> FastAPI:
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
    for module in (
        staff,
        projects,
        flags,
        legal,
        ops,
        jobs_api,
        site_api,
        rules_api,
        envelope_api,
        catalog_api,
        configuration_api,
        inquiry_api,
    ):
        v1.include_router(module.router)
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
