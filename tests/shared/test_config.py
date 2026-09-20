"""Tests for the shared config loader (step 1.2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shared.config import CategoryConfig, list_available_categories, load_category_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cafe_config() -> CategoryConfig:
    return load_category_config("cafe")


@pytest.fixture
def clothing_config() -> CategoryConfig:
    return load_category_config("clothing")


@pytest.fixture
def pharmacy_config() -> CategoryConfig:
    return load_category_config("pharmacy")


# ---------------------------------------------------------------------------
# Tests - real YAML files
# ---------------------------------------------------------------------------


class TestLoadCategoryConfig:
    def test_cafe_loads(self, cafe_config: CategoryConfig) -> None:
        assert cafe_config.category == "cafe"

    def test_clothing_loads(self, clothing_config: CategoryConfig) -> None:
        assert clothing_config.category == "clothing"

    def test_pharmacy_loads(self, pharmacy_config: CategoryConfig) -> None:
        assert pharmacy_config.category == "pharmacy"

    def test_weights_sum_to_one_cafe(self, cafe_config: CategoryConfig) -> None:
        total = sum(cafe_config.weights.values())
        assert abs(total - 1.0) < 1e-9, f"cafe weights sum={total}"

    def test_weights_sum_to_one_clothing(self, clothing_config: CategoryConfig) -> None:
        total = sum(clothing_config.weights.values())
        assert abs(total - 1.0) < 1e-9, f"clothing weights sum={total}"

    def test_weights_sum_to_one_pharmacy(self, pharmacy_config: CategoryConfig) -> None:
        total = sum(pharmacy_config.weights.values())
        assert abs(total - 1.0) < 1e-9, f"pharmacy weights sum={total}"

    def test_tier_targets_in_range(self, cafe_config: CategoryConfig) -> None:
        for tier, target in cafe_config.tier_targets.items():
            assert 0.0 <= target <= 1.0, f"tier_target[{tier}]={target} out of [0,1]"

    def test_tier_labels_keys_match_targets(self, cafe_config: CategoryConfig) -> None:
        assert set(cafe_config.tier_labels.keys()) >= set(cafe_config.tier_targets.keys())

    def test_pharmacy_has_residential_flag(self, pharmacy_config: CategoryConfig) -> None:
        assert pharmacy_config.hard_filters.residential_only_flag is True

    def test_cafe_no_residential_flag(self, cafe_config: CategoryConfig) -> None:
        assert cafe_config.hard_filters.residential_only_flag is False

    def test_list_available_categories(self) -> None:
        cats = list_available_categories()
        assert set(cats) >= {"cafe", "clothing", "pharmacy"}


# ---------------------------------------------------------------------------
# Tests - validation errors (fixture YAML files)
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


def _minimal_valid(overrides: dict | None = None) -> dict:
    """Return a minimal valid config dict."""
    base: dict = {
        "category": "test",
        "version": "v0",
        "h3_resolution": 9,
        "catchment_k": 2,
        "decay_lambda_m": 350.0,
        "tier_labels": {"budget": "Lower class", "mid": "Medium class", "premium": "Niche"},
        "tier_targets": {"budget": 0.30, "mid": 0.55, "premium": 0.80},
        "tier_fit": {"shortfall_penalty": 2.0, "overshoot_penalty": 0.8},
        "weights": {
            "F1_anchor_footfall": 0.28,
            "F2_affluence_fit": 0.20,
            "F3_residential_demand": 0.07,
            "F4_retail_cluster": 0.05,
            "F5_competition_inverted": 0.10,
            "F6_gap_opportunity": 0.10,
            "F7_accessibility": 0.08,
            "F8_rent_efficiency": 0.07,
            "F9_growth_momentum": 0.05,
        },
        "poi_weights": {"college": 1.0},
        "competitor_categories": [],
        "complementary_categories": [],
        "answer_modifiers": {},
        "hard_filters": {
            "rent_budget_multiplier": 1.2,
            "exclude_land_use": [],
            "min_confidence_ranked": 0.25,
            "residential_only_flag": False,
        },
    }
    if overrides:
        base.update(overrides)
    return base


class TestValidationErrors:
    def test_weights_not_sum_to_one_raises(self, tmp_path: Path) -> None:
        data = _minimal_valid()
        data["weights"]["F1_anchor_footfall"] = 0.99  # makes sum ≠ 1.0
        p = _write_yaml(tmp_path, data)
        with pytest.raises(ValidationError, match="weights sum"):
            CategoryConfig.model_validate(yaml.safe_load(p.read_text()))

    def test_unknown_weight_key_raises(self, tmp_path: Path) -> None:
        data = _minimal_valid()
        # Replace one known key with an unknown one (keep sum = 1.0)
        w = data["weights"]
        w["F_UNKNOWN"] = w.pop("F9_growth_momentum")
        p = _write_yaml(tmp_path, data)
        with pytest.raises(ValidationError, match="Unknown weight key"):
            CategoryConfig.model_validate(yaml.safe_load(p.read_text()))

    def test_tier_target_out_of_range_raises(self, tmp_path: Path) -> None:
        data = _minimal_valid()
        data["tier_targets"]["budget"] = 1.5  # out of [0, 1]
        p = _write_yaml(tmp_path, data)
        with pytest.raises(ValidationError, match="out of range"):
            CategoryConfig.model_validate(yaml.safe_load(p.read_text()))

    def test_missing_tier_label_raises(self, tmp_path: Path) -> None:
        data = _minimal_valid()
        del data["tier_labels"]["premium"]
        p = _write_yaml(tmp_path, data)
        with pytest.raises(ValidationError, match="tier_labels is missing"):
            CategoryConfig.model_validate(yaml.safe_load(p.read_text()))

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_category_config("nonexistent_category_xyz", config_dir=tmp_path)

    def test_valid_minimal_config_loads(self, tmp_path: Path) -> None:
        data = _minimal_valid()
        p = _write_yaml(tmp_path, data)
        cfg = CategoryConfig.model_validate(yaml.safe_load(p.read_text()))
        assert cfg.category == "test"
