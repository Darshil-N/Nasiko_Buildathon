"""
Config loader and validator for SiteScout category configurations.

Loads ``config/categories/{category}.yaml`` files and validates them against
strict rules:

- ``weights`` must sum to exactly 1.0 (within 1e-9).
- Every key in ``weights`` must be one of the nine known feature keys.
- ``tier_targets`` values must be in the range [0, 1].
- ``catchment_k`` must be a positive integer.
- ``decay_lambda_m`` must be a positive float.

Usage::

    from shared.config import load_category_config, CategoryConfig

    cfg = load_category_config("cafe")
    print(cfg.weights["F1_anchor_footfall"])   # 0.28
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KNOWN_FEATURE_KEYS: frozenset[str] = frozenset(
    {
        "F1_anchor_footfall",
        "F2_affluence_fit",
        "F3_residential_demand",
        "F4_retail_cluster",
        "F5_competition_inverted",
        "F6_gap_opportunity",
        "F7_accessibility",
        "F8_rent_efficiency",
        "F9_growth_momentum",
    }
)

_KNOWN_TIERS: frozenset[str] = frozenset({"budget", "mid", "premium"})
_WEIGHT_TOLERANCE: float = 1e-9

# Repo root is two levels above this file: shared/config.py → shared/ → repo root
_REPO_ROOT = Path(__file__).parent.parent
_CATEGORIES_DIR = _REPO_ROOT / "config" / "categories"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TierFitConfig(BaseModel):
    """Penalties applied when area affluence deviates from the tier target."""

    shortfall_penalty: float = Field(
        ...,
        gt=0.0,
        description="Multiplier on affluence shortfall below tier target (architecture §5.3)",
    )
    overshoot_penalty: float = Field(
        ...,
        gt=0.0,
        description="Multiplier on affluence overshoot above tier target",
    )


class HardFiltersConfig(BaseModel):
    """Hard constraints applied before ranking (architecture §5.5)."""

    rent_budget_multiplier: float = Field(
        1.2,
        gt=0.0,
        description="Exclude cell if est_rent * shop_size > multiplier * user_budget",
    )
    exclude_land_use: list[str] = Field(
        default_factory=list,
        description="Land-use classes that unconditionally exclude a cell",
    )
    min_confidence_ranked: float = Field(
        0.25,
        ge=0.0,
        le=1.0,
        description="Cells below this confidence are greyed and not ranked",
    )
    residential_only_flag: bool = Field(
        False,
        description=(
            "If True, residential-only cells are kept but flagged (pharmacy exception). "
            "If False, they are excluded."
        ),
    )


class CategoryConfig(BaseModel):
    """Full validated configuration for one category."""

    category: str = Field(..., description="'cafe' | 'clothing' | 'pharmacy'")
    version: str = Field(..., description="Config version string, e.g. '2026-09-a'")
    h3_resolution: int = Field(9, ge=7, le=15)
    catchment_k: int = Field(..., ge=1, description="k-ring radius for catchment aggregation")
    decay_lambda_m: float = Field(..., gt=0.0, description="Exponential decay λ in metres for F1")

    tier_labels: dict[str, str] = Field(
        ...,
        description="Human-readable label per tier id, e.g. {'budget': 'Lower class', ...}",
    )
    tier_targets: dict[str, float] = Field(
        ...,
        description="Target affluence per tier, values in [0, 1]",
    )
    tier_fit: TierFitConfig

    weights: dict[str, float] = Field(
        ...,
        description="Feature weights; must sum to 1.0 and use only known feature keys",
    )
    poi_weights: dict[str, float] = Field(
        ...,
        description="OSM category → footfall multiplier for F1 computation",
    )

    competitor_categories: list[str] = Field(default_factory=list)
    complementary_categories: list[str] = Field(default_factory=list)

    answer_modifiers: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Questionnaire answer → {poi_type: multiplier} overrides",
    )

    hard_filters: HardFiltersConfig

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("weights")
    @classmethod
    def _weights_sum_to_one(cls, v: dict[str, float]) -> dict[str, float]:
        """Weights must sum to 1.0 within _WEIGHT_TOLERANCE."""
        total = sum(v.values())
        if abs(total - 1.0) > _WEIGHT_TOLERANCE:
            raise ValueError(
                f"weights sum to {total:.10f}, expected 1.0 (tolerance {_WEIGHT_TOLERANCE})"
            )
        return v

    @field_validator("weights")
    @classmethod
    def _weights_known_keys(cls, v: dict[str, float]) -> dict[str, float]:
        """Every weight key must be a recognised feature."""
        unknown = set(v.keys()) - _KNOWN_FEATURE_KEYS
        if unknown:
            raise ValueError(
                f"Unknown weight key(s): {sorted(unknown)}. "
                f"Expected one of: {sorted(_KNOWN_FEATURE_KEYS)}"
            )
        return v

    @field_validator("tier_targets")
    @classmethod
    def _tier_targets_valid(cls, v: dict[str, float]) -> dict[str, float]:
        """Tier targets must use known tier ids and have values in [0, 1]."""
        unknown_tiers = set(v.keys()) - _KNOWN_TIERS
        if unknown_tiers:
            raise ValueError(f"Unknown tier id(s): {sorted(unknown_tiers)}")
        for tier, target in v.items():
            if not (0.0 <= target <= 1.0):
                raise ValueError(f"tier_target[{tier!r}] = {target} is out of range [0, 1]")
        return v

    @model_validator(mode="after")
    def _tier_labels_cover_all_tiers(self) -> CategoryConfig:
        """tier_labels must have an entry for every key in tier_targets."""
        missing = set(self.tier_targets.keys()) - set(self.tier_labels.keys())
        if missing:
            raise ValueError(f"tier_labels is missing entries for: {sorted(missing)}")
        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a plain dict."""
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"Expected a YAML mapping at {path}, got {type(data)}")
    return data


@functools.lru_cache(maxsize=16)
def load_category_config(category: str, *, config_dir: Path | None = None) -> CategoryConfig:
    """Load and validate the config YAML for *category*.

    Results are cached by ``category`` so repeated calls in the same process
    pay no I/O cost.  Pass a custom *config_dir* in tests to point at fixture
    files instead of the real config directory.

    Parameters
    ----------
    category:
        One of ``'cafe'``, ``'clothing'``, ``'pharmacy'`` (or any future
        category whose YAML file exists).
    config_dir:
        Directory that holds ``{category}.yaml``.  Defaults to
        ``<repo_root>/config/categories/``.

    Returns
    -------
    CategoryConfig
        Fully validated configuration object.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    pydantic.ValidationError
        If validation fails (bad weights, out-of-range values, etc.).
    """
    base_dir = config_dir if config_dir is not None else _CATEGORIES_DIR
    yaml_path = base_dir / f"{category}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Category config not found: {yaml_path}\n"
            f"Available files: {sorted(base_dir.glob('*.yaml'))}"
        )
    raw = _load_yaml(yaml_path)
    return CategoryConfig.model_validate(raw)


def list_available_categories(*, config_dir: Path | None = None) -> list[str]:
    """Return sorted category names for which a config YAML exists."""
    base_dir = config_dir if config_dir is not None else _CATEGORIES_DIR
    return sorted(p.stem for p in base_dir.glob("*.yaml"))
