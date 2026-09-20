"""GET /v1/health: liveness and versions (public, so container health checks can call it)."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.settings import API_VERSION, APP_VERSION
from backend.app.db.session import get_read_session

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthOut(BaseModel):
    """Liveness plus a database reachability hint."""

    status: Literal["ok"]
    api_version: str
    app_version: str
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthOut, summary="Liveness and versions")
def health(session: Annotated[Session, Depends(get_read_session)]) -> HealthOut:
    """Always answers; ``database`` says whether a trivial query succeeded."""
    try:
        session.execute(text("SELECT 1"))
        database: Literal["ok", "unavailable"] = "ok"
    except SQLAlchemyError:
        logger.warning("health check: database unavailable", exc_info=True)
        database = "unavailable"
    return HealthOut(
        status="ok", api_version=API_VERSION, app_version=APP_VERSION, database=database
    )
