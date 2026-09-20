"""Tests for the feature build: numpy sums must match the scoring library's own functions."""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pytest

from pipelines.attributes import CellAttributeRow
from pipelines.build_features import (
    TIERS,
    UNKNOWN_CODE,
    build_category_features,
    confidence_without_rent,
    load_premium_brands,
    premium_flags,
    tier_cuts,
    tier_weights,
)
from pipelines.catchment_sums import PoiArrays, compute_catchments, decay_sums
from pipelines.catchments import iter_catchments
from pipelines.grid import describe_cell, point_to_cell
from pipelines.normalise import PoiRecord
from scoring.features import anchor_footfall, competition_pressure, retail_cluster
from scoring.score import ScoreEngine
from shared.config import CategoryConfig, load_category_config
from shared.contracts import POIRow

CENTRE = point_to_cell(12.9716, 77.5946, 9)
CELLS = [describe_cell(c) for c in sorted(h3.grid_disk(CENTRE, 3))]  # 37 cells
INFO = describe_cell(CENTRE)


@pytest.fixture(scope="module")
def cafe() -> CategoryConfig:
    return load_category_config("cafe")


def make_pois(seed: int = 7, n: int = 400) -> list[PoiRecord]:
    rng = np.random.default_rng(seed)
    kinds = [
        "college",
        "office",
        "cafe",
        "residential_building",
        "bus_stop",
        "parking",
        "restaurant",
    ]
    pois: list[PoiRecord] = []
    for i in range(n):
        kind = kinds[int(rng.integers(len(kinds)))]
        tags = {"building": "apartments"} if kind == "residential_building" and i % 2 else {}
        pois.append(
            PoiRecord(
                "node", i + 1, kind,
                INFO.lat + float(rng.normal(0, 0.004)), INFO.lon + float(rng.normal(0, 0.004)),
                brand="Starbucks" if kind == "cafe" and i % 5 == 0 else None, tags=tags,
            )
        )  # fmt: skip
    pois.append(PoiRecord("node", 9001, "hotel", INFO.lat, INFO.lon, tags={"stars": "5"}))
    pois.append(PoiRecord("node", 9002, "hotel", INFO.lat, INFO.lon, tags={"stars": "3"}))
    pois.append(PoiRecord("node", 9003, "car_showroom", INFO.lat, INFO.lon))
    return pois


def make_attributes() -> dict[str, CellAttributeRow]:
    return {
        c.h3_index: CellAttributeRow(
            h3_index=c.h3_index,
            landuse_residential_share=0.3 if i % 3 else 0.0,
            landuse_commercial_share=0.4 if i % 4 == 0 else 0.0,
            landuse_retail_share=0.0,
            main_road_dist_m=100.0 + 20 * i,
            main_road_class=("primary", "secondary", "trunk")[i % 3],
            locality_name="Test",
            land_use="mixed",
        )
        for i, c in enumerate(CELLS)
    }


def to_row(poi: PoiRecord, distance: float = 0.0, tier: str = "unknown") -> POIRow:
    return POIRow(
        osm_type="node", osm_id=poi.osm_id, city_id=1, category=poi.category,
        lat=poi.lat, lon=poi.lon, tier_guess=tier, distance_m=distance,
    )  # type: ignore[arg-type]  # fmt: skip


# --- numpy sums must equal the scoring library's per-POI functions ----------------------------
def test_decay_sums_match_anchor_footfall_and_retail_cluster(cafe: CategoryConfig) -> None:
    pois = make_pois()
    arrays = PoiArrays.from_pois(pois, 9)
    catchments = compute_catchments(CELLS, arrays, cafe.catchment_k)
    decays = decay_sums(catchments, arrays, cafe.decay_lambda_m)
    weights = np.zeros(len(arrays.categories))
    for name, w in cafe.poi_weights.items():
        if name in arrays.categories:
            weights[arrays.categories.index(name)] = w

    generated = list(iter_catchments(CELLS, pois, k=cafe.catchment_k, resolution=9, city_id=1))
    for i in (0, 5, 18, 30):
        rows = generated[i][1]
        expected_f1 = anchor_footfall(rows, cafe.poi_weights, cafe.decay_lambda_m)
        assert float(decays[i] @ weights) == pytest.approx(expected_f1, rel=2e-3, abs=1e-9)

        same = [r for r in rows if r.category in cafe.competitor_categories]
        comp = [r for r in rows if r.category in cafe.complementary_categories]
        expected_f4 = retail_cluster(same, comp, cafe.decay_lambda_m)
        same_codes = arrays.codes_for(cafe.competitor_categories)
        comp_codes = arrays.codes_for(cafe.complementary_categories)
        mine = 0.7 * decays[i, same_codes].sum() + 0.3 * decays[i, comp_codes].sum()
        assert float(mine) == pytest.approx(expected_f4, rel=2e-3, abs=1e-9)


@pytest.mark.parametrize("user_tier", TIERS)
@pytest.mark.parametrize("competitor_tier", [*TIERS, "unknown"])
def test_tier_weights_match_competition_pressure(user_tier: str, competitor_tier: str) -> None:
    poi = PoiRecord("node", 1, "cafe", INFO.lat, INFO.lon)
    row = to_row(poi, distance=0.0, tier=competitor_tier)
    code = UNKNOWN_CODE if competitor_tier == "unknown" else TIERS.index(competitor_tier)
    expected = competition_pressure([row], user_tier, decay_lambda_m=350.0)
    assert tier_weights(code, user_tier) == pytest.approx(expected)


