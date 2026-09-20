"""Tests for the scoring library (steps 3.9.1 - 3.9.5).

Covers:
- weights sum to 1.0 for every config (3.9.1)
- contributions sum to score (3.9.1)
- score in [0, 100] (3.9.1)
- premium tier lowers scores in low-affluence cells (3.9.1)
- worked example section 5.8 within tolerance (3.9.1)
- category awareness: same location scores differently per category (3.9.4)
- OSM-only mode: scoring works with no rent data (3.9.5)
"""

from __future__ import annotations

import math

import pytest

from scoring.features import (
    affluence_index,
    anchor_footfall,
    apply_answer_modifiers,
    confidence_score,
    growth_momentum,
    residential_demand,
    tier_fit,
)
from scoring.score import ScoreEngine, score_cell_direct
from shared.config import load_category_config
from shared.contracts import (
    CellFeatures,
    NormalisedFeatures,
    POIRow,
    RawFeatures,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_norm(
    *,
    f1: float = 0.5,
    f2: float = 0.5,
    f3: float = 0.5,
    f4: float = 0.5,
    f5: float = 0.5,
    f6: float = 0.5,
    f7: float = 0.5,
    f8: float | None = 0.5,
    f9: float = 0.5,
) -> NormalisedFeatures:
    return NormalisedFeatures(
        F1_anchor_footfall_norm=f1,
        F2_affluence_fit_norm=f2,
        F3_residential_demand_norm=f3,
        F4_retail_cluster_norm=f4,
        F5_competition_inverted_norm=f5,
        F6_gap_opportunity_norm=f6,
        F7_accessibility_norm=f7,
        F8_rent_efficiency_norm=f8,
        F9_growth_momentum_norm=f9,
    )


def _make_raw(f1: float = 1.0) -> RawFeatures:
    return RawFeatures(
        F1_anchor_footfall_raw=f1,
        F3_residential_demand_raw=0.5,
        F4_retail_cluster_raw=0.5,
        F5_competition_pressure_raw=0.5,
        F7_accessibility_raw=0.5,
        F8_rent_efficiency_raw=None,
        F9_growth_momentum_raw=0.5,
        premium_poi_density_raw=0.5,
        apartment_share_raw=0.5,
        resi_price_per_sqft=None,
        resi_rent_per_sqft=None,
    )


def _make_cell(
    h3: str = "891e2657affffff",
    city_id: int = 1,
    norm: NormalisedFeatures | None = None,
    raw: RawFeatures | None = None,
    affluence: float = 0.5,
    confidence: float = 0.8,
    rent_per_sqft: float | None = None,
) -> CellFeatures:
    return CellFeatures(
        h3_index=h3,
        city_id=city_id,
        feature_version=1,
        raw=raw or _make_raw(),
        normalised=norm or _make_norm(),
        affluence=affluence,
        rent_per_sqft_est=rent_per_sqft,
        rent_is_estimated=True,
        poi_coverage=0.8,
        listing_coverage=0.0,
        recency=1.0,
        price_coverage=0.0,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Config: weights sum to 1.0 for every category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", ["cafe", "clothing", "pharmacy"])
def test_weights_sum_to_one(category: str) -> None:
    """Step 3.9.1: weights must sum to 1.0 for every category config."""
    cfg = load_category_config(category)
    total = sum(cfg.weights.values())
    assert abs(total - 1.0) < 1e-9, f"{category} weights sum {total}"


# ---------------------------------------------------------------------------
# score_cell_direct: contributions sum to score, score in [0, 100]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", ["cafe", "clothing", "pharmacy"])
def test_contributions_sum_to_score(category: str) -> None:
    """Step 3.9.1: contributions must sum to the total score."""
    cfg = load_category_config(category)
    f = dict.fromkeys(cfg.weights, 0.6)
    score, contribs = score_cell_direct(f, cfg.weights)
    assert abs(sum(contribs.values()) - score) < 1e-9


@pytest.mark.parametrize("category", ["cafe", "clothing", "pharmacy"])
def test_score_in_range(category: str) -> None:
    """Step 3.9.1: score must be in [0, 100]."""
    cfg = load_category_config(category)
    for val in [0.0, 0.5, 1.0]:
        f = dict.fromkeys(cfg.weights, val)
        score, _ = score_cell_direct(f, cfg.weights)
        assert 0.0 <= score <= 100.0, f"{category} score {score} out of range"


# ---------------------------------------------------------------------------
# Tier fit: premium penalised in low-affluence cells
# ---------------------------------------------------------------------------


def test_premium_penalised_in_low_affluence() -> None:
    """Step 3.9.1: premium tier must score lower than budget in a low-affluence cell."""
    cfg = load_category_config("cafe")
    low_affluence = 0.10  # well below even budget target (0.30)

    premium_fit = tier_fit(
        affluence=low_affluence,
        tier="premium",
        tier_targets=cfg.tier_targets,
        shortfall_penalty=cfg.tier_fit.shortfall_penalty,
        overshoot_penalty=cfg.tier_fit.overshoot_penalty,
    )
    budget_fit = tier_fit(
        affluence=low_affluence,
        tier="budget",
        tier_targets=cfg.tier_targets,
        shortfall_penalty=cfg.tier_fit.shortfall_penalty,
        overshoot_penalty=cfg.tier_fit.overshoot_penalty,
    )
    assert (
        premium_fit < budget_fit
    ), f"premium_fit ({premium_fit}) should be < budget_fit ({budget_fit}) in a low-affluence area"


def test_tier_fit_zero_for_extreme_mismatch() -> None:
    """A premium store in a very poor area should get tier fit of 0."""
    cfg = load_category_config("cafe")
    fit = tier_fit(
        affluence=0.0,
        tier="premium",
        tier_targets=cfg.tier_targets,
        shortfall_penalty=cfg.tier_fit.shortfall_penalty,
        overshoot_penalty=cfg.tier_fit.overshoot_penalty,
    )
    assert fit == 0.0


# ---------------------------------------------------------------------------
# Worked example section 5.8 (clothing, regular/mid tier)
# ---------------------------------------------------------------------------

# Architecture section 5.8 reference values (clothing, mid tier):
# Cell A: dense residential, no shops  -> score ~39
# Cell B: established cloth market + bus hub -> score ~70
# Feature values (already normalised, F5 inverted):
_WORKED_EXAMPLE_F = {
    "A": {
        "F1_anchor_footfall": 0.30,
        "F2_affluence_fit": 0.55,
        "F3_residential_demand": 0.95,
        "F4_retail_cluster": 0.05,
        "F5_competition_inverted": 0.70,
        "F6_gap_opportunity": 0.40,
        "F7_accessibility": 0.50,
        "F8_rent_efficiency": 0.60,
        "F9_growth_momentum": 0.40,
    },
    "B": {
        "F1_anchor_footfall": 0.85,
        "F2_affluence_fit": 0.60,
        "F3_residential_demand": 0.60,
        "F4_retail_cluster": 0.95,
        "F5_competition_inverted": 0.35,
        "F6_gap_opportunity": 0.45,
        "F7_accessibility": 0.85,
        "F8_rent_efficiency": 0.40,
        "F9_growth_momentum": 0.50,
    },
}
_WORKED_EXAMPLE_EXPECTED = {"A": 39, "B": 70}
_WORKED_EXAMPLE_TOLERANCE = 3.0  # +/- 3 points allowed


@pytest.mark.parametrize(
    ("cell_name", "expected_score"),
    _WORKED_EXAMPLE_EXPECTED.items(),
)
def test_worked_example_within_tolerance(cell_name: str, expected_score: float) -> None:
    """Step 3.9.1: section 5.8 clothing worked example must be within +/- 3 points."""
    cfg = load_category_config("clothing")
    f = _WORKED_EXAMPLE_F[cell_name]
    score, _ = score_cell_direct(f, cfg.weights)
    assert abs(score - expected_score) <= _WORKED_EXAMPLE_TOLERANCE, (
        f"Cell {cell_name}: got {score:.1f}, expected {expected_score} "
        f"(tolerance +/-{_WORKED_EXAMPLE_TOLERANCE})"
    )


def test_worked_example_b_beats_a() -> None:
    """Market cell B must rank above residential cell A (clothing)."""
    cfg = load_category_config("clothing")
    score_a, _ = score_cell_direct(_WORKED_EXAMPLE_F["A"], cfg.weights)
    score_b, _ = score_cell_direct(_WORKED_EXAMPLE_F["B"], cfg.weights)
    assert score_b > score_a, f"B ({score_b:.1f}) should beat A ({score_a:.1f})"


# ---------------------------------------------------------------------------
# Category awareness (3.9.4): same features -> different scores
# ---------------------------------------------------------------------------


def test_category_awareness_different_scores() -> None:
    """Step 3.9.4: the same feature values must give different scores per category."""
    scores = {}
    for category in ["cafe", "clothing", "pharmacy"]:
        cfg = load_category_config(category)
        f = _WORKED_EXAMPLE_F["A"]
        score, _ = score_cell_direct(f, cfg.weights)
        scores[category] = score

    # They must not all be identical
    assert (
        len({round(s, 4) for s in scores.values()}) > 1
    ), f"All three categories gave the same score: {scores}"


# ---------------------------------------------------------------------------
# Feature function unit tests
# ---------------------------------------------------------------------------


class TestAnchorFootfall:
    def test_empty_pois_gives_zero(self) -> None:
        assert anchor_footfall([], {"college": 1.0}, 350.0) == 0.0

    def test_unknown_category_ignored(self) -> None:
        poi = POIRow(city_id=1, category="unknown_xyz", lat=0.0, lon=0.0, distance_m=0.0)
        result = anchor_footfall([poi], {"college": 1.0}, 350.0)
        assert result == 0.0

    def test_at_zero_distance_equals_weight(self) -> None:
        poi = POIRow(city_id=1, category="college", lat=0.0, lon=0.0, distance_m=0.0)
        result = anchor_footfall([poi], {"college": 1.0}, 350.0)
        assert abs(result - 1.0) < 1e-9

    def test_decay_at_lambda(self) -> None:
        """At distance = lambda, contribution should be e^{-1} ~0.368."""
        lam = 350.0
        poi = POIRow(city_id=1, category="college", lat=0.0, lon=0.0, distance_m=lam)
        result = anchor_footfall([poi], {"college": 1.0}, lam)
        assert abs(result - math.exp(-1.0)) < 1e-9

    def test_invalid_lambda_raises(self) -> None:
        with pytest.raises(ValueError, match="decay_lambda_m"):
            anchor_footfall([], {}, 0.0)


class TestTierFit:
    def test_perfect_match(self) -> None:
        targets = {"budget": 0.30, "mid": 0.55, "premium": 0.80}
        result = tier_fit(0.80, "premium", targets, 2.0, 0.8)
        assert result == pytest.approx(1.0)

    def test_shortfall_penalises_more_than_overshoot(self) -> None:
        targets = {"budget": 0.30, "mid": 0.55, "premium": 0.80}
        # 0.10 shortfall vs 0.10 overshoot from target
        shortfall_fit = tier_fit(0.45, "mid", targets, 2.0, 0.8)
        overshoot_fit = tier_fit(0.65, "mid", targets, 2.0, 0.8)
        assert shortfall_fit < overshoot_fit

    def test_result_clamped_to_zero(self) -> None:
        targets = {"budget": 0.30, "mid": 0.55, "premium": 0.80}
        result = tier_fit(0.0, "premium", targets, 2.0, 0.8)
        assert result == 0.0

    def test_result_clamped_to_one(self) -> None:
        targets = {"budget": 0.30, "mid": 0.55, "premium": 0.80}
        result = tier_fit(0.30, "budget", targets, 2.0, 0.8)
        assert result == pytest.approx(1.0)


class TestConfidenceScore:
    def test_full_data_gives_high_confidence(self) -> None:
        result = confidence_score(
            poi_coverage=1.0, listing_coverage=1.0, recency=1.0, price_coverage=1.0
        )
        assert result == pytest.approx(1.0)

    def test_no_data_gives_low_confidence(self) -> None:
        result = confidence_score(
            poi_coverage=0.0, listing_coverage=0.0, recency=0.0, price_coverage=0.0
        )
        assert result == pytest.approx(0.0)

    def test_poi_coverage_weighted_most(self) -> None:
        """poi_coverage has the highest weight (0.4)."""
        with_poi = confidence_score(1.0, 0.0, 0.0, 0.0)
        with_listing = confidence_score(0.0, 1.0, 0.0, 0.0)
        assert with_poi > with_listing


class TestGrowthMomentum:
    def test_no_data_returns_neutral(self) -> None:
        score, estimated = growth_momentum(None, None)
        assert score == pytest.approx(0.5)
        assert estimated is True

    def test_with_data_not_estimated(self) -> None:
        _score, estimated = growth_momentum(0.8, None)
        assert estimated is False

    def test_result_in_range(self) -> None:
        for osm in [0.0, 0.5, 1.0]:
            score, _ = growth_momentum(osm, None)
            assert 0.0 <= score <= 1.0


class TestResidentialDemand:
    def test_both_zero_gives_zero(self) -> None:
        assert residential_demand(0.0, 0.0) == 0.0

    def test_both_one_gives_one(self) -> None:
        assert residential_demand(1.0, 1.0) == pytest.approx(1.0)

    def test_invalid_weights_raise(self) -> None:
        with pytest.raises(ValueError, match=r"must equal 1\.0"):
            residential_demand(0.5, 0.5, pop_weight=0.6, bldg_weight=0.6)


class TestAffluenceIndex:
    def test_osm_only_within_range(self) -> None:
        val = affluence_index(0.7, 0.6, None, None)
        assert 0.0 <= val <= 1.0

    def test_full_data_uses_all_terms(self) -> None:
        val = affluence_index(0.5, 0.5, 0.5, 0.5)
        assert val == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# OSM-only mode: scoring with no rent data (3.9.5)
# ---------------------------------------------------------------------------


def test_osm_only_mode_scores_without_rent() -> None:
    """Step 3.9.5: scoring must work end-to-end with F8 absent."""
    cfg = load_category_config("cafe")
    norm = _make_norm(f8=None)
    cell = _make_cell(norm=norm, rent_per_sqft=None)

    engine = ScoreEngine(config=cfg, tier="mid")
    results = engine.rank([cell], top_n=10)
    assert len(results) >= 1
    assert 0.0 <= results[0].score <= 100.0


# ---------------------------------------------------------------------------
# Answer modifiers
# ---------------------------------------------------------------------------


class TestAnswerModifiers:
    def test_student_modifier_raises_college_weight(self) -> None:
        cfg = load_category_config("cafe")
        base_college = cfg.poi_weights.get("college", 0.0)
        adjusted = apply_answer_modifiers(
            cfg.poi_weights,
            cfg.answer_modifiers,
            {"target_customer": ["students"]},
        )
        assert adjusted["college"] == pytest.approx(base_college * 1.3)

    def test_no_matching_answer_leaves_weights_unchanged(self) -> None:
        cfg = load_category_config("cafe")
        adjusted = apply_answer_modifiers(
            cfg.poi_weights,
            cfg.answer_modifiers,
            {},
        )
        assert adjusted == dict(cfg.poi_weights)

    def test_does_not_mutate_original(self) -> None:
        cfg = load_category_config("cafe")
        original_college = cfg.poi_weights.get("college")
        apply_answer_modifiers(
            cfg.poi_weights,
            cfg.answer_modifiers,
            {"target_customer": ["students"]},
        )
        assert cfg.poi_weights.get("college") == original_college
