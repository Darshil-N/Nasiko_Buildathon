"""
Tier-fit module for SiteScout.

Provides the ``TierFitEngine`` class, which wraps the pure ``tier_fit`` and
``affluence_index`` functions from :mod:`scoring.features` together with a
``CategoryConfig``.  This is the primary interface used by the scoring engine
to compute F2 (affluence_fit).
"""

from __future__ import annotations

from dataclasses import dataclass

from scoring.features import affluence_index, tier_fit
from shared.config import CategoryConfig


@dataclass(frozen=True)
class AffluenceResult:
    """Output of affluence computation for one cell."""

    affluence: float
    """Affluence index in [0, 1]."""

    tier_fit_score: float
    """How well the area matches the chosen tier, in [0, 1]."""

    data_sources: list[str]
    """Which data sources were used, e.g. ``['osm_premium_poi', 'apartment_share']``."""


class TierFitEngine:
    """Compute F2 (affluence_fit) for a set of cells using category config.

    Parameters
    ----------
    config:
        Loaded and validated category configuration.
    tier:
        The store tier the user chose: ``'budget'``, ``'mid'``, or ``'premium'``.
    """

    def __init__(self, config: CategoryConfig, tier: str) -> None:
        if tier not in config.tier_targets:
            raise ValueError(
                f"Unknown tier {tier!r}. Valid tiers: {sorted(config.tier_targets.keys())}"
            )
        self._config = config
        self._tier = tier

    def compute(
        self,
        *,
        premium_poi_density_pct: float,
        apartment_share_pct: float,
        resi_price_per_sqft_pct: float | None = None,
        resi_rent_per_sqft_pct: float | None = None,
    ) -> AffluenceResult:
        """Compute affluence and tier fit for one cell.

        All ``*_pct`` parameters are percentile ranks (0..1) relative to the
        full city.

        Parameters
        ----------
        premium_poi_density_pct:
            City percentile rank of premium POI density.
        apartment_share_pct:
            City percentile rank of apartment fraction.
        resi_price_per_sqft_pct:
            City percentile rank of residential price per sq ft.
            ``None`` when no CSV data is available.
        resi_rent_per_sqft_pct:
            City percentile rank of residential rent per sq ft.
            ``None`` when no CSV data is available.

        Returns
        -------
        AffluenceResult
        """
        aff = affluence_index(
            premium_poi_density=premium_poi_density_pct,
            apartment_share=apartment_share_pct,
            resi_price_per_sqft_pct=resi_price_per_sqft_pct,
            resi_rent_per_sqft_pct=resi_rent_per_sqft_pct,
        )
        fit = tier_fit(
            affluence=aff,
            tier=self._tier,
            tier_targets=self._config.tier_targets,
            shortfall_penalty=self._config.tier_fit.shortfall_penalty,
            overshoot_penalty=self._config.tier_fit.overshoot_penalty,
        )

        sources: list[str] = ["premium_poi_density", "apartment_share"]
        if resi_price_per_sqft_pct is not None:
            sources.append("resi_price_per_sqft")
        if resi_rent_per_sqft_pct is not None:
            sources.append("resi_rent_per_sqft")

        return AffluenceResult(
            affluence=aff,
            tier_fit_score=fit,
            data_sources=sources,
        )
