"""Tests for the scoring agent's own logic (plan step 5.5), against an in-memory store."""

from __future__ import annotations

import pytest

from backend.app.db.analysis_store import CityInfo
from backend.app.services.analysis_service import CellMeta
from backend.app.services.scoring_agent import ScoringRequest, score_for_agent
from backend.tests.test_analysis_service import MemoryStore, record
from pipelines.features_store import FeatureBundle

CITY = CityInfo(
    id=1, key="bengaluru", name="Bengaluru", state=None, country="India", status="ready"
)


class AgentMemoryStore(MemoryStore):
    def get_city(self, key: str) -> CityInfo | None:
        return CITY if key == CITY.key else None


def test_score_for_agent_returns_the_same_shape_as_the_backend(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta]
) -> None:
    store = AgentMemoryStore(bundles, meta, record())
    request = ScoringRequest(city="bengaluru", category="cafe", tier="mid", top_n=3)
    payload = score_for_agent(store, request)
    assert payload["city"] == "Bengaluru"
    assert len(payload["zones"]) == 3
    assert payload["zones"][0]["rank"] == 1
    assert isinstance(payload["config_version"], str)
    assert isinstance(payload["notes"], list)


def test_score_for_agent_rejects_an_unknown_city(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta]
) -> None:
    store = AgentMemoryStore(bundles, meta, record())
    request = ScoringRequest(city="nowhere", category="cafe", tier="mid")
    with pytest.raises(LookupError, match="nowhere"):
        score_for_agent(store, request)


def test_scoring_request_rejects_out_of_range_top_n() -> None:
    with pytest.raises(ValueError, match="top_n"):
        ScoringRequest(city="bengaluru", category="cafe", tier="mid", top_n=0)
