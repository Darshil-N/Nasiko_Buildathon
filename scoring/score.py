"""
Core scoring engine for SiteScout.

Takes a list of :class:`~shared.contracts.CellFeatures` records, applies the
category-specific weights from :class:`~shared.config.CategoryConfig`, enforces
hard filters, and returns a ranked list of :class:`~shared.contracts.ZoneScore`
objects.

Design principles
-----------------
- Deterministic: given the same inputs, always returns the same output.
- Pure: no database, no network, no side effects.
- Category-aware: the same cell gets a different score per category.
- Config-over-code: adding a new category requires only a new YAML file.

Usage::

    from scoring.score import ScoreEngine
    from shared.config import load_category_config

    cfg = load_category_config("cafe")
    engine = ScoreEngine(config=cfg, tier="premium")
    results = engine.rank(
        features=cell_features_list,
        constraints={"monthly_rent_budget_inr": 120_000, "shop_size_sqft": 800},
    )
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

from shared.config import CategoryConfig
from shared.contracts import CellFeatures, ZoneScore

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Percentile normalisation
# ---------------------------------------------------------------------------

EPSILON = 1e-9


def pct(series: pd.Series[float]) -> pd.Series[float]:
    """Percentile rank (0..1) within the city.

    Uses pandas ``rank(pct=True)`` which assigns average ranks to ties.

    Parameters
    ----------
    series:
        Numeric series of raw feature values (one entry per cell).

    Returns
    -------
    pd.Series
        Ranks in [0, 1].
    """
    return series.rank(pct=True)


def pct_invert(series: pd.Series[float]) -> pd.Series[float]:
    """Percentile rank then invert so that lower raw = higher score.

    Used for negative features (e.g. F5 competition pressure, where more
    competition is *bad*).
    """
    return 1.0 - pct(series)


# ---------------------------------------------------------------------------
# Driver and risk templates
# ---------------------------------------------------------------------------

_DRIVER_TEMPLATES: dict[str, str] = {
    "F1_anchor_footfall": "High footfall anchors (offices, colleges, malls) within reach",
    "F2_affluence_fit": "Area spending power closely matches the chosen tier",
    "F3_residential_demand": "Dense residential catchment providing a local customer base",
    "F4_retail_cluster": "Strong retail cluster (market effect) in the area",
    "F5_competition_inverted": "Low same-tier competition in the catchment",
    "F6_gap_opportunity": "Significant demand-supply gap for this tier",
    "F7_accessibility": "Good road access and transit connectivity",
    "F8_rent_efficiency": "Favourable footfall-to-rent ratio",
    "F9_growth_momentum": "Positive area growth signals (construction, new projects)",
}

_RISK_TEMPLATES: dict[str, str] = {
    "F1_anchor_footfall": "Weak footfall anchors in the catchment",
    "F2_affluence_fit": "Area affluence does not well match the chosen tier",
    "F3_residential_demand": "Low residential population or building density",
    "F4_retail_cluster": "Sparse retail environment - limited cluster effect",
    "F5_competition_inverted": "High concentration of same-tier competitors nearby",
    "F6_gap_opportunity": "Low demand-supply gap; market may be saturated",
    "F7_accessibility": "Limited road access or transit connectivity",
    "F8_rent_efficiency": "High rent relative to estimated footfall potential",
    "F9_growth_momentum": "No significant growth signals detected",
}


def _top_drivers_and_risks(
    contributions: dict[str, float],
    top_n_drivers: int = 3,
    top_n_risks: int = 2,
) -> tuple[list[str], list[str]]:
    """Select top positive drivers and top risk features from contributions."""
    sorted_contribs = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    drivers = [_DRIVER_TEMPLATES.get(k, k) for k, _ in sorted_contribs[:top_n_drivers]]
    risks = [_RISK_TEMPLATES.get(k, k) for k, _ in sorted_contribs[-top_n_risks:]]
    return drivers, risks


# ---------------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------------


def _passes_rent_filter(
    rent_per_sqft_est: float | None,
    shop_size_sqft: float,
    monthly_rent_budget_inr: float,
    multiplier: float = 1.2,
) -> bool:
    """Return True if the cell passes the rent budget hard filter.

    Excludes the cell when ``rent_per_sqft * shop_size > multiplier * budget``.
    If rent data is absent, the filter does not apply (returns True).
    """
    if rent_per_sqft_est is None:
        return True
    monthly_rent = rent_per_sqft_est * shop_size_sqft
    return monthly_rent <= multiplier * monthly_rent_budget_inr


def _passes_land_use_filter(
    land_use: str | None,
    exclude_land_use: list[str],
    residential_only_flag: bool,
) -> tuple[bool, str | None]:
    """Check land-use eligibility.

    Returns ``(passes, reason)`` where ``reason`` is non-None when excluded.

    - Cells whose land-use is in ``exclude_land_use`` are always excluded.
    - If ``residential_only_flag`` is False (non-pharmacy), residential-only
      cells (land_use == 'residential') are excluded.
    - If ``residential_only_flag`` is True (pharmacy), they are kept but that
      is signalled through the greyed flag downstream.
    """
    if land_use in exclude_land_use:
        return False, f"Land use '{land_use}' is excluded for this category"
    if not residential_only_flag and land_use == "residential":
        return False, "Residential-only area; no commercial land use"
    return True, None


# ---------------------------------------------------------------------------
# Score engine
# ---------------------------------------------------------------------------


class ScoreEngine:
    """Rank cells for a given category, tier and user constraints.

    Parameters
    ----------
    config:
        Validated :class:`~shared.config.CategoryConfig`.
    tier:
        The chosen store tier: ``'budget'``, ``'mid'``, or ``'premium'``.
    """

    def __init__(self, config: CategoryConfig, tier: str) -> None:
        if tier not in config.tier_targets:
            raise ValueError(f"Unknown tier {tier!r}. Valid: {sorted(config.tier_targets.keys())}")
        self._config = config
        self._tier = tier

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(
        self,
        features: list[CellFeatures],
        constraints: dict[str, float] | None = None,
        *,
        top_n: int = 10,
        land_uses: dict[str, str | None] | None = None,
    ) -> list[ZoneScore]:
        """Score, filter and rank a list of cells.

        Parameters
        ----------
        features:
            All ``CellFeatures`` for the city.  Must include at least one cell.
        constraints:
            User constraints: ``monthly_rent_budget_inr`` and ``shop_size_sqft``.
        top_n:
            Maximum number of ranked zones to return (excludes greyed-out cells).
        land_uses:
            Optional mapping of ``h3_index → land_use`` for hard-filter checks.
            If absent, land-use filters are skipped.

        Returns
        -------
        list[ZoneScore]
            Scored zones, sorted descending by score.  Excluded cells appear
            at the end with ``excluded=True``; greyed cells have ``greyed=True``.
        """
        if not features:
            return []

        constraints = constraints or {}
        land_uses = land_uses or {}

        # --- Normalise features across the city ---
        norm_df = self._normalise(features)

        scored: list[ZoneScore] = []
        for feat in features:
            h3 = feat.h3_index
            norm_row: pd.Series[float] = norm_df.loc[h3]  # type: ignore[assignment]
            zone = self._score_cell(feat, norm_row, constraints, land_uses.get(h3))
            scored.append(zone)

        # Sort: ranked (not excluded, not greyed) by score desc, then greyed, then excluded
        ranked = [z for z in scored if not z.excluded and not z.greyed]
        greyed = [z for z in scored if not z.excluded and z.greyed]
        excluded = [z for z in scored if z.excluded]

        ranked.sort(key=lambda z: z.score, reverse=True)

        # Assign final ranks
        for i, zone in enumerate(ranked[:top_n], start=1):
            object.__setattr__(zone, "rank", i)

        return ranked[:top_n] + greyed + excluded

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalise(self, features: list[CellFeatures]) -> pd.DataFrame:
        """Build a DataFrame of city-level percentile-normalised values.

        F5 is inverted (lower competition = higher score).  F8 is omitted
        from percentile normalisation when all values are None.
        """
        rows: dict[str, dict[str, float | None]] = {}
        for feat in features:
            n = feat.normalised
            rows[feat.h3_index] = {
                "F1_anchor_footfall": n.F1_anchor_footfall_norm,
                "F2_affluence_fit": n.F2_affluence_fit_norm,
                "F3_residential_demand": n.F3_residential_demand_norm,
                "F4_retail_cluster": n.F4_retail_cluster_norm,
                "F5_competition_inverted": n.F5_competition_inverted_norm,
                "F6_gap_opportunity": n.F6_gap_opportunity_norm,
                "F7_accessibility": n.F7_accessibility_norm,
                "F8_rent_efficiency": n.F8_rent_efficiency_norm,
                "F9_growth_momentum": n.F9_growth_momentum_norm,
            }

        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index.name = "h3_index"
        return df

    def _score_cell(
        self,
        feat: CellFeatures,
        norm_row: pd.Series[float],
        constraints: dict[str, float],
        land_use: str | None,
    ) -> ZoneScore:
        """Score one cell and build its ZoneScore."""
        cfg = self._config
        weights = cfg.weights

        # --- Hard filters ---
        budget = constraints.get("monthly_rent_budget_inr")
        shop_size = constraints.get("shop_size_sqft")

        if budget is not None and shop_size is not None:
            rent_ok = _passes_rent_filter(
                feat.rent_per_sqft_est,
                shop_size,
                budget,
                cfg.hard_filters.rent_budget_multiplier,
            )
            if not rent_ok:
                return ZoneScore(
                    h3_index=feat.h3_index,
                    rank=9999,
                    score=0.0,
                    confidence=feat.confidence,
                    contributions=dict.fromkeys(weights, 0.0),
                    top_drivers=[],
                    top_risks=[],
                    excluded=True,
                    exclusion_reason="Estimated rent exceeds budget",
                )

        land_ok, land_reason = _passes_land_use_filter(
            land_use,
            cfg.hard_filters.exclude_land_use,
            cfg.hard_filters.residential_only_flag,
        )
        if not land_ok:
            return ZoneScore(
                h3_index=feat.h3_index,
                rank=9999,
                score=0.0,
                confidence=feat.confidence,
                contributions=dict.fromkeys(weights, 0.0),
                top_drivers=[],
                top_risks=[],
                excluded=True,
                exclusion_reason=land_reason,
            )

        # --- Build feature vector ---
        f_vals: dict[str, float] = {}
        for key in weights:
            col = key  # column name matches weight key
            raw_val = norm_row.get(col)
            if raw_val is None or (isinstance(raw_val, float) and math.isnan(raw_val)):
                # F8 absent when no rent data; use 0.5 (neutral) so sum still works
                f_vals[key] = 0.5
            else:
                f_vals[key] = float(raw_val)

        # --- Compute score and contributions ---
        contributions = {k: 100.0 * weights[k] * f_vals[k] for k in weights}
        score = sum(contributions.values())
        score = max(0.0, min(100.0, score))

        # Correct floating-point drift so ZoneScore validator passes
        contrib_sum = sum(contributions.values())
        if abs(contrib_sum - score) > EPSILON and contrib_sum > EPSILON:
            factor = score / contrib_sum
            contributions = {k: v * factor for k, v in contributions.items()}

        drivers, risks = _top_drivers_and_risks(contributions)

        greyed = feat.confidence < cfg.hard_filters.min_confidence_ranked

        return ZoneScore(
            h3_index=feat.h3_index,
            rank=9999,  # set after sorting
            score=round(score, 4),
            confidence=feat.confidence,
            contributions={k: round(v, 6) for k, v in contributions.items()},
            top_drivers=drivers,
            top_risks=risks,
            excluded=False,
            greyed=greyed,
        )


# ---------------------------------------------------------------------------
# Utility: worked example check (architecture §5.8)
# ---------------------------------------------------------------------------


def score_cell_direct(
    f: dict[str, float], weights: dict[str, float]
) -> tuple[float, dict[str, float]]:
    """Score a cell directly from a dict of normalised feature values.

    ``f`` must contain all keys present in ``weights``.  F5 is expected to
    have already been inverted by the caller (as per architecture Appendix E).

    Parameters
    ----------
    f:
        Normalised feature values, e.g.
        ``{"F1_anchor_footfall": 0.85, "F2_affluence_fit": 0.60, ...}``.
        Key format matches the weight keys in category YAML files.
    weights:
        Feature weights summing to 1.0.

    Returns
    -------
    (score, contributions)
        ``score`` is in [0, 100]; ``contributions`` sums to ``score``.
    """
    contributions = {k: 100.0 * weights[k] * f[k] for k in weights}
    score = sum(contributions.values())
    return score, contributions
