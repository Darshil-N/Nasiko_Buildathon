"""Feature build (plan step 3.8): from the loaded city data to scoring inputs for every cell.

For one business category this computes, for every cell:

* F1 anchor footfall, F4 retail cluster and F5 competition from distance-decayed sums over the
  cell's H3 k-ring (numpy; verified against ``scoring.features`` in the tests);
* affluence from OSM signals only (decision D-22: 2/3 premium-POI density + 1/3 apartment share);
* F3 residential demand from building density and land-use share (decision D-06: no population);
* F7 accessibility, F9 growth (neutral until growth data exists) and the confidence inputs;
* the tier-dependent parts (F2 tier fit, F5, F6) for all three tiers, so a "what if" tier change
  needs no recomputation.

Formulas live in the scoring library (Agent B). This module orchestrates them over the whole city,
does the city-wide percentile normalisation, and shapes the result as ``CellFeatures``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h3
import numpy as np
import numpy.typing as npt
import pandas as pd
import yaml

from pipelines.attributes import CellAttributeRow
from pipelines.catchment_sums import PoiArrays, compute_catchments, decay_sums
from pipelines.grid import GridCell
from pipelines.normalise import PoiRecord
from scoring.features import (
    accessibility,
    affluence_index,
    gap_opportunity,
    growth_momentum,
    residential_demand,
    tier_fit,
)
from scoring.score import pct
from shared.config import CategoryConfig
from shared.contracts import CellFeatures, NormalisedFeatures, RawFeatures

TIERS = ("budget", "mid", "premium")
UNKNOWN_CODE = 3  # tier code for a competitor whose tier cannot be guessed
WALK_RADIUS_M = 500.0
TRANSIT_CATEGORIES = ("bus_stop", "rail_or_metro")
PARKING_CATEGORY = "parking"
ROAD_CLASS_SCORE = {"trunk": 1.0, "primary": 1.0, "secondary": 0.7}
NO_ROAD_SCORE = 0.3
RECENCY_STALE_DAYS = 60.0  # architecture section 11.4: POIs are stale after 60 days
COMMERCIAL_ZONE_SHARE = 0.25  # land share that makes a cell "commercially zoned"
COVERAGE_PERCENTILE = 25.0  # how many POIs a commercially zoned cell is expected to have
F4_SAME_WEIGHT, F4_COMP_WEIGHT = 0.7, 0.3  # defaults of scoring.features.retail_cluster
NEUTRAL_GROWTH = 0.5

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class CategoryFeatureSet:
    """Everything built for one category."""

    category: str
    config_version: str
    feature_version: int
    cell_ids: tuple[str, ...]
    tiers: dict[str, list[CellFeatures]]
    anchor_components: dict[str, dict[str, float]]  # cell -> {poi category: decay sum}
    summary: dict[str, Any]


def load_premium_brands(path: Path) -> frozenset[str]:
    """Lower-cased premium brand names from ``config/brands_premium.yaml``.

    Accepts a flat ``brands`` list, or a mapping whose values are lists (the union is used).
    """
    if not path.exists():
        return frozenset()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("brands", [])
    names: list[str] = []
    if isinstance(raw, list):
        names = [str(b) for b in raw]
    elif isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list):
                names += [str(b) for b in value]
    return frozenset(n.strip().lower() for n in names if n.strip())


def _stars(tags: Mapping[str, str]) -> float:
    match = re.match(r"\d+(\.\d+)?", tags.get("stars", ""))
    return float(match.group(0)) if match else 0.0


def premium_flags(pois: Sequence[PoiRecord], brands: frozenset[str]) -> npt.NDArray[np.bool_]:
    """True for premium brands, car showrooms and 4-5 star hotels (architecture section 5.3)."""
    return np.array(
        [
            (p.brand or "").lower() in brands
            or (p.name or "").lower() in brands
            or p.category == "car_showroom"
            or (p.category == "hotel" and _stars(p.tags) >= 4)
            for p in pois
        ],
        dtype=bool,
    )


def rank_pct(values: FloatArray) -> FloatArray:
    """City-wide percentile rank in [0, 1], using the scoring library's ``pct``."""
    return np.asarray(pct(pd.Series(values, dtype=float)).to_numpy(), dtype=np.float64)


