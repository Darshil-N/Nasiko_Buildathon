"""FastAPI application factory.

Run with:  ``uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000``
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import analyses, cities, health
from backend.app.core.errors import AppError, ErrorCode, error_response, register_error_handlers
from backend.app.core.logging import configure_logging, request_id_var
from backend.app.core.settings import API_VERSION, APP_VERSION, Settings, get_settings
from backend.app.db.analysis_store import open_store
from backend.app.services.agent_gateway import AgentGateway, NasikoScorer
from backend.app.services.nasiko_client import NasikoClient

logger = logging.getLogger("backend.access")
REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 64
SCORING_TIMEOUT_S = 60.0


def _clean_request_id(supplied: str | None) -> str:
    """Reuse a sane caller-supplied id, otherwise generate one."""
    if supplied and len(supplied) <= MAX_REQUEST_ID_LENGTH and supplied.isprintable():
        return supplied
    return uuid.uuid4().hex


def build_scorer(settings: Settings) -> NasikoScorer | None:
    """A scorer that uses the Nasiko scoring agent, or None to score in this process."""
    password = settings.nasiko_password
    if not (settings.use_nasiko_agents and settings.nasiko_username and password):
        return None
    client = NasikoClient(
        settings.nasiko_base_url,
        settings.nasiko_username,
        password.get_secret_value(),
        timeout_s=SCORING_TIMEOUT_S,
    )
    return NasikoScorer(AgentGateway(client))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Passing ``settings`` lets tests avoid the environment."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SiteScout API",
        version=APP_VERSION,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    app.state.settings = settings
    # Storage factory used by the analysis endpoints; tests replace it with an in-memory store.
    app.state.open_store = lambda write: open_store(settings, write=write)
    app.state.scorer = build_scorer(settings)  # None means: score in this process
    register_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _clean_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error", extra={"path": request.url.path})
            response = error_response(
                AppError(ErrorCode.INTERNAL, "Something went wrong on our side.")
            )
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        request_id_var.reset(token)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["X-API-Key", "X-User-Id", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    prefix = f"/{API_VERSION}"
    app.include_router(health.router, prefix=prefix, tags=["meta"])
    app.include_router(cities.router, prefix=prefix, tags=["meta"])
    app.include_router(analyses.router, prefix=prefix, tags=["analyses"])
    return app
