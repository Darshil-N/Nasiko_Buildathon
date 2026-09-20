"""The work done by the Nasiko ``sitescout-scoring`` agent (plan step 5.5).

Kept here, next to the scoring logic it wraps, so it is unit-tested on the host. The agent's own
``__main__`` only adds the A2A server around ``score_for_agent``. The agent reads stored features
through a READ ONLY database session and never writes anything.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from pydantic import BaseModel, Field

from backend.app.db.analysis_store import CityInfo, open_store_url
from backend.app.services.analysis_service import AnalysisStore, score_zones


class ScoringRequest(BaseModel):
    """What the backend sends the scoring agent for one analysis."""

    city: str = Field(min_length=1)
    category: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    answers: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    top_n: int = Field(10, ge=1, le=50)


class AgentStore(AnalysisStore, Protocol):
    """Storage the agent needs: the analysis reads plus a city lookup."""

    def get_city(self, key: str) -> CityInfo | None: ...


def score_for_agent(store: AgentStore, request: ScoringRequest) -> dict[str, Any]:
    """Score one analysis and return the JSON payload the backend expects."""
    city = store.get_city(request.city)
    if city is None:
        raise LookupError(f"unknown city {request.city!r}")
    result = score_zones(
        store,
        city_id=city.id,
        city_name=city.name,
        category=request.category,
        tier=request.tier,
        answers=request.answers,
        constraints=request.constraints,
        top_n=request.top_n,
    )
    return {
        "city": city.name,
        "zones": [asdict(z) for z in result.zones],
        "config_version": result.config_version,
        "notes": result.notes,
    }


def score_from_database(database_url: str, request: ScoringRequest) -> dict[str, Any]:
    """``score_for_agent`` over a READ ONLY session on ``database_url``."""
    with open_store_url(database_url, write=False) as store:
        return score_for_agent(store, request)
