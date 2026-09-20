"""Pydantic schemas for analysis endpoints (architecture sections 10.2, 10.3)."""

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts import ZoneScore


class Answers(BaseModel):
    """User answers for category-specific questions."""

    model_config = ConfigDict(extra="allow")

    format: str | None = None
    target_customer: list[str] | None = None
    opening_hours: str | None = None


class Constraints(BaseModel):
    """Hard constraints for the analysis."""

    monthly_rent_budget_inr: float | None = Field(default=None, ge=0)
    shop_size_sqft: float | None = Field(default=None, gt=0)
    preferred_areas: list[str] = Field(default_factory=list)


class CreateAnalysisRequest(BaseModel):
    """Request payload to create a new analysis (10.2)."""

    city: str
    category: str
    tier: str
    answers: Answers = Field(default_factory=Answers)
    constraints: Constraints = Field(default_factory=Constraints)
    top_n: int = Field(10, ge=1, le=50)


class CreateAnalysisResponse(BaseModel):
    """Immediate response returning the queued job ID (10.2)."""

    analysis_id: str
    status: str = "queued"


class LatLon(BaseModel):
    """A geographic point."""

    lat: float
    lon: float


class NearbyListing(BaseModel):
    """A real-estate listing near a recommended zone."""

    title: str
    rent_inr_month: float
    url: str
    distance_m: float


class Recommendation(ZoneScore):
    """A fully enriched recommendation zone for the final output (10.3)."""

    centroid: LatLon | None = None
    nearby_listings: list[NearbyListing] = Field(default_factory=list)
    narrative: str | None = None


class RecommendationsResponse(BaseModel):
    """The final completed analysis result (10.3)."""

    analysis_id: str
    status: str
    category: str
    tier: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    data_notes: list[str] = Field(default_factory=list)


class CompareRequest(BaseModel):
    """Request payload to compare specific zones."""

    zone_h3_indices: list[str] = Field(..., min_length=2, max_length=3)


class WhatIfRequest(BaseModel):
    """Request payload to run a what-if scenario on an existing analysis."""

    category: str | None = None
    tier: str | None = None
    constraints: Constraints | None = None