# --- small helpers -----------------------------------------------------------------------------
def test_premium_flags_brands_showrooms_and_five_star_hotels() -> None:
    pois = [
        PoiRecord("node", 1, "cafe", 1, 1, brand="Starbucks"),
        PoiRecord("node", 2, "cafe", 1, 1, brand="Local Chai"),
        PoiRecord("node", 3, "car_showroom", 1, 1),
        PoiRecord("node", 4, "hotel", 1, 1, tags={"stars": "5"}),
        PoiRecord("node", 5, "hotel", 1, 1, tags={"stars": "3"}),
        PoiRecord("node", 6, "hotel", 1, 1),
    ]
    assert premium_flags(pois, frozenset({"starbucks"})).tolist() == [
        True, False, True, True, False, False,
    ]  # fmt: skip


def test_load_premium_brands_formats(tmp_path: Path) -> None:
    flat = tmp_path / "flat.yaml"
    flat.write_text("brands:\n  - Zara\n  - ' Starbucks '\n", encoding="utf-8")
    assert load_premium_brands(flat) == frozenset({"zara", "starbucks"})
    nested = tmp_path / "nested.yaml"
    nested.write_text("brands:\n  cafe: [Blue Tokai]\n  clothing: [Zara]\n", encoding="utf-8")
    assert load_premium_brands(nested) == frozenset({"blue tokai", "zara"})
    assert load_premium_brands(tmp_path / "missing.yaml") == frozenset()


def test_confidence_without_rent_and_tier_cuts() -> None:
    assert confidence_without_rent(1.0, 1.0) == pytest.approx(1.0)
    assert confidence_without_rent(0.0, 1.0) == pytest.approx(1 / 3)
    assert confidence_without_rent(1.0, 0.0) == pytest.approx(2 / 3)
    assert tier_cuts({"budget": 0.3, "mid": 0.55, "premium": 0.8}) == pytest.approx((0.425, 0.675))


# --- the whole build, and B's engine consuming it ----------------------------------------------
@pytest.fixture(scope="module")
def built(cafe: CategoryConfig):  # type: ignore[no-untyped-def]
    pois = make_pois()
    return build_category_features(
        city_id=1,
        cells=CELLS,
        attributes=make_attributes(),
        pois=pois,
        arrays=PoiArrays.from_pois(pois, 9),
        config=cafe,
        premium_brands=frozenset({"starbucks"}),
        age_days=10,
    )


def test_build_produces_features_for_every_cell_and_tier(built) -> None:  # type: ignore[no-untyped-def]
    assert set(built.tiers) == set(TIERS)
    for tier in TIERS:
        assert [f.h3_index for f in built.tiers[tier]] == [c.h3_index for c in CELLS]
    assert built.category == "cafe"
    assert built.summary["cells"] == len(CELLS)


def test_no_rent_data_is_reported_honestly(built) -> None:  # type: ignore[no-untyped-def]
    feature = built.tiers["mid"][0]
    assert feature.raw.F8_rent_efficiency_raw is None
    assert feature.normalised.F8_rent_efficiency_norm is None
    assert feature.rent_per_sqft_est is None
    assert feature.listing_coverage == 0.0
    assert feature.price_coverage == 0.0
    assert built.summary["growth_estimated"] is True
    assert feature.normalised.F9_growth_momentum_norm == 0.5


def test_tier_dependent_parts_differ_across_tiers(built) -> None:  # type: ignore[no-untyped-def]
    fits = {t: [f.normalised.F2_affluence_fit_norm for f in built.tiers[t]] for t in TIERS}
    assert fits["budget"] != fits["premium"]
    aff = [f.affluence for f in built.tiers["mid"]]
    assert aff == [f.affluence for f in built.tiers["premium"]]  # affluence itself is tier free
    # a premium store is punished at least as hard as a budget one in the least affluent cell
    poorest = int(np.argmin(aff))
    assert fits["premium"][poorest] <= fits["budget"][poorest]


def test_all_normalised_values_are_valid_and_confidence_reflects_data(built) -> None:  # type: ignore[no-untyped-def]
    for feature in built.tiers["mid"]:
        n = feature.normalised
        for value in (
            n.F1_anchor_footfall_norm, n.F2_affluence_fit_norm, n.F3_residential_demand_norm,
            n.F4_retail_cluster_norm, n.F5_competition_inverted_norm, n.F6_gap_opportunity_norm,
            n.F7_accessibility_norm,
        ):  # fmt: skip
            assert 0.0 <= value <= 1.0
        assert 0.0 < feature.confidence <= 1.0
        assert feature.recency == pytest.approx(1 - 10 / 60)


def test_anchor_components_allow_recomputing_f1_with_modified_weights(built, cafe) -> None:  # type: ignore[no-untyped-def]
    cell = CELLS[0].h3_index
    components = built.anchor_components[cell]
    f1 = sum(cafe.poi_weights[c] * v for c, v in components.items())
    assert f1 == pytest.approx(built.tiers["mid"][0].raw.F1_anchor_footfall_raw, rel=1e-3, abs=1e-3)


def test_scoring_engine_ranks_the_built_features(built, cafe) -> None:  # type: ignore[no-untyped-def]
    zones = ScoreEngine(cafe, "mid").rank(built.tiers["mid"], top_n=5)
    ranked = [z for z in zones if not z.excluded and not z.greyed]
    assert len(ranked) == 5
    assert [z.rank for z in ranked] == [1, 2, 3, 4, 5]
    assert ranked[0].score >= ranked[-1].score
    for zone in ranked:
        assert sum(zone.contributions.values()) == pytest.approx(zone.score, abs=0.1)
