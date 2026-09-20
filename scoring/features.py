"""
Scoring library: raw feature computation.

All functions are pure (no I/O, no randomness).  They operate on in-memory
Python structures so they can run in any environment without a database.

Units
-----
- ``distance_m``         metres (float ≥ 0)
- ``decay_lambda_m``     metres (float > 0)
- ``poi_weights``        dimensionless multiplier (float ≥ 0)
- ``affluence``          0 .. 1
- ``anchor_raw``         0 .. ∞ (percentile-normalised in :mod:`scoring.score`)
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from shared.contracts import POIRow

# ---------------------------------------------------------------------------
# F1 - Anchor footfall
# ---------------------------------------------------------------------------


def anchor_footfall(
    pois_in_catchment: list[POIRow],
    poi_weights: dict[str, float],
    decay_lambda_m: float,
) -> float:
    """Distance-decayed weighted sum of landmarks in the catchment.

    Each POI contributes ``w[category] x exp(-d / λ)``.  POIs with unknown
    categories get weight 0 and are effectively ignored.

    Parameters
    ----------
    pois_in_catchment:
        All POIs in the cell's k-ring, each with a populated ``distance_m``.
    poi_weights:
        Category → footfall weight mapping from the category config.
    decay_lambda_m:
        Exponential decay constant in metres (``λ``).  Smaller values make
        the footfall drop off faster with distance.

    Returns
    -------
    float
        Raw (un-normalised) anchor footfall score ≥ 0.
    """
    if decay_lambda_m <= 0:
        raise ValueError(f"decay_lambda_m must be > 0, got {decay_lambda_m}")

    total = 0.0
    for poi in pois_in_catchment:
        w = poi_weights.get(poi.category, 0.0)
        if w == 0.0:
            continue
        d = poi.distance_m if poi.distance_m is not None else 0.0
        total += w * math.exp(-d / decay_lambda_m)
    return total


def apply_answer_modifiers(
    poi_weights: dict[str, float],
    answer_modifiers: dict[str, dict[str, float]],
    answers: dict[str, object],
) -> dict[str, float]:
    """Return a *copy* of ``poi_weights`` with questionnaire modifiers applied.

    Modifiers are additive on the multiplier: if ``target_customer.students``
    sets ``{college: 1.3}`` the college weight is multiplied by 1.3.

    Parameters
    ----------
    poi_weights:
        Base POI weights from the category config.
    answer_modifiers:
        Mapping of ``"key.value"`` → ``{poi_type: multiplier}``.
    answers:
        Flat dict of questionnaire answers, e.g.
        ``{"target_customer": ["students", "families"]}``.

    Returns
    -------
    dict[str, float]
        Adjusted weights (new dict, original unchanged).
    """
    adjusted: dict[str, float] = dict(poi_weights)
    for modifier_key, overrides in answer_modifiers.items():
        # modifier_key format: "answer_field.answer_value"
        if "." not in modifier_key:
            continue
        field, value = modifier_key.split(".", 1)
        answer = answers.get(field)
        # Support single values and lists (multi-select questions)
        answer_list = answer if isinstance(answer, list) else [answer]
        if value in answer_list:
            for poi_type, multiplier in overrides.items():
                if poi_type in adjusted:
                    adjusted[poi_type] = adjusted[poi_type] * multiplier
    return adjusted


# ---------------------------------------------------------------------------
# F2 - Affluence and tier fit (also used for F6)
# ---------------------------------------------------------------------------


def affluence_index(
    premium_poi_density: float,
    apartment_share: float,
    resi_price_per_sqft_pct: float | None,
    resi_rent_per_sqft_pct: float | None,
) -> float:
    """Compute the affluence index for one cell.

    Uses the architecture §5.3 formula when price / rent data are available.
    When both are absent, only the OSM proxies are used and the weight is
    redistributed (handled here by accepting ``None``).

    Architecture formula (with data)::

        0.40 x pct(resi_price_per_sqft)
        + 0.15 x pct(resi_rent_per_sqft)
        + 0.30 x pct(premium_poi_density)
        + 0.15 x pct(apartment_share)

    When price / rent are absent (D-22 deferred), only the two OSM terms are
    available.  This function accepts their already-normalised (0..1) values
    so the caller can pass the city-level percentile rank directly.

    Parameters
    ----------
    premium_poi_density:
        Percentile rank (0..1) of the cell's premium POI density.
    apartment_share:
        Percentile rank (0..1) of the cell's apartment-to-total-buildings ratio.
    resi_price_per_sqft_pct:
        Percentile rank (0..1) of residential sale price per sq ft.
        Pass ``None`` when no price data exists.
    resi_rent_per_sqft_pct:
        Percentile rank (0..1) of residential rent per sq ft.
        Pass ``None`` when no rent data exists.

    Returns
    -------
    float
        Affluence index in [0, 1].
    """
    has_price = resi_price_per_sqft_pct is not None
    has_rent = resi_rent_per_sqft_pct is not None

    if has_price and has_rent:
        # Full §5.3 formula
        val = (
            0.40 * resi_price_per_sqft_pct  # type: ignore[operator]
            + 0.15 * resi_rent_per_sqft_pct  # type: ignore[operator]
            + 0.30 * premium_poi_density
            + 0.15 * apartment_share
        )
    elif has_price:
        # Rent missing; rescale: 0.40+0.30+0.15 = 0.85 -> normalise to 1
        val = (
            0.40 * resi_price_per_sqft_pct  # type: ignore[operator]
            + 0.30 * premium_poi_density
            + 0.15 * apartment_share
        ) / 0.85
    elif has_rent:
        # Price missing
        val = (
            0.15 * resi_rent_per_sqft_pct  # type: ignore[operator]
            + 0.30 * premium_poi_density
            + 0.15 * apartment_share
        ) / 0.60
    else:
        # No property data at all (OSM-only case; weights from D-22 proposal)
        # 0.30 premium_poi + 0.15 apartment → rescale to 1.0
        val = (0.30 * premium_poi_density + 0.15 * apartment_share) / 0.45

    return max(0.0, min(1.0, val))


def tier_fit(
    affluence: float,
    tier: str,
    tier_targets: dict[str, float],
    shortfall_penalty: float,
    overshoot_penalty: float,
) -> float:
    """Compute how well the area's affluence matches the chosen tier.

    Architecture formula (§5.3)::

        short = max(0, tier_target - affluence)
        over  = max(0, affluence - tier_target)
        fit   = clamp(1 - shortfall_penalty x short - overshoot_penalty x over, 0, 1)

    Parameters
    ----------
    affluence:
        Cell affluence index (0..1).
    tier:
        Chosen store tier: ``'budget'``, ``'mid'``, or ``'premium'``.
    tier_targets:
        Mapping of tier → target affluence value (from category config).
    shortfall_penalty:
        Multiplier on affluence shortfall (architecture uses 2.0).
    overshoot_penalty:
        Multiplier on affluence overshoot (architecture uses 0.8).

    Returns
    -------
    float
        Tier fit score in [0, 1].  1.0 means perfect match; 0.0 means very
        poor match.
    """
    t = tier_targets[tier]
    short = max(0.0, t - affluence)
    over = max(0.0, affluence - t)
    raw = 1.0 - shortfall_penalty * short - overshoot_penalty * over
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# F3 - Residential demand
# ---------------------------------------------------------------------------


def residential_demand(
    population_density_pct: float,
    building_density_pct: float,
    pop_weight: float = 0.6,
    bldg_weight: float = 0.4,
) -> float:
    """Composite residential demand for a cell.

    Both inputs are expected to be already percentile-ranked (0..1) at the
    city level.  The weights default to 60 / 40 but can be overridden.

    Parameters
    ----------
    population_density_pct:
        Percentile rank of population density.
    building_density_pct:
        Percentile rank of residential building density.
    pop_weight:
        Weight for population density term.
    bldg_weight:
        Weight for building density term.

    Returns
    -------
    float
        Residential demand index in [0, 1].
    """
    if abs(pop_weight + bldg_weight - 1.0) > 1e-9:
        raise ValueError("pop_weight + bldg_weight must equal 1.0")
    val = pop_weight * population_density_pct + bldg_weight * building_density_pct
    return max(0.0, min(1.0, val))


# ---------------------------------------------------------------------------
# F4 - Retail cluster
# ---------------------------------------------------------------------------


def retail_cluster(
    same_category_pois: list[POIRow],
    complementary_pois: list[POIRow],
    decay_lambda_m: float,
    same_weight: float = 0.7,
    comp_weight: float = 0.3,
) -> float:
    """Distance-decayed retail cluster density.

    Combines same-category shops (market cluster effect) and complementary
    shops.  For clothing, same-category is a *positive* cluster signal.

    Parameters
    ----------
    same_category_pois:
        Competitor or same-category POIs in catchment, with ``distance_m``.
    complementary_pois:
        Complementary category POIs in catchment, with ``distance_m``.
    decay_lambda_m:
        Decay constant in metres.
    same_weight, comp_weight:
        Relative weights for same-category vs complementary contributions.

    Returns
    -------
    float
        Raw retail cluster score ≥ 0 (percentile-normalised by the caller).
    """

    def _decay_sum(pois: list[POIRow]) -> float:
        return sum(math.exp(-(p.distance_m or 0.0) / decay_lambda_m) for p in pois)

    return same_weight * _decay_sum(same_category_pois) + comp_weight * _decay_sum(
        complementary_pois
    )


# ---------------------------------------------------------------------------
# F5 - Competition pressure
# ---------------------------------------------------------------------------


def competition_pressure(
    competitor_pois: list[POIRow],
    user_tier: str,
    decay_lambda_m: float,
) -> float:
    """Distance-weighted competition pressure (raw, before inversion).

    Architecture formula::

        supply(cell) = Σ  exp(-d/λ) x tier_weight(c.tier, user.tier)
        tier_weight  = 1.0 same tier  |  0.5 adjacent  |  0.2 otherwise

    Parameters
    ----------
    competitor_pois:
        Same-category POIs in catchment with ``tier_guess`` and ``distance_m``.
    user_tier:
        The tier the user is opening: ``'budget'``, ``'mid'``, ``'premium'``.
    decay_lambda_m:
        Decay constant in metres.

    Returns
    -------
    float
        Raw competition pressure ≥ 0.  Higher = more competition.
        The caller inverts this (``1 - percentile``) before scoring.
    """
    _tier_order: dict[str, int] = {"budget": 0, "mid": 1, "premium": 2, "unknown": -1}
    user_order = _tier_order.get(user_tier, -1)

    total = 0.0
    for poi in competitor_pois:
        d = poi.distance_m or 0.0
        decay = math.exp(-d / decay_lambda_m)
        comp_order = _tier_order.get(poi.tier_guess, -1)
        if comp_order == -1 or user_order == -1:
            # unknown tier → treat as adjacent
            tw = 0.5
        elif comp_order == user_order:
            tw = 1.0
        elif abs(comp_order - user_order) == 1:
            tw = 0.5
        else:
            tw = 0.2
        total += decay * tw
    return total


# ---------------------------------------------------------------------------
# F6 - Gap opportunity
# ---------------------------------------------------------------------------


def gap_opportunity(
    f1_raw: float,
    affluence_fit_val: float,
    supply_raw: float,
) -> float:
    """Raw gap opportunity (demand / (supply + 0.5)).

    Architecture formula::

        demand = F1_raw x affluence_fit
        gap    = pct( demand / (supply + 0.5) )

    This function returns the *pre-percentile* value; ``pct()`` is applied
    by the caller over all city cells.

    Parameters
    ----------
    f1_raw:
        Raw (un-normalised) anchor footfall for this cell.
    affluence_fit_val:
        Tier-fit score for this cell (0..1).
    supply_raw:
        Raw competition pressure (F5, before inversion).

    Returns
    -------
    float
        Pre-percentile gap value ≥ 0.
    """
    demand = f1_raw * affluence_fit_val
    return demand / (supply_raw + 0.5)


# ---------------------------------------------------------------------------
# F7 - Accessibility
# ---------------------------------------------------------------------------


@runtime_checkable
class AccessibilityInputs(Protocol):
    """Protocol for the inputs needed to compute F7."""

    road_class_score: float  # 0..1, higher = better road class
    main_road_distance_m: float  # metres to nearest main road
    transit_stops_in_catchment: int
    has_parking: bool


def accessibility(
    road_class_score: float,
    main_road_distance_m: float,
    transit_stops: int,
    has_parking: bool,
    max_transit_benefit: float = 5.0,
) -> float:
    """Composite accessibility score for one cell.

    Components:
    - Road class (0..1): 40 % weight.
    - Proximity to main road: 30 % weight; score decays with distance.
    - Transit density: 20 % weight; bounded at ``max_transit_benefit`` stops.
    - Parking presence: 10 % weight.

    Parameters
    ----------
    road_class_score:
        0..1 rating of the road class (e.g. primary=1.0, tertiary=0.5, track=0.1).
    main_road_distance_m:
        Distance in metres to the nearest main road.
    transit_stops:
        Count of transit stops within the catchment.
    has_parking:
        Whether parking is available within the catchment.
    max_transit_benefit:
        Number of stops at which the transit component saturates at 1.0.

    Returns
    -------
    float
        Accessibility score in [0, 1].
    """
    # Proximity score decays exponentially; at 500 m it is about 0.37
    road_dist_score = math.exp(-main_road_distance_m / 500.0)
    transit_score = min(transit_stops / max_transit_benefit, 1.0)
    parking_score = 1.0 if has_parking else 0.0

    val = (
        0.40 * road_class_score
        + 0.30 * road_dist_score
        + 0.20 * transit_score
        + 0.10 * parking_score
    )
    return max(0.0, min(1.0, val))


# ---------------------------------------------------------------------------
# F8 - Rent efficiency
# ---------------------------------------------------------------------------


def rent_efficiency(
    f1_norm: float,
    rent_norm: float,
) -> float:
    """Pre-percentile rent efficiency value.

    Architecture formula::

        rent_efficiency = pct( F1_norm / (rent_norm + 0.1) )

    This function returns the *un-percentiled* value.  Pass ``None`` to signal
    that no rent data exists; the caller should then omit F8 from the score.

    Parameters
    ----------
    f1_norm:
        Percentile-normalised anchor footfall (0..1).
    rent_norm:
        Percentile-normalised rent per sq ft (0..1).

    Returns
    -------
    float
        Pre-percentile efficiency value ≥ 0.
    """
    return f1_norm / (rent_norm + 0.1)


# ---------------------------------------------------------------------------
# F9 - Growth momentum
# ---------------------------------------------------------------------------


def growth_momentum(
    osm_growth_signal: float | None,
    curated_note_score: float | None,
    osm_weight: float = 0.7,
    note_weight: float = 0.3,
) -> tuple[float, bool]:
    """Growth momentum score for one cell.

    Returns a neutral value (0.5) when no data is available, and sets the
    ``estimated`` flag.

    Parameters
    ----------
    osm_growth_signal:
        Number of ``construction`` / ``proposed`` OSM features in catchment,
        already normalised to [0, 1] at the city level.  ``None`` if absent.
    curated_note_score:
        Score derived from the curated area notes file, in [0, 1].
        ``None`` if no notes exist for this cell.
    osm_weight, note_weight:
        Relative weights for the two signals.

    Returns
    -------
    (float, bool)
        ``(score, is_estimated)`` where ``score`` ∈ [0, 1] and
        ``is_estimated`` is ``True`` when the neutral fallback was used.
    """
    has_osm = osm_growth_signal is not None
    has_note = curated_note_score is not None

    if not has_osm and not has_note:
        return 0.5, True

    total_w = (osm_weight if has_osm else 0.0) + (note_weight if has_note else 0.0)
    val = 0.0
    if has_osm:
        val += osm_weight * osm_growth_signal  # type: ignore[operator]
    if has_note:
        val += note_weight * curated_note_score  # type: ignore[operator]

    return max(0.0, min(1.0, val / total_w)), False


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_score(
    poi_coverage: float,
    listing_coverage: float,
    recency: float,
    price_coverage: float,
) -> float:
    """Data confidence for one cell (architecture §5.7).

    Formula::

        0.4 x poi_coverage + 0.3 x listing_coverage + 0.2 x recency + 0.1 x price_coverage

    All inputs are in [0, 1].

    Parameters
    ----------
    poi_coverage:
        Fraction of expected POI types present in this cell's area.
    listing_coverage:
        Fraction of cells in the locality with at least one rent listing.
    recency:
        Data freshness score: 1.0 = very recent, 0.0 = stale.
    price_coverage:
        Fraction of cells with locality-level residential price data.

    Returns
    -------
    float
        Confidence in [0, 1].
    """
    val = 0.4 * poi_coverage + 0.3 * listing_coverage + 0.2 * recency + 0.1 * price_coverage
    return max(0.0, min(1.0, val))
