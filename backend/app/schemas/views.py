"""Response shapes added by the backend beyond the core analysis schemas (architecture 10.1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.analyses import Recommendation


class TierOut(BaseModel):
    """One store tier the user can choose."""

    id: str
    label: str
    target_affluence: float


class CategoryOut(BaseModel):
    """A category with its tiers and wizard questions."""

    key: str
    label: str
    tiers: list[TierOut]
    questions: list[dict[str, Any]]


class CategoriesOut(BaseModel):
    """GET /categories."""

    categories: list[CategoryOut]


class AnalysisError(BaseModel):
    """Why an analysis failed."""

    code: str
    message: str


class AnalysisStatusResponse(BaseModel):
    """GET /analyses/{id}: status, plus the results once the analysis is done."""

    analysis_id: str
    status: str
    city: str
    category: str
    tier: str
    summary: str | None = None
    error: AnalysisError | None = None
    created_at: str | None = None
    finished_at: str | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    data_notes: list[str] = Field(default_factory=list)


class AnalysisListItemOut(BaseModel):
    """One row of the user's analysis history."""

    analysis_id: str
    city: str
    category: str
    tier: str
    status: str
    created_at: str | None
    top_zone: str | None


class AnalysesOut(BaseModel):
    """GET /analyses."""

    analyses: list[AnalysisListItemOut]


class Landmark(BaseModel):
    """A point of interest near a zone."""

    category: str
    name: str | None
    brand: str | None
    distance_m: float


class ZoneDetailResponse(BaseModel):
    """GET /analyses/{id}/zones/{rank}."""

    analysis_id: str
    recommendation: Recommendation
    landmarks: list[Landmark]
    data_notes: list[str]


class MapCell(BaseModel):
    """One scored cell for the map (rank is empty for greyed or excluded cells)."""

    h3_index: str
    rank: int | None
    score: float
    greyed: bool
    excluded: bool


class CellsResponse(BaseModel):
    """GET /analyses/{id}/cells."""

    analysis_id: str
    cells: list[MapCell]


class CompareResponse(BaseModel):
    """POST /analyses/{id}/compare."""

    analysis_id: str
    zones: list[Recommendation]
    feature_leaders: dict[str, str] = Field(
        description="For each score component, the h3_index of the zone contributing the most."
    )


class RankChange(BaseModel):
    """How one zone moved in a what-if scenario."""

    h3_index: str
    zone_name: str
    from_rank: int | None
    to_rank: int


class WhatIfResponse(BaseModel):
    """POST /analyses/{id}/what-if."""

    analysis_id: str
    category: str
    tier: str
    recommendations: list[Recommendation]
    rank_changes: list[RankChange]
    data_notes: list[str]
