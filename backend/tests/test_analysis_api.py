"""Tests for the analysis endpoints, driven through the real app with an in-memory store."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.db.analysis_store import AnalysisListItem, CityInfo, NearbyPoi
from backend.app.main import create_app
from backend.app.services.analysis_service import AnalysisRecord, CellMeta, StoredZone
from pipelines.features_store import FeatureBundle

KEY = "test-key-12345"
HEADERS = {"X-API-Key": KEY, "X-User-Id": "tester"}
POLYGON = {
    "type": "Polygon",
    "coordinates": [[[77.0, 12.0], [77.1, 12.0], [77.1, 12.1], [77.0, 12.0]]],
}


class MemoryStore:
    """Everything the endpoints use, kept in dictionaries. Shared across requests in one test."""

    def __init__(self, bundles: list[FeatureBundle], meta: dict[str, CellMeta]) -> None:
        self.bundles, self.meta = bundles, meta
        self.city = CityInfo(1, "bengaluru", "Bengaluru", "Karnataka", "IN", "ready")
        self.records: dict[str, AnalysisRecord] = {}
        self.zones: dict[str, list[StoredZone]] = {}
        self.users: dict[str, int] = {}
        self.write_opens = 0

    def get_city(self, key: str) -> CityInfo | None:
        return self.city if key == self.city.key else None

    def list_cities(self) -> list[CityInfo]:
        return [self.city]

    def cell_meta(self, city_id: int) -> dict[str, CellMeta]:
        return self.meta

    def cell_meta_for(self, h3_indexes: Sequence[str]) -> dict[str, CellMeta]:
        return {h: self.meta[h] for h in h3_indexes if h in self.meta}

    def cell_polygons(self, h3_indexes: Sequence[str]) -> dict[str, dict[str, Any]]:
        return dict.fromkeys(h3_indexes, POLYGON)

    def nearby_pois(self, lat: float, lon: float, radius_m: float, limit: int) -> list[NearbyPoi]:
        return [NearbyPoi("college", "Test College", None, 120.0)]

    def tier_bundles(self, category: str, tier: str) -> list[FeatureBundle]:
        return self.bundles

    def upsert_user(self, external_id: str) -> int:
        return self.users.setdefault(external_id, len(self.users) + 1)

    def create_analysis(
        self,
        analysis_id: str,
        *,
        user_id: int | None,
        city_id: int,
        category: str,
        tier: str,
        answers: dict[str, Any],
        constraints: dict[str, Any],
    ) -> None:
        self.records[analysis_id] = AnalysisRecord(
            id=analysis_id,
            city_id=city_id,
            city_key="bengaluru",
            category=category,
            tier=tier,
            answers=answers,
            constraints=constraints,
            config_version=None,
            status="queued",
            summary_narrative=None,
            created_at=datetime(2026, 9, 20, tzinfo=UTC),
        )

    def set_status(
        self,
        analysis_id: str,
        status: str,
        *,
        narrative: str | None = None,
        config_version: str | None = None,
    ) -> None:
        old = self.records[analysis_id]
        self.records[analysis_id] = AnalysisRecord(
            **{
                **old.__dict__,
                "status": status,
                "summary_narrative": narrative or old.summary_narrative,
                "config_version": config_version or old.config_version,
            }
        )

    def save_recommendations(self, analysis_id: str, zones: Sequence[StoredZone]) -> None:
        self.zones[analysis_id] = list(zones)

    def load_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        return self.records.get(analysis_id)

    def load_recommendations(self, analysis_id: str) -> list[StoredZone]:
        return self.zones.get(analysis_id, [])

    def list_analyses(self, external_user_id: str, limit: int = 50) -> list[AnalysisListItem]:
        if external_user_id not in self.users:
            return []
        return [
            AnalysisListItem(
                r.id, r.city_key, r.category, r.tier, r.status, None,
                self.zones[r.id][0].zone_name if r.id in self.zones else None,
            )
            for r in self.records.values()
        ]  # fmt: skip


@pytest.fixture
def store(bundles: list[FeatureBundle], meta: dict[str, CellMeta]) -> MemoryStore:
    return MemoryStore(bundles, meta)


@pytest.fixture
def client(store: MemoryStore) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@127.0.0.1:5433/x",
        backend_api_key=KEY,
    )
    app = create_app(settings)

    @contextmanager
    def open_store(write: bool) -> Iterator[MemoryStore]:
        store.write_opens += int(write)
        yield store

    app.state.open_store = open_store
    return TestClient(app, raise_server_exceptions=False)


REQUEST = {
    "city": "bengaluru",
    "category": "cafe",
    "tier": "mid",
    "answers": {"target_customer": ["students"], "format": "sit_down"},
    "constraints": {"monthly_rent_budget_inr": 90000, "shop_size_sqft": 600},
    "top_n": 5,
}


def create(client: TestClient, **overrides: Any) -> str:
    response = client.post("/v1/analyses", json={**REQUEST, **overrides}, headers=HEADERS)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    return str(body["analysis_id"])


# --- categories ------------------------------------------------------------------------------
def test_categories_list_tiers_and_questions(client: TestClient) -> None:
    body = client.get("/v1/categories", headers=HEADERS).json()
    by_key = {c["key"]: c for c in body["categories"]}
    assert set(by_key) == {"cafe", "clothing", "pharmacy"}
    assert [t["id"] for t in by_key["cafe"]["tiers"]] == ["budget", "mid", "premium"]
    assert by_key["cafe"]["tiers"][0]["label"] == "Lower class"
    assert any(q["id"] == "is_24x7" for q in by_key["pharmacy"]["questions"])


# --- create ----------------------------------------------------------------------------------
def test_create_runs_in_the_background_and_results_are_ready(
    client: TestClient, store: MemoryStore
) -> None:
    analysis_id = create(client)
    assert analysis_id.startswith("an_")
    assert store.users == {"tester": 1}
    body = client.get(f"/v1/analyses/{analysis_id}", headers=HEADERS).json()
    assert body["status"] == "done"
    assert [r["rank"] for r in body["recommendations"]] == [1, 2, 3, 4, 5]
    assert body["recommendations"][0]["centroid"]["lat"] > 0
    assert body["summary"].startswith("Top zone:")
    assert any("Rent and property-price" in n for n in body["data_notes"])
    saved = store.records[analysis_id]
    assert saved.constraints["top_n"] == 5
    assert saved.answers == {"target_customer": ["students"], "format": "sit_down"}


def test_user_defaults_to_local_when_no_header(client: TestClient, store: MemoryStore) -> None:
    response = client.post("/v1/analyses", json=REQUEST, headers={"X-API-Key": KEY})
    assert response.status_code == 202
    assert list(store.users) == ["local"]


@pytest.mark.parametrize(
    ("override", "code", "status"),
    [
        ({"city": "atlantis"}, "INVALID_INPUT", 422),
        ({"category": "spaceport"}, "INVALID_INPUT", 422),
        ({"tier": "ultra"}, "INVALID_INPUT", 422),
        ({"top_n": 0}, "INVALID_INPUT", 422),
    ],
)
def test_create_rejects_bad_input(
    client: TestClient, override: dict[str, Any], code: str, status: int
) -> None:
    response = client.post("/v1/analyses", json={**REQUEST, **override}, headers=HEADERS)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_create_refuses_a_city_that_is_not_ready(client: TestClient, store: MemoryStore) -> None:
    store.city = CityInfo(1, "bengaluru", "Bengaluru", "Karnataka", "IN", "building")
    response = client.post("/v1/analyses", json=REQUEST, headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CITY_NOT_READY"
    assert store.records == {}


def test_endpoints_need_the_api_key(client: TestClient) -> None:
    assert client.post("/v1/analyses", json=REQUEST).status_code == 401
    assert client.get("/v1/categories").status_code == 401


# --- read ------------------------------------------------------------------------------------
def test_unknown_analysis_is_not_found(client: TestClient) -> None:
    for path in ("", "/recommendations", "/zones/1", "/cells"):
        response = client.get(f"/v1/analyses/an_nope0000{path}", headers=HEADERS)
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_failed_analysis_reports_a_structured_error(client: TestClient, store: MemoryStore) -> None:
    analysis_id = create(client)
    store.set_status(
        analysis_id, "failed", narrative="NO_CANDIDATES: no zone passes your constraints."
    )
    body = client.get(f"/v1/analyses/{analysis_id}", headers=HEADERS).json()
    assert body["status"] == "failed"
    assert body["error"] == {"code": "NO_CANDIDATES", "message": "no zone passes your constraints."}
    assert body["recommendations"] == []


def test_recommendations_json_and_geojson(client: TestClient) -> None:
    analysis_id = create(client)
    body = client.get(f"/v1/analyses/{analysis_id}/recommendations", headers=HEADERS).json()
    assert body["status"] == "done"
    assert len(body["recommendations"]) == 5
    geo = client.get(
        f"/v1/analyses/{analysis_id}/recommendations?format=geojson", headers=HEADERS
    ).json()
    assert geo["type"] == "FeatureCollection"
    assert [f["properties"]["rank"] for f in geo["features"]] == [1, 2, 3, 4, 5]
    assert geo["features"][0]["geometry"]["type"] == "Polygon"


def test_zone_detail_includes_nearby_landmarks(client: TestClient) -> None:
    analysis_id = create(client)
    body = client.get(f"/v1/analyses/{analysis_id}/zones/2", headers=HEADERS).json()
    assert body["recommendation"]["rank"] == 2
    assert body["landmarks"] == [
        {"category": "college", "name": "Test College", "brand": None, "distance_m": 120.0}
    ]
    assert client.get(f"/v1/analyses/{analysis_id}/zones/99", headers=HEADERS).status_code == 404


def test_cells_cover_every_scored_cell(client: TestClient, meta: dict[str, CellMeta]) -> None:
    analysis_id = create(client)
    body = client.get(f"/v1/analyses/{analysis_id}/cells", headers=HEADERS).json()
    assert len(body["cells"]) == len(meta)
    ranks = sorted(c["rank"] for c in body["cells"] if c["rank"] is not None)
    assert ranks == list(range(1, len(ranks) + 1))


def test_history_lists_the_users_analyses(client: TestClient) -> None:
    analysis_id = create(client)
    body = client.get("/v1/analyses", headers=HEADERS).json()
    assert [a["analysis_id"] for a in body["analyses"]] == [analysis_id]
    assert body["analyses"][0]["top_zone"]
    other = client.get("/v1/analyses", headers={**HEADERS, "X-User-Id": "someone-else"}).json()
    assert other["analyses"] == []


# --- compare and what-if ---------------------------------------------------------------------
def test_compare_two_zones(client: TestClient) -> None:
    analysis_id = create(client)
    top = client.get(f"/v1/analyses/{analysis_id}/recommendations", headers=HEADERS).json()
    picks = [r["h3_index"] for r in top["recommendations"][:2]]
    response = client.post(
        f"/v1/analyses/{analysis_id}/compare", json={"zone_h3_indices": picks}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert [z["h3_index"] for z in body["zones"]] == picks
    assert body["zones"][0]["zone_name"] == top["recommendations"][0]["zone_name"]
    assert set(body["feature_leaders"].values()) <= set(picks)


def test_compare_rejects_duplicates_and_unknown_zones(client: TestClient) -> None:
    analysis_id = create(client)
    top = client.get(f"/v1/analyses/{analysis_id}/recommendations", headers=HEADERS).json()
    first = top["recommendations"][0]["h3_index"]
    same = client.post(
        f"/v1/analyses/{analysis_id}/compare",
        json={"zone_h3_indices": [first, first]},
        headers=HEADERS,
    )
    assert same.status_code == 422
    unknown = client.post(
        f"/v1/analyses/{analysis_id}/compare",
        json={"zone_h3_indices": [first, "89ffffffffffff"]},
        headers=HEADERS,
    )
    assert unknown.status_code == 422


def test_what_if_changes_the_tier_and_reports_rank_moves(client: TestClient) -> None:
    analysis_id = create(client)
    response = client.post(
        f"/v1/analyses/{analysis_id}/what-if", json={"tier": "premium"}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "premium"
    assert len(body["recommendations"]) == 5
    assert body["rank_changes"]
    assert {"h3_index", "zone_name", "from_rank", "to_rank"} <= set(body["rank_changes"][0])


def test_what_if_can_switch_category_and_rejects_a_bad_tier(client: TestClient) -> None:
    analysis_id = create(client)
    ok = client.post(
        f"/v1/analyses/{analysis_id}/what-if", json={"category": "pharmacy"}, headers=HEADERS
    )
    assert ok.status_code == 200
    assert ok.json()["category"] == "pharmacy"
    bad = client.post(
        f"/v1/analyses/{analysis_id}/what-if", json={"tier": "ultra"}, headers=HEADERS
    )
    assert bad.status_code == 422


def test_reads_never_open_a_write_store(client: TestClient, store: MemoryStore) -> None:
    analysis_id = create(client)
    opened = store.write_opens
    client.get(f"/v1/analyses/{analysis_id}", headers=HEADERS)
    client.get("/v1/analyses", headers=HEADERS)
    client.get(f"/v1/analyses/{analysis_id}/cells", headers=HEADERS)
    client.post(f"/v1/analyses/{analysis_id}/what-if", json={"tier": "budget"}, headers=HEADERS)
    assert store.write_opens == opened
