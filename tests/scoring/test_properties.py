"""Property-based tests for the scoring engine (step 3.9.2)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from scoring.score import ScoreEngine
from shared.config import load_category_config
from shared.contracts import CellFeatures, NormalisedFeatures, RawFeatures

CAFE_CONFIG = load_category_config("cafe")

# A strategy to generate valid RawFeatures dicts
raw_features_strategy = st.builds(
    RawFeatures,
    F1_anchor_footfall_raw=st.floats(min_value=0.0, max_value=100.0),
    F3_residential_demand_raw=st.floats(min_value=0.0, max_value=100.0),
    F4_retail_cluster_raw=st.floats(min_value=0.0, max_value=100.0),
    F5_competition_pressure_raw=st.floats(min_value=0.0, max_value=100.0),
    F7_accessibility_raw=st.floats(min_value=0.0, max_value=1.0),
    F8_rent_efficiency_raw=st.floats(min_value=0.0, max_value=100.0) | st.none(),
    F9_growth_momentum_raw=st.floats(min_value=0.0, max_value=1.0),
    premium_poi_density_raw=st.floats(min_value=0.0, max_value=100.0),
    apartment_share_raw=st.floats(min_value=0.0, max_value=1.0),
    resi_price_per_sqft=st.floats(min_value=10.0, max_value=1000.0) | st.none(),
    resi_rent_per_sqft=st.floats(min_value=10.0, max_value=1000.0) | st.none(),
)

normalised_features_strategy = st.builds(
    NormalisedFeatures,
    F1_anchor_footfall_norm=st.floats(min_value=0.0, max_value=1.0),
    F2_affluence_fit_norm=st.floats(min_value=0.0, max_value=1.0),
    F3_residential_demand_norm=st.floats(min_value=0.0, max_value=1.0),
    F4_retail_cluster_norm=st.floats(min_value=0.0, max_value=1.0),
    F5_competition_inverted_norm=st.floats(min_value=0.0, max_value=1.0),
    F6_gap_opportunity_norm=st.floats(min_value=0.0, max_value=1.0),
    F7_accessibility_norm=st.floats(min_value=0.0, max_value=1.0),
    F8_rent_efficiency_norm=st.floats(min_value=0.0, max_value=1.0) | st.none(),
    F9_growth_momentum_norm=st.floats(min_value=0.0, max_value=1.0),
)

cell_features_strategy = st.builds(
    CellFeatures,
    h3_index=st.just("8961a2..."),
    city_id=st.just(1),
    feature_version=st.just(1),
    raw=raw_features_strategy,
    normalised=normalised_features_strategy,
    affluence=st.floats(min_value=0.0, max_value=1.0),
    rent_per_sqft_est=st.floats(min_value=50.0, max_value=500.0) | st.none(),
    rent_is_estimated=st.booleans(),
    poi_coverage=st.floats(min_value=0.0, max_value=1.0),
    listing_coverage=st.floats(min_value=0.0, max_value=1.0),
    recency=st.floats(min_value=0.0, max_value=1.0),
    price_coverage=st.floats(min_value=0.0, max_value=1.0),
    confidence=st.floats(min_value=0.0, max_value=1.0),
)


@given(cf=cell_features_strategy)
@settings(max_examples=100)
def test_score_bounds(cf: CellFeatures) -> None:
    """The final score is always between 0 and 100."""
    engine = ScoreEngine(CAFE_CONFIG, "premium")
    zone_score = engine.rank([cf])[0]

    assert 0.0 <= zone_score.score <= 100.0


@given(cf=cell_features_strategy)
@settings(max_examples=100)
def test_monotonicity(cf: CellFeatures) -> None:
    """Increasing a positive feature (like footfall) should not decrease the score."""
    engine = ScoreEngine(CAFE_CONFIG, "premium")
    base_score = engine.rank([cf])[0].score

    # Increase footfall
    new_footfall = min(1.0, cf.normalised.F1_anchor_footfall_norm + 0.1)
    new_norm = cf.normalised.model_copy(update={"F1_anchor_footfall_norm": new_footfall})
    cf_better = cf.model_copy(update={"normalised": new_norm})

    better_score = engine.rank([cf_better])[0].score

    assert better_score >= base_score - 1e-5  # allow tiny float error


@given(cf=cell_features_strategy)
@settings(max_examples=100)
def test_exclusion_budget(cf: CellFeatures) -> None:
    """If rent exceeds budget + 20%, it is excluded."""
    # Provide a constraints dict
    constraints = {"monthly_rent_budget_inr": 1000.0, "shop_size_sqft": 1000.0}

    # Update to a rent that is well above the 1000 INR budget + 20%
    cf_expensive = cf.model_copy(update={"rent_per_sqft_est": 2.0})

    engine = ScoreEngine(CAFE_CONFIG, "premium")
    zone_score = engine.rank([cf_expensive], constraints=constraints)[0]

    assert zone_score.excluded
    assert zone_score.exclusion_reason
    assert "budget" in zone_score.exclusion_reason.lower()
