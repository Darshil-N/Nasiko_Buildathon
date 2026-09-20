"""Tests for storing and reading cell features (fake connection and session; no database)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import h3
import pytest

from pipelines import features_store
from pipelines.attributes import CellAttributeRow
from pipelines.build_features import TIERS, CategoryFeatureSet, build_category_features
from pipelines.catchment_sums import PoiArrays
from pipelines.features_store import (
    feature_rows,
    load_tier_features,
    mark_city_ready,
    store_feature_set,
)
from pipelines.grid import describe_cell, point_to_cell
from pipelines.normalise import PoiRecord
from shared.config import load_category_config

CENTRE = point_to_cell(12.9716, 77.5946, 9)
CELLS = [describe_cell(c) for c in sorted(h3.grid_disk(CENTRE, 2))]


def small_set() -> CategoryFeatureSet:
    info = describe_cell(CENTRE)
    pois = [PoiRecord("node", i, "college", info.lat, info.lon) for i in range(1, 6)]
    attributes = {
        c.h3_index: CellAttributeRow(c.h3_index, 0.1, 0.0, 0.0, 200.0, "primary", "T", "mixed")
        for c in CELLS
    }
    return build_category_features(
        city_id=1,
        cells=CELLS,
        attributes=attributes,
        pois=pois,
        arrays=PoiArrays.from_pois(pois, 9),
        config=load_category_config("cafe"),
        premium_brands=frozenset(),
        age_days=1,
    )


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, statement: Any, params: Any = None) -> SimpleNamespace:
        self.calls.append((str(statement), params))
        return SimpleNamespace(scalar_one=lambda: 7)


def test_feature_rows_hold_all_tiers_and_anchor_sums() -> None:
    feature_set = small_set()
    rows = feature_rows(feature_set, city_id=7)
    assert len(rows) == len(CELLS)
    row = rows[0]
    assert row["category"] == "cafe"
    assert row["feature_version"] == 1
    payload = json.loads(row["features"])
    assert set(payload["tiers"]) == set(TIERS)
    assert payload["tiers"]["mid"]["city_id"] == 7
    assert payload["config_version"] == feature_set.config_version
    assert "anchor_components" in payload
    assert 0.0 <= row["affluence"] <= 1.0
    assert 0.0 <= row["confidence"] <= 1.0


def test_store_uses_the_city_id_and_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(features_store, "BATCH_SIZE", 10)
    conn = FakeConnection()
    count = store_feature_set(conn, small_set(), "bengaluru")  # type: ignore[arg-type]
    assert count == len(CELLS)
    assert conn.calls[0][1] == {"key": "bengaluru"}
    batches = [params for sql, params in conn.calls if "INSERT INTO cell_features" in sql]
    assert sum(len(b) for b in batches) == len(CELLS)
    assert len(batches) == -(-len(CELLS) // 10)
    assert all(row["features"] for batch in batches for row in batch)


def test_statements_are_idempotent_and_mark_ready_is_scoped_to_one_city() -> None:
    assert "ON CONFLICT (h3_index, category, feature_version) DO UPDATE" in str(
        features_store.UPSERT_CELL_FEATURES
    )
    conn = FakeConnection()
    mark_city_ready(conn, "bengaluru")  # type: ignore[arg-type]
    sql, params = conn.calls[0]
    assert "status = 'ready'" in sql
    assert "WHERE key = :key" in sql
    assert params == {"key": "bengaluru"}


def test_load_tier_features_round_trips_and_selects_only_one_tier() -> None:
    feature_set = small_set()
    stored = json.loads(feature_rows(feature_set, 7)[0]["features"])["tiers"]["premium"]

    class FakeSession:
        statement = ""
        params: Any = None

        def execute(self, statement: Any, params: Any = None) -> SimpleNamespace:
            FakeSession.statement, FakeSession.params = str(statement), params
            return SimpleNamespace(all=lambda: [SimpleNamespace(tier_features=stored)])

    features = load_tier_features(FakeSession(), "cafe", "premium")  # type: ignore[arg-type]
    assert features[0].h3_index == CELLS[0].h3_index
    assert features[0].city_id == 7
    assert "features -> 'tiers' -> CAST(:tier AS TEXT)" in FakeSession.statement
    assert FakeSession.params == {"category": "cafe", "tier": "premium", "feature_version": 1}