def tier_weights(competitor_code: int, user_tier: str) -> float:
    """Tier weight of a competitor for a user tier (same 1.0, adjacent 0.5, other 0.2, unknown 0.5).

    Mirrors ``scoring.features.competition_pressure``; a test keeps the two identical.
    """
    user = TIERS.index(user_tier)
    if competitor_code == UNKNOWN_CODE:
        return 0.5
    gap = abs(competitor_code - user)
    return 1.0 if gap == 0 else (0.5 if gap == 1 else 0.2)


def tier_cuts(targets: Mapping[str, float]) -> tuple[float, float]:
    """Affluence thresholds between budget/mid and mid/premium (midpoints of the tier targets)."""
    return (
        (targets["budget"] + targets["mid"]) / 2,
        (targets["mid"] + targets["premium"]) / 2,
    )


def _ring_mean(
    cell_ids: Sequence[str], value_by_cell: Mapping[str, float], k: int = 2
) -> FloatArray:
    out = np.zeros(len(cell_ids), dtype=np.float64)
    for i, cell in enumerate(cell_ids):
        values = [value_by_cell[c] for c in h3.grid_disk(cell, k) if c in value_by_cell]
        out[i] = sum(values) / len(values) if values else 0.0
    return out


def confidence_without_rent(poi_coverage: float, recency: float) -> float:
    """Decision D-22(c): confidence when there is no rent or price data.

    ``2/3 * poi_coverage + 1/3 * recency``, instead of the architecture's four-term formula whose
    listing and price terms would always be zero.
    """
    return max(0.0, min(1.0, (2 / 3) * poi_coverage + (1 / 3) * recency))


