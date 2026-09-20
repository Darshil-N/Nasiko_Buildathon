"""Shared-secret authentication (architecture section 10: X-API-Key and X-User-Id)."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from backend.app.core.errors import AppError, ErrorCode
from backend.app.core.settings import Settings


def get_app_settings(request: Request) -> Settings:
    """The settings of the running app (overridable in tests)."""
    settings: Settings = request.app.state.settings
    return settings


def require_api_key(
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Reject requests whose ``X-API-Key`` does not match, using a constant-time comparison."""
    expected = settings.backend_api_key.get_secret_value().encode()
    supplied = (x_api_key or "").encode()
    if not hmac.compare_digest(supplied, expected):
        raise AppError(ErrorCode.UNAUTHORIZED, "Missing or invalid API key.")


def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str | None:
    """The end user's id as passed by the Streamlit app, if any."""
    return x_user_id.strip() if x_user_id and x_user_id.strip() else None
