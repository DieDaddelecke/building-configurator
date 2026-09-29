"""Querschnitt je Anfrage: Anfragekennung, Logzeile, Sicherheitsköpfe, CSRF-Schutz."""

import hmac
import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.platform.auth.tokens import CSRF_COOKIE, CSRF_HEADER, new_token
from app.platform.logging import get_logger, request_id_var
from app.platform.problems import problem_response

log = get_logger("http")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            route = request.scope.get("route")
            log.info(
                "request",
                method=request.method,
                route=getattr(route, "path", None) or "unmatched",
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if get_settings().cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-Submit-Cookie: schreibende API-Aufrufe senden den Cookiewert zusätzlich im Header.

    Frontend und API liegen unter derselben Domain (Plan 6.2); das Cookie ist bewusst lesbar.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cookie = request.cookies.get(CSRF_COOKIE)
        if request.method not in SAFE_METHODS and request.url.path.startswith("/api/"):
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not hmac.compare_digest(cookie, header):
                return problem_response(request, 403, "csrf_failed")
        response = await call_next(request)
        # Nicht bei Gesundheitsprüfungen: Überwachung und Lastverteiler brauchen kein Cookie
        if not cookie and request.url.path.startswith("/api/v1/"):
            response.set_cookie(
                CSRF_COOKIE,
                new_token(),
                httponly=False,
                secure=get_settings().cookie_secure,
                samesite="lax",
                path="/",
            )
        return response
