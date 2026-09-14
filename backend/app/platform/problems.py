"""Fehler nach RFC 9457 mit stabilem `code` (Spez. 6.1)."""

from typing import Any

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.platform.i18n import request_locale, translate
from app.platform.logging import get_logger, request_id_var

PROBLEM_JSON = "application/problem+json"
log = get_logger(__name__)

_STATUS_CODES = {
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "rate_limited",
    503: "service_unavailable",
}


class Problem(Exception):
    """Fachlicher oder technischer Fehler mit stabilem Code."""

    def __init__(
        self,
        status: int,
        code: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers
        self.extra = extra


def problem_response(
    request: Request,
    status: int,
    code: str,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": translate(f"problem.{code}", request_locale(request)),
        "status": status,
        "code": code,
        "instance": request.url.path,
        "request_id": request_id_var.get(),
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem) -> JSONResponse:
        return problem_response(request, exc.status, exc.code, exc.detail, exc.headers, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(err.get("loc", ())), "type": err.get("type"), "msg": err.get("msg")}
            for err in exc.errors()
        ]
        return problem_response(request, 422, "validation_error", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, f"http_{exc.status_code}")
        return problem_response(request, exc.status_code, code, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", path=request.url.path)
        sentry_sdk.capture_exception(exc)
        return problem_response(request, 500, "internal_error")
