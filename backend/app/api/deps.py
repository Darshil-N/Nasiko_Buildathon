"""Shared API dependencies: storage access (read-only by default) and the end user's id."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Annotated, Any, Protocol

from fastapi import Depends, Request

from backend.app.core.auth import current_user_id
from backend.app.db.analysis_store import AnalysisListItem, CityInfo, NearbyPoi
from backend.app.services.analysis_service import AnalysisRecord, CellMeta, StoredZone
from pipelines.features_store import FeatureBundle


class ApiStore(Protocol):
    """Everything the endpoints use from storage (SQL in production, memory in tests)."""

    def get_city(self, key: str) -> CityInfo | None: ...
    def list_cities(self) -> list[CityInfo]: ...
    def cell_meta(self, city_id: int) -> dict[str, CellMeta]: ...
    def cell_meta_for(self, h3_indexes: Sequence[str]) -> dict[str, CellMeta]: ...
    def cell_polygons(self, h3_indexes: Sequence[str]) -> dict[str, dict[str, Any]]: ...
    def nearby_pois(
        self, lat: float, lon: float, radius_m: float, limit: int
    ) -> list[NearbyPoi]: ...
    def tier_bundles(self, category: str, tier: str) -> list[FeatureBundle]: ...
    def upsert_user(self, external_id: str) -> int: ...
    def create_analysis(
        self,
        analysis_id: str,
        *,
        user_id: int | None,
        city_id: int,
        category: str,
        tier: str,
        answers: dict[str, Any],
        constraints: dict[str, Any],
    ) -> None: ...
    def set_status(
        self,
        analysis_id: str,
        status: str,
        *,
        narrative: str | None = None,
        config_version: str | None = None,
    ) -> None: ...
    def save_recommendations(self, analysis_id: str, zones: Sequence[StoredZone]) -> None: ...
    def load_analysis(self, analysis_id: str) -> AnalysisRecord | None: ...
    def load_recommendations(self, analysis_id: str) -> list[StoredZone]: ...
    def list_analyses(self, external_user_id: str, limit: int = 50) -> list[AnalysisListItem]: ...


def read_store(request: Request) -> Iterator[ApiStore]:
    """A READ ONLY store for one request."""
    with request.app.state.open_store(False) as store:
        yield store


def write_store(request: Request) -> Iterator[ApiStore]:
    """A store that may write. Used only by endpoints that create analyses."""
    with request.app.state.open_store(True) as store:
        yield store


ReadStore = Annotated[ApiStore, Depends(read_store)]
WriteStore = Annotated[ApiStore, Depends(write_store)]
UserId = Annotated[str | None, Depends(current_user_id)]
