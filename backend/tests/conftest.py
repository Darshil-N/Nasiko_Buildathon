"""Fixtures shared by the backend tests: a small synthetic city scored for a cafe."""

from __future__ import annotations

import h3
import numpy as np
import pytest

from backend.app.services.analysis_service import CellMeta
from pipelines.attributes import CellAttributeRow
from pipelines.build_features import build_category_features
from pipelines.catchment_sums import PoiArrays
from pipelines.features_store import FeatureBundle
from pipelines.grid import describe_cell, point_to_cell
from pipelines.normalise import PoiRecord
from shared.config import CategoryConfig, load_category_config

CENTRE = point_to_cell(12.9716, 77.5946, 9)
CELLS = [describe_cell(c) for c in sorted(h3.grid_disk(CENTRE, 3))]
INFO = describe_cell(CENTRE)


@pytest.fixture(scope="module")
def cafe() -> CategoryConfig:
    return load_category_config("cafe")


@pytest.fixture(scope="module")
def bundles(cafe: CategoryConfig) -> list[FeatureBundle]:
    rng = np.random.default_rng(3)
    kinds = ["college", "office", "cafe", "residential_building", "bus_stop", "restaurant"]
    pois = [
        PoiRecord(
            "node",
            i,
            kinds[i % len(kinds)],
            INFO.lat + float(rng.normal(0, 0.004)),
            INFO.lon + float(rng.normal(0, 0.004)),
        )
        for i in range(1, 500)
    ]
    attributes = {
        c.h3_index: CellAttributeRow(
            c.h3_index, 0.2, 0.3 if i % 2 else 0.0, 0.0, 150.0, "primary", "Area", "mixed"
        )
        for i, c in enumerate(CELLS)
    }
    built = build_category_features(
        city_id=1,
        cells=CELLS,
        attributes=attributes,
        pois=pois,
        arrays=PoiArrays.from_pois(pois, 9),
        config=cafe,
        premium_brands=frozenset(),
        age_days=1,
    )
    return [FeatureBundle(f, built.anchor_components[f.h3_index]) for f in built.tiers["mid"]]


@pytest.fixture(scope="module")
def meta() -> dict[str, CellMeta]:
    names = ["Indiranagar", "Koramangala", "Indiranagar", None]
    return {
        c.h3_index: CellMeta(c.h3_index, names[i % 4], "mixed", c.lat, c.lon)
        for i, c in enumerate(CELLS)
    }