def build_category_features(
    *,
    city_id: int,
    cells: Sequence[GridCell],
    attributes: Mapping[str, CellAttributeRow],
    pois: Sequence[PoiRecord],
    arrays: PoiArrays,
    config: CategoryConfig,
    premium_brands: frozenset[str],
    age_days: float,
    feature_version: int = 1,
) -> CategoryFeatureSet:
    """Build ``CellFeatures`` for every cell and tier of one category."""
    cell_ids = tuple(c.h3_index for c in cells)
    n = len(cell_ids)
    catchments = compute_catchments(cells, arrays, config.catchment_k)
    decays = decay_sums(catchments, arrays, config.decay_lambda_m)  # (cells x categories)

    # --- F1 anchor footfall, F4 retail cluster (tier independent) -------------------------------
    weights = np.zeros(len(arrays.categories))
    for name, weight in config.poi_weights.items():
        if name in arrays.categories:
            weights[arrays.categories.index(name)] = weight
    f1 = decays @ weights
    same_codes = arrays.codes_for(config.competitor_categories)
    comp_codes = arrays.codes_for(config.complementary_categories)
    f4 = F4_SAME_WEIGHT * decays[:, same_codes].sum(axis=1) + F4_COMP_WEIGHT * decays[
        :, comp_codes
    ].sum(axis=1)

    # --- catchment counts: premium POIs, apartments, residential buildings, transit, parking ----
    premium = premium_flags(pois, premium_brands)
    is_apartment = np.array([p.tags.get("building") == "apartments" for p in pois], dtype=bool)
    resi_code = arrays.codes_for(["residential_building"])
    is_resi = np.isin(arrays.category_code, resi_code)
    transit_codes = arrays.codes_for(TRANSIT_CATEGORIES)
    parking_codes = arrays.codes_for([PARKING_CATEGORY])
    premium_count = np.zeros(n)
    apartment_share = np.zeros(n)
    resi_buildings = np.zeros(n)
    transit = np.zeros(n, dtype=np.int64)
    has_parking = np.zeros(n, dtype=bool)
    near_count = np.zeros(n, dtype=np.int64)
    for i, catchment in enumerate(catchments):
        idx, dist = catchment.idx, catchment.dist
        if not idx.size:
            continue
        premium_count[i] = premium[idx].sum()
        resi_here = is_resi[idx]
        resi_buildings[i] = resi_here.sum()
        if resi_here.any():
            apartment_share[i] = is_apartment[idx][resi_here].mean()
        near = dist <= WALK_RADIUS_M
        near_count[i] = near.sum()
        near_codes = arrays.category_code[idx][near]
        transit[i] = np.isin(near_codes, transit_codes).sum()
        has_parking[i] = bool(np.isin(near_codes, parking_codes).any())

    # --- affluence (OSM only, D-22) and F3 residential demand (D-06) ---------------------------
    premium_pct = rank_pct(premium_count)
    apartment_pct = rank_pct(apartment_share)
    affluence = np.array(
        [affluence_index(premium_pct[i], apartment_pct[i], None, None) for i in range(n)]
    )
    resi_share = {c: float(a.landuse_residential_share) for c, a in attributes.items()}
    resi_signal = 0.6 * rank_pct(resi_buildings) + 0.4 * rank_pct(_ring_mean(cell_ids, resi_share))
    f3_norm = np.array(
        [residential_demand(0.0, float(v), pop_weight=0.0, bldg_weight=1.0) for v in resi_signal]
    )

    # --- F7 accessibility, F9 growth (neutral) -------------------------------------------------
    f7_values: list[float] = []
    for i, c in enumerate(cell_ids):
        attrs = attributes[c]
        road_distance = attrs.main_road_dist_m if attrs.main_road_dist_m is not None else 5000.0
        road_score = ROAD_CLASS_SCORE.get(attrs.main_road_class or "", NO_ROAD_SCORE)
        f7_values.append(
            accessibility(road_score, road_distance, int(transit[i]), bool(has_parking[i]))
        )
    f7 = np.array(f7_values)
    growth, growth_estimated = growth_momentum(None, None)

    # --- confidence inputs ----------------------------------------------------------------------
    zoned = np.array(
        [
            (attributes[c].landuse_commercial_share + attributes[c].landuse_retail_share)
            >= COMMERCIAL_ZONE_SHARE
            for c in cell_ids
        ],
        dtype=bool,
    )
    expected = float(np.percentile(near_count[zoned], COVERAGE_PERCENTILE)) if zoned.any() else 0.0
    poi_coverage = (
        np.ones(n)
        if expected <= 0
        else np.where(zoned, np.minimum(1.0, near_count / expected), 1.0)
    )
    recency = max(0.0, min(1.0, 1.0 - age_days / RECENCY_STALE_DAYS))
    confidence = np.array([confidence_without_rent(float(c), recency) for c in poi_coverage])

    # --- competitor tiers (brand list, then the area's affluence) -----------------------------
    cut_low, cut_high = tier_cuts(config.tier_targets)
    affluence_of = dict(zip(cell_ids, affluence.tolist(), strict=True))
    competitor_cats = set(arrays.codes_for(config.competitor_categories).tolist())
    tier_code = np.full(len(pois), -1, dtype=np.int64)
    for j, poi in enumerate(pois):
        if int(arrays.category_code[j]) not in competitor_cats:
            continue
        if premium[j] and poi.category != "car_showroom":
            tier_code[j] = 2
            continue
        aff = affluence_of.get(arrays.cell_of_poi[j])
        tier_code[j] = (
            UNKNOWN_CODE if aff is None else (0 if aff < cut_low else (1 if aff < cut_high else 2))
        )
    competitor_by_tier = np.zeros((n, 4))
    for i, catchment in enumerate(catchments):
        idx = catchment.idx
        if not idx.size:
            continue
        mask = tier_code[idx] >= 0
        if mask.any():
            competitor_by_tier[i] = np.bincount(
                tier_code[idx][mask],
                weights=np.exp(-catchment.dist[mask] / config.decay_lambda_m),
                minlength=4,
            )

    # --- the three tiers -----------------------------------------------------------------------
    f1_pct, f4_pct, f7_pct = rank_pct(f1), rank_pct(f4), rank_pct(f7)
    tiers: dict[str, list[CellFeatures]] = {}
    for tier in TIERS:
        supply = np.zeros(n)
        for code in range(4):
            supply += tier_weights(code, tier) * competitor_by_tier[:, code]
        fit = np.array(
            [
                tier_fit(
                    float(a),
                    tier,
                    config.tier_targets,
                    config.tier_fit.shortfall_penalty,
                    config.tier_fit.overshoot_penalty,
                )
                for a in affluence
            ]
        )
        gap = np.array(
            [gap_opportunity(float(f1[i]), float(fit[i]), float(supply[i])) for i in range(n)]
        )
        f5_inverted, f6_pct = 1.0 - rank_pct(np.asarray(supply, dtype=np.float64)), rank_pct(gap)
        tiers[tier] = [
            CellFeatures(
                h3_index=cell_ids[i],
                city_id=city_id,
                feature_version=feature_version,
                raw=RawFeatures(
                    F1_anchor_footfall_raw=float(f1[i]),
                    F3_residential_demand_raw=float(resi_buildings[i]),
                    F4_retail_cluster_raw=float(f4[i]),
                    F5_competition_pressure_raw=float(supply[i]),
                    F7_accessibility_raw=float(f7[i]),
                    F8_rent_efficiency_raw=None,
                    F9_growth_momentum_raw=growth,
                    premium_poi_density_raw=float(premium_count[i]),
                    apartment_share_raw=float(apartment_share[i]),
                ),
                normalised=NormalisedFeatures(
                    F1_anchor_footfall_norm=float(f1_pct[i]),
                    F2_affluence_fit_norm=float(fit[i]),
                    F3_residential_demand_norm=float(f3_norm[i]),
                    F4_retail_cluster_norm=float(f4_pct[i]),
                    F5_competition_inverted_norm=float(f5_inverted[i]),
                    F6_gap_opportunity_norm=float(f6_pct[i]),
                    F7_accessibility_norm=float(f7_pct[i]),
                    F8_rent_efficiency_norm=None,
                    F9_growth_momentum_norm=growth,
                ),
                affluence=float(affluence[i]),
                rent_per_sqft_est=None,
                rent_is_estimated=False,
                poi_coverage=float(poi_coverage[i]),
                listing_coverage=0.0,
                recency=recency,
                price_coverage=0.0,
                confidence=float(confidence[i]),
            )
            for i in range(n)
        ]

    weighted = [c for c in config.poi_weights if c in arrays.categories]
    columns = {c: arrays.categories.index(c) for c in weighted}
    anchor_components = {
        cell_ids[i]: {
            c: round(float(decays[i, col]), 4) for c, col in columns.items() if decays[i, col] > 0
        }
        for i in range(n)
    }
    summary = {
        "cells": n,
        "catchment_k": config.catchment_k,
        "mean_catchment_pois": round(float(np.mean([c.idx.size for c in catchments])), 1),
        "cells_with_no_anchor_signal": int((f1 == 0).sum()),
        "affluence_mean": round(float(affluence.mean()), 3),
        "premium_pois": int(premium.sum()),
        "competitor_pois": int((tier_code >= 0).sum()),
        "competitor_tiers": {
            "budget": int((tier_code == 0).sum()),
            "mid": int((tier_code == 1).sum()),
            "premium": int((tier_code == 2).sum()),
            "unknown": int((tier_code == UNKNOWN_CODE).sum()),
        },
        "growth_estimated": growth_estimated,
        "expected_pois_in_commercial_cell": round(expected, 1),
        "recency": round(recency, 3),
    }
    return CategoryFeatureSet(
        category=config.category,
        config_version=config.version,
        feature_version=feature_version,
        cell_ids=cell_ids,
        tiers=tiers,
        anchor_components=anchor_components,
        summary=summary,
    )
