"""GET /v1/cities: cities that are ready for analysis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.auth import require_api_key
from backend.app.db.repositories import list_ready_cities
from backend.app.db.session import get_read_session

router = APIRouter(dependencies=[Depends(require_api_key)])


class CityOut(BaseModel):
    """A city the user can run an analysis for."""

    id: int
    key: str
    name: str
    state: str | None
    country: str
    status: str = "ready"


class CitiesOut(BaseModel):
    """The list wrapper the Streamlit client expects."""

    cities: list[CityOut]


@router.get("/cities", response_model=CitiesOut, summary="Cities with status ready")
def cities(session: Annotated[Session, Depends(get_read_session)]) -> CitiesOut:
    """Only cities whose data is complete are listed."""
    return CitiesOut(cities=[CityOut(**vars(c)) for c in list_ready_cities(session)])
