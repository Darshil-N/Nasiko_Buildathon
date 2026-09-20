"""
Shared Pydantic data contracts for SiteScout.

These models define the shapes that flow between the pipeline stages,
scoring library, backend API, and Nasiko agents.  Every boundary uses
one of these types so mypy can verify end-to-end correctness.

Units
-----
- distances:        metres (float)
- areas:            square feet (float)
- prices:           INR (int or float)
- fractions / fits: 0 .. 1 (float)
- scores:           0 .. 100 (float)
- H3 index:         text, resolution 9 (str)
- lat / lon:        WGS-84 decimal degrees (float)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enumerations and simple aliases
# ---------------------------------------------------------------------------

Category = Literal["cafe", "clothing", "pharmacy"]
Tier = Literal["budget", "mid", "premium"]
TierLabel = Literal["Lower class", "Medium class", "Niche"]

TIER_LABEL: dict[Tier, TierLabel] = {
    "budget": "Lower class",
    "mid": "Medium class",
    "premium": "Niche",
}
TIER_FROM_LABEL: dict[TierLabel, Tier] = {v: k for k, v in TIER_LABEL.items()}

LandUse = Literal["residential", "commercial", "mixed", "other"]
TierGuess = Literal["budget", "mid", "premium", "unknown"]
GeoSource = Literal["osm", "csv"]
GeoPrecision = Literal["exact", "locality"]
ListingType = Literal["rent", "sale"]
PropertyType = Literal["shop", "office", "showroom", "apartment", "plot"]
AnalysisStatus = Literal["queued", "running", "done", "failed"]


# ---------------------------------------------------------------------------
# Cell (H3 grid unit)
# ---------------------------------------------------------------------------


class CellRow(BaseModel):
    """One H3 resolution-9 cell as stored in the ``cells`` table."""

    h3_index: str = Field(..., description="H3 resolution-9 index string")
    city_id: int = Field(..., description="Foreign key to cities.id")
    centroid_lat: float = Field(..., ge=-90.0, le=90.0, description="WGS-84 latitude")
    centroid_lon: float = Field(..., ge=-180.0, le=180.0, description="WGS-84 longitude")
    locality_name: str | None = Field(None, description="OSM suburb name, if assigned")
    land_use: LandUse | None = Field(None, description="Majority land-use class")


# ---------------------------------------------------------------------------
# Point of Interest
# ---------------------------------------------------------------------------


class POIRow(BaseModel):
    """Normalised POI as stored in the ``pois`` table.

    ``distance_m`` is populated at query time (distance from cell centroid to
    the POI); it is ``None`` when the POI is stored without a reference cell.
    """

    osm_type: str | None = Field(None, description="'node' | 'way' | 'relation'")
    osm_id: int | None = Field(None, description="OSM element id")
    city_id: int
    category: str = Field(..., description="Normalised internal category, e.g. 'college'")
    name: str | None = None
    brand: str | None = None
    tier_guess: TierGuess = Field("unknown", description="Estimated tier for competitor POIs")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    h3_index: str | None = Field(None, description="Cell this POI belongs to")
    source: GeoSource = "osm"
    # Populated at scoring time, not stored
    distance_m: float | None = Field(
        None,
        ge=0.0,
        description="Distance in metres from a reference cell centroid",
    )


# ---------------------------------------------------------------------------
# Commercial listing (from optional rent CSV)
# ---------------------------------------------------------------------------


class ListingRow(BaseModel):
    """One commercial listing from the optional rent CSV.

    ``price_per_sqft`` is computed from ``price_inr / area_sqft`` if the
    field is not provided directly.
    """

    city_id: int
    source: str = Field(..., description="Originating source tag, e.g. '99acres'")
    listing_type: ListingType
    property_type: PropertyType
    price_inr: float = Field(..., gt=0.0, description="Asking price in INR")
    price_period: Literal["month", "total"]
    area_sqft: float = Field(..., gt=0.0, description="Gross area in square feet")
    price_per_sqft: float | None = Field(
        None, gt=0.0, description="INR per sq ft (computed if absent)"
    )
    locality: str = Field(..., description="Locality / neighbourhood name")
    address_text: str | None = None
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lon: float | None = Field(None, ge=-180.0, le=180.0)
    geo_precision: GeoPrecision | None = None
    h3_index: str | None = None
    posted_date: str | None = Field(None, description="ISO date YYYY-MM-DD")
    source_note: str | None = None

    @model_validator(mode="after")
    def _compute_price_per_sqft(self) -> ListingRow:
        if self.price_per_sqft is None and self.area_sqft > 0:
            self.price_per_sqft = self.price_inr / self.area_sqft
        return self


# ---------------------------------------------------------------------------
# Market intelligence signal
# ---------------------------------------------------------------------------


class MarketIntelRow(BaseModel):
    """One market-intelligence entry (OSM growth signal or curated note)."""

    city_id: int
    category: str | None = Field(
        None,
        description="'clothing' | 'cafe' | 'pharmacy' | 'general'",
    )
    topic: str = Field(..., description="'market_reputation' | 'growth_news'")
    summary: str = Field(..., description="Human-readable cited summary")
    sources: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {'title': ..., 'url': ...} dicts",
    )
    locality_mentions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cell features (output of the feature build pipeline)
# ---------------------------------------------------------------------------


class RawFeatures(BaseModel):
    """Raw (un-normalised) feature values before percentile ranking.

    All numeric fields are in their natural units.  ``None`` means the feature
    could not be computed for this cell (e.g. no rent data for F8).
    """

    F1_anchor_footfall_raw: float = Field(
        ..., ge=0.0, description="Weighted landmark sum (no unit, city-relative)"
    )
    F3_residential_demand_raw: float = Field(
        ..., ge=0.0, description="Population or building density proxy"
    )
    F4_retail_cluster_raw: float = Field(
        ..., ge=0.0, description="Same-category and complementary shop density"
    )
    F5_competition_pressure_raw: float = Field(
        ..., ge=0.0, description="Distance-weighted same-category competitor count"
    )
    F7_accessibility_raw: float = Field(
        ..., ge=0.0, le=1.0, description="Road/transit composite (0..1, higher = better)"
    )
    F8_rent_efficiency_raw: float | None = Field(
        None, description="F1_raw / rent_per_sqft_norm; None when no rent data"
    )
    F9_growth_momentum_raw: float = Field(
        ..., ge=0.0, le=1.0, description="OSM growth signal (0..1); 0.5 = neutral"
    )
    premium_poi_density_raw: float = Field(
        ..., ge=0.0, description="Count of premium POIs in catchment"
    )
    apartment_share_raw: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of buildings that are apartments"
    )
    resi_price_per_sqft: float | None = Field(
        None, gt=0.0, description="Median residential sale price per sq ft (INR)"
    )
    resi_rent_per_sqft: float | None = Field(
        None, gt=0.0, description="Median residential rent per sq ft per month (INR)"
    )


class NormalisedFeatures(BaseModel):
    """Percentile-normalised features, all in [0, 1].

    F5 is stored *after* inversion (higher = less competition = better) so that
    every ``F*_norm`` field follows the convention that higher is better.
    """

    F1_anchor_footfall_norm: float = Field(..., ge=0.0, le=1.0)
    F2_affluence_fit_norm: float = Field(..., ge=0.0, le=1.0)
    F3_residential_demand_norm: float = Field(..., ge=0.0, le=1.0)
    F4_retail_cluster_norm: float = Field(..., ge=0.0, le=1.0)
    F5_competition_inverted_norm: float = Field(..., ge=0.0, le=1.0)
    F6_gap_opportunity_norm: float = Field(..., ge=0.0, le=1.0)
    F7_accessibility_norm: float = Field(..., ge=0.0, le=1.0)
    F8_rent_efficiency_norm: float | None = Field(None, ge=0.0, le=1.0)
    F9_growth_momentum_norm: float = Field(..., ge=0.0, le=1.0)


class CellFeatures(BaseModel):
    """Full feature record for one cell, output of the feature-build pipeline.

    This is the primary contract between the pipeline (Agent A territory) and
    the scoring library (Agent B territory).  Agent A writes these rows;
    Agent B reads them.
    """

    h3_index: str
    city_id: int
    feature_version: int = Field(1, ge=1)
    raw: RawFeatures
    normalised: NormalisedFeatures
    affluence: float = Field(..., ge=0.0, le=1.0, description="Affluence index (0..1)")
    rent_per_sqft_est: float | None = Field(
        None, gt=0.0, description="Estimated commercial rent per sq ft per month (INR)"
    )
    rent_is_estimated: bool = Field(
        True,
        description="True when rent is a k-ring IDW estimate rather than from direct listings",
    )
    # Confidence inputs (each 0..1)
    poi_coverage: float = Field(..., ge=0.0, le=1.0)
    listing_coverage: float = Field(0.0, ge=0.0, le=1.0)
    recency: float = Field(..., ge=0.0, le=1.0, description="Data freshness score")
    price_coverage: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Scoring outputs
# ---------------------------------------------------------------------------


class ZoneScore(BaseModel):
    """Score and explanation for one ranked zone (cell or merged cluster)."""

    h3_index: str
    zone_name: str | None = Field(
        None, description="Human-readable name like 'Koramangala (north)'"
    )
    rank: int = Field(..., ge=1)
    score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score 0..100")
    confidence: float = Field(..., ge=0.0, le=1.0)
    contributions: dict[str, float] = Field(
        ...,
        description=(
            "Per-feature contribution: {'F1_anchor_footfall': 21.3, ...}. Sum equals score."
        ),
    )
    top_drivers: list[str] = Field(
        ..., max_length=3, description="Up to 3 human-readable positive driver strings"
    )
    top_risks: list[str] = Field(
        ..., max_length=2, description="Up to 2 human-readable risk strings"
    )
    excluded: bool = Field(False, description="True when the cell failed a hard filter")
    exclusion_reason: str | None = None
    greyed: bool = Field(False, description="True when confidence < min_confidence_ranked")

    @model_validator(mode="after")
    def _validate_contributions_sum(self) -> ZoneScore:
        total = round(sum(self.contributions.values()), 6)
        # Allow small floating-point drift (up to 0.1 points)
        if abs(total - self.score) > 0.1:
            raise ValueError(f"contributions sum {total:.4f} does not match score {self.score:.4f}")
        return self


class RankingResult(BaseModel):
    """Full ranked output for one analysis request."""

    analysis_id: str
    city_id: int
    category: Category
    tier: Tier
    config_version: str
    ranked_zones: list[ZoneScore] = Field(default_factory=list)
    no_candidates: bool = False
    cheapest_fallback: list[ZoneScore] | None = Field(
        None,
        description="Three cheapest zones shown when no_candidates is True and rent data exists",
    )
    data_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent response envelope (§9.4)
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """Standard wrapper every Nasiko agent must include in its response."""

    agent: str = Field(..., description="Agent name, e.g. 'scoring'")
    version: str = Field(..., description="Semantic version, e.g. '0.1.0'")
    latency_ms: int = Field(..., ge=0)
    warnings: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(
        default_factory=dict, description="Agent-specific response body"
    )
