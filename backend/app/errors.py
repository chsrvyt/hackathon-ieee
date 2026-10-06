"""Uniform error contract: {"error": {"code", "message", "details"}}. No stack traces leak."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("attendai.errors")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None, extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details if details is not None else []
        self.extra = extra or {}


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "NOT_FOUND", f"{what} not found.")


def forbidden(message: str = "You do not have permission to access this resource.") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def _body(code: str, message: str, details: Any = None, extra: dict | None = None) -> dict:
    body = dict(extra or {})
    body["error"] = {"code": code, "message": message, "details": details if details is not None else []}
    return body


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details, exc.extra))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=_body(code, message), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors():
            if err.get("type") == "json_invalid":  # loc holds a character offset, not a field
                details.append({"field": None, "message": "The request body is not valid JSON."})
                continue
            loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
            details.append({"field": ".".join(loc) or None, "message": err.get("msg", "Invalid value")})
        first = details[0]["message"] if details else "Invalid request."
        field = details[0]["field"] if details else None
        message = f"{field}: {first}" if field else first
        return JSONResponse(status_code=422, content=_body("VALIDATION_ERROR", message, details))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log.exception("Unhandled error request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_body(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Please try again.",
                [{"request_id": request_id}] if request_id else [],
            ),
        )
