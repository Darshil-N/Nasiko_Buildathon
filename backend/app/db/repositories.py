"""Typed read queries. Each function takes a session and returns plain data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import City


@dataclass(frozen=True)
class CitySummary:
    """The public facts about a city."""

    id: int
    key: str
    name: str
    state: str | None
    country: str


def list_ready_cities(session: Session) -> list[CitySummary]:
    """Cities whose data is complete (status ``ready``), ordered by name."""
    statement = (
        select(City.id, City.key, City.name, City.state, City.country)
        .where(City.status == "ready")
        .order_by(City.name)
    )
    return [
        CitySummary(row.id, row.key, row.name, row.state, row.country)
        for row in session.execute(statement).all()
    ]
