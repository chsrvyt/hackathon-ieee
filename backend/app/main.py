from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import SessionLocal
from .errors import register_error_handlers
from .routers import alerts, analytics, attendance, auth, condonation, meta, students

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "AttendAI"


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


log = logging.getLogger("attendai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info(
        "AttendAI starting env=%s docs=%s static=%s cors=%s",
        settings.app_env,
        settings.docs_enabled,
        bool(settings.static_path),
        settings.allowed_origins,
    )
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="AttendAI API",
        version="1.0.0",
        description="Attendance Shortage Early Warning & Condonation System",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        path = request.url.path
        # CSRF defence-in-depth: state-changing API calls must carry a custom header. Browsers
        # only send custom headers cross-origin after a CORS preflight, which only allowed origins pass.
        if (
            path.startswith("/api/")
            and request.method in UNSAFE_METHODS
            and request.headers.get(CSRF_HEADER) != CSRF_VALUE
        ):
            response = JSONResponse(
                status_code=403,
                content={
                    "error": {"code": "CSRF_CHECK_FAILED", "message": f"Missing {CSRF_HEADER} header.", "details": []}
                },
            )
        else:
            start = time.perf_counter()
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            if path != "/health":
                log.info("%s %s %s %.0fms rid=%s", request.method, path, response.status_code, elapsed, request_id)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type", "X-Requested-With"],
            max_age=600,
        )

    def _health() -> JSONResponse:
        db = SessionLocal()
        try:
            status, body = meta.health_payload(db)
        finally:
            db.close()
        return JSONResponse(status_code=status, content=body)

    app.add_api_route("/health", _health, methods=["GET"], include_in_schema=True, tags=["meta"])
    app.add_api_route("/api/health", _health, methods=["GET"], include_in_schema=False)

    api = APIRouter(prefix="/api")
    for module in (auth, students, attendance, analytics, alerts, condonation, meta):
        api.include_router(module.router)
    app.include_router(api)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], include_in_schema=False)
    async def api_not_found(path: str) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Unknown API route.", "details": []}}
        )

    static = settings.static_path
    if static is not None:
        _mount_frontend(app, static)
    return app


_SPA_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def _mount_frontend(app: FastAPI, static: Path) -> None:
    """Serve the built React app. Unknown non-API paths fall back to index.html (client-side routing)."""
    root = static.resolve()
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        response = FileResponse(index, headers={"Cache-Control": "no-cache"})
        response.headers["Content-Security-Policy"] = _SPA_CSP
        return response


app = create_app()
