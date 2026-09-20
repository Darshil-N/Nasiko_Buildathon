"""Standard error envelope (architecture section 10.4) and the exception handlers that emit it.

    {"error": {"code": "CITY_NOT_READY", "message": "...", "retryable": false}}

Codes ``UNAUTHORIZED`` and ``NOT_FOUND`` are additive to the five listed in section 10.4.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    CITY_NOT_READY = "CITY_NOT_READY"
    NO_CANDIDATES = "NO_CANDIDATES"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    INTERNAL = "INTERNAL"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"


# HTTP status and default retryability for each code.
_STATUS: dict[ErrorCode, tuple[int, bool]] = {
    ErrorCode.INVALID_INPUT: (422, False),
    ErrorCode.CITY_NOT_READY: (409, False),
    ErrorCode.NO_CANDIDATES: (422, False),
    ErrorCode.UPSTREAM_TIMEOUT: (504, True),
    ErrorCode.INTERNAL: (500, False),
    ErrorCode.UNAUTHORIZED: (401, False),
    ErrorCode.NOT_FOUND: (404, False),
}


class AppError(Exception):
    """An expected, client-visible failure. Raise it from anywhere in a request."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code, default_retryable = _STATUS[code]
        self.retryable = default_retryable if retryable is None else retryable
        self.details = details


def envelope(error: AppError) -> dict[str, Any]:
    """The JSON body for an error."""
    body: dict[str, Any] = {
        "code": error.code.value,
        "message": error.message,
        "retryable": error.retryable,
    }
    if error.details:
        body["details"] = error.details
    request_id = request_id_var.get()
    if request_id:
        body["request_id"] = request_id
    return {"error": body}


def error_response(error: AppError) -> JSONResponse:
    """An HTTP response carrying the standard envelope for ``error``."""
    return JSONResponse(status_code=error.status_code, content=jsonable_encoder(envelope(error)))


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return error_response(cast(AppError, exc))


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    validation = cast(RequestValidationError, exc)
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]}
        for e in validation.errors()
    ]
    return error_response(
        AppError(ErrorCode.INVALID_INPUT, "The request is not valid.", details=details)
    )


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    if http_exc.status_code == 404:
        return error_response(AppError(ErrorCode.NOT_FOUND, "Resource not found."))
    if http_exc.status_code == 401:
        return error_response(AppError(ErrorCode.UNAUTHORIZED, "Authentication required."))
    return error_response(AppError(ErrorCode.INVALID_INPUT, str(http_exc.detail)))


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)  # the stack trace stays in the log only
    return error_response(AppError(ErrorCode.INTERNAL, "Something went wrong on our side."))


def register_error_handlers(app: FastAPI) -> None:
    """Install handlers so every failure uses the standard envelope."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
