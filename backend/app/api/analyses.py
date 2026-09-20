"""Analysis endpoints (architecture section 10): create, poll, results, zone detail, map, compare,
what-if, history, plus the category list for the wizard.

Scoring all cells takes well under a second, so the map, compare and what-if endpoints simply score
again from the stored features; nothing beyond ``analyses`` and ``recommendations`` is written.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from backend.app.api.deps import ReadStore, UserId, WriteStore
from backend.app.core.auth import require_api_key
from backend.app.core.errors import AppError, ErrorCode
from backend.app.schemas.analyses import (
    CompareRequest,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    LatLon,
    Recommendation,
    RecommendationsResponse,
    WhatIfRequest,
)
from backend.app.schemas.views import (
    AnalysesOut,
    AnalysisError,
    AnalysisListItemOut,
    AnalysisStatusResponse,
    CategoriesOut,
    CategoryOut,
    CellsResponse,
    CompareResponse,
    Landmark,
    MapCell,
    RankChange,
    TierOut,
    WhatIfResponse,
    ZoneDetailResponse,
)
from backend.app.services.analysis_service import (
    DEFAULT_TOP_N,
    AnalysisRecord,
    CellMeta,
    StoredZone,
    compute_outcome,
    data_notes,
    make_narrative,
    new_analysis_id,
    rank_changes,
    run_analysis,
    to_stored_zones,
    zone_names,
)
from backend.app.services.questionnaire import questions_for
from shared.config import CategoryConfig, list_available_categories, load_category_config
from shared.contracts import ZoneScore

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])

LOCAL_USER = "local"
LANDMARK_RADIUS_M = 500.0
LANDMARK_LIMIT = 25
CATEGORY_LABELS = {"cafe": "Cafe", "clothing": "Clothing store", "pharmacy": "Pharmacy"}


# --- helpers ---------------------------------------------------------------------------------
def _not_found(what: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, f"{what} was not found.")


def _config(category: str) -> CategoryConfig:
    """Load a category's config or answer with a clear input error."""
    if category not in list_available_categories():
        raise AppError(ErrorCode.INVALID_INPUT, f"Unknown category {category!r}.")
    return load_category_config(category)


def _require_record(store: ReadStore, analysis_id: str) -> AnalysisRecord:
    record = store.load_analysis(analysis_id)
    if record is None:
        raise _not_found("Analysis")
    return record


def _city_name(store: ReadStore, city_key: str) -> str:
    city = store.get_city(city_key)
    return city.name if city else city_key


def _recommendation(zone: StoredZone, meta: dict[str, CellMeta]) -> Recommendation:
    cell = meta.get(zone.h3_index)
    return Recommendation(
        h3_index=zone.h3_index,
        zone_name=zone.zone_name,
        rank=zone.rank,
        score=zone.score,
        confidence=zone.confidence,
        contributions=zone.contributions,
        top_drivers=zone.top_drivers,
        top_risks=zone.top_risks,
        centroid=LatLon(lat=cell.lat, lon=cell.lon) if cell else None,
        nearby_listings=[],
        narrative=zone.narrative,
    )


def _recommendations(
    store: ReadStore, zones: Sequence[StoredZone]
) -> tuple[list[Recommendation], dict[str, CellMeta]]:
    meta = store.cell_meta_for([z.h3_index for z in zones])
    return [_recommendation(z, meta) for z in zones], meta


def _error_for(record: AnalysisRecord) -> AnalysisError | None:
    """Turn a failed analysis's stored message into a structured error."""
    if record.status != "failed":
        return None
    message = record.summary_narrative or "The analysis could not be completed."
    code, _, rest = message.partition(": ")
    if code == ErrorCode.NO_CANDIDATES.value and rest:
        return AnalysisError(code=code, message=rest)
    return AnalysisError(code=ErrorCode.INTERNAL.value, message=message)


def _stored_from_scores(
    zones: Sequence[ZoneScore],
    meta: dict[str, CellMeta],
    *,
    city_name: str,
    category: str,
    tier_label: str,
    name_hints: dict[str, str] | None = None,
) -> list[StoredZone]:
    """Name and narrate scored zones (used for compare and what-if results)."""
    names = zone_names(zones, meta)
    if name_hints:
        names.update({h: n for h, n in name_hints.items() if h in names})
    return [
        StoredZone(
            rank=z.rank,
            h3_index=z.h3_index,
            zone_name=names[z.h3_index],
            score=z.score,
            confidence=z.confidence,
            contributions=dict(z.contributions),
            top_drivers=list(z.top_drivers),
            top_risks=list(z.top_risks),
            narrative=make_narrative(z, names[z.h3_index], city_name, category, tier_label),
        )
        for z in zones
    ]


def _run_in_background(request: Request, analysis_id: str, city_name: str) -> None:
    """Runs after the response is sent, with its own writable store."""
    with request.app.state.open_store(True) as store:
        run_analysis(store, analysis_id, city_name=city_name)


# --- categories ------------------------------------------------------------------------------
@router.get("/categories", response_model=CategoriesOut, summary="Categories, tiers and questions")
def categories() -> CategoriesOut:
    """What the wizard needs: each category's tiers (with labels) and its questions."""
    items = []
    for key in list_available_categories():
        config = load_category_config(key)
        items.append(
            CategoryOut(
                key=key,
                label=CATEGORY_LABELS.get(key, key.title()),
                tiers=[
                    TierOut(id=t, label=config.tier_labels[t], target_affluence=target)
                    for t, target in config.tier_targets.items()
                ],
                questions=questions_for(key),
            )
        )
    return CategoriesOut(categories=items)


# --- create and read -------------------------------------------------------------------------
@router.post(
    "/analyses",
    response_model=CreateAnalysisResponse,
    status_code=202,
    summary="Create an analysis (returns immediately)",
)
def create_analysis(
    body: CreateAnalysisRequest,
    request: Request,
    background: BackgroundTasks,
    store: WriteStore,
    user_id: UserId,
) -> CreateAnalysisResponse:
    """Validate the request, store it as queued, and score in the background."""
    city = store.get_city(body.city)
    if city is None:
        raise AppError(ErrorCode.INVALID_INPUT, f"Unknown city {body.city!r}.")
    if city.status != "ready":
        raise AppError(ErrorCode.CITY_NOT_READY, f"{city.name} is not ready for analysis yet.")
    config = _config(body.category)
    if body.tier not in config.tier_labels:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            f"Tier {body.tier!r} is not offered for {body.category}; "
            f"choose one of {sorted(config.tier_labels)}.",
        )
    constraints: dict[str, Any] = body.constraints.model_dump(exclude_none=True)
    constraints["top_n"] = body.top_n
    analysis_id = new_analysis_id()
    store.create_analysis(
        analysis_id,
        user_id=store.upsert_user(user_id or LOCAL_USER),
        city_id=city.id,
        category=body.category,
        tier=body.tier,
        answers=body.answers.model_dump(exclude_none=True),
        constraints=constraints,
    )
    background.add_task(_run_in_background, request, analysis_id, city.name)
    return CreateAnalysisResponse(analysis_id=analysis_id, status="queued")


@router.get("/analyses", response_model=AnalysesOut, summary="The user's past analyses")
def list_analyses(
    store: ReadStore, user_id: UserId, limit: int = Query(50, ge=1, le=200)
) -> AnalysesOut:
    rows = store.list_analyses(user_id or LOCAL_USER, limit)
    return AnalysesOut(
        analyses=[
            AnalysisListItemOut(
                analysis_id=r.id,
                city=r.city_key,
                category=r.category,
                tier=r.tier,
                status=r.status,
                created_at=r.created_at,
                top_zone=r.top_zone,
            )
            for r in rows
        ]
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisStatusResponse,
    summary="Status, and the results once done",
)
def get_analysis(analysis_id: str, store: ReadStore) -> AnalysisStatusResponse:
    record = _require_record(store, analysis_id)
    recommendations: list[Recommendation] = []
    notes: list[str] = []
    if record.status == "done":
        recommendations, _ = _recommendations(store, store.load_recommendations(analysis_id))
        notes = data_notes(_city_name(store, record.city_key))
    return AnalysisStatusResponse(
        analysis_id=record.id,
        status=record.status,
        city=record.city_key,
        category=record.category,
        tier=record.tier,
        summary=record.summary_narrative if record.status == "done" else None,
        error=_error_for(record),
        created_at=record.created_at.isoformat() if record.created_at else None,
        finished_at=record.finished_at.isoformat() if record.finished_at else None,
        recommendations=recommendations,
        data_notes=notes,
    )


@router.get(
    "/analyses/{analysis_id}/recommendations",
    response_model=None,  # a RecommendationsResponse, or a GeoJSON collection with format=geojson
    summary="Ranked zones with their breakdown (format=geojson for a map layer)",
)
def get_recommendations(
    analysis_id: str,
    store: ReadStore,
    format: Literal["json", "geojson"] = "json",
) -> RecommendationsResponse | dict[str, Any]:
    record = _require_record(store, analysis_id)
    zones = store.load_recommendations(analysis_id) if record.status == "done" else []
    recommendations, _ = _recommendations(store, zones)
    if format == "geojson":
        polygons = store.cell_polygons([z.h3_index for z in zones])
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": polygons.get(r.h3_index),
                    "properties": {
                        "rank": r.rank,
                        "zone_name": r.zone_name,
                        "h3_index": r.h3_index,
                        "score": r.score,
                        "confidence": r.confidence,
                    },
                }
                for r in recommendations
            ],
        }
    return RecommendationsResponse(
        analysis_id=record.id,
        status=record.status,
        category=record.category,
        tier=record.tier,
        recommendations=recommendations,
        data_notes=data_notes(_city_name(store, record.city_key)) if zones else [],
    )


@router.get(
    "/analyses/{analysis_id}/zones/{rank}",
    response_model=ZoneDetailResponse,
    summary="Full detail for one ranked zone",
)
def get_zone(analysis_id: str, rank: int, store: ReadStore) -> ZoneDetailResponse:
    record = _require_record(store, analysis_id)
    zone = next((z for z in store.load_recommendations(analysis_id) if z.rank == rank), None)
    if record.status != "done" or zone is None:
        raise _not_found(f"Zone ranked {rank}")
    recommendations, meta = _recommendations(store, [zone])
    cell = meta.get(zone.h3_index)
    landmarks = (
        [
            Landmark(category=p.category, name=p.name, brand=p.brand, distance_m=p.distance_m)
            for p in store.nearby_pois(cell.lat, cell.lon, LANDMARK_RADIUS_M, LANDMARK_LIMIT)
        ]
        if cell
        else []
    )
    return ZoneDetailResponse(
        analysis_id=record.id,
        recommendation=recommendations[0],
        landmarks=landmarks,
        data_notes=data_notes(_city_name(store, record.city_key)),
    )


@router.get(
    "/analyses/{analysis_id}/cells",
    response_model=CellsResponse,
    summary="Every scored cell (for a heat map)",
)
def get_cells(analysis_id: str, store: ReadStore) -> CellsResponse:
    record = _require_record(store, analysis_id)
    if record.status != "done":
        raise _not_found("Scored cells")
    outcome, _, _ = compute_outcome(store, record)
    return CellsResponse(
        analysis_id=record.id,
        cells=[
            MapCell(
                h3_index=z.h3_index,
                rank=None if z.excluded or z.greyed else z.rank,
                score=z.score,
                greyed=z.greyed,
                excluded=z.excluded,
            )
            for z in outcome.zones
        ],
    )


# --- compare and what-if ---------------------------------------------------------------------
@router.post(
    "/analyses/{analysis_id}/compare",
    response_model=CompareResponse,
    summary="Compare two or three zones side by side",
)
def compare(analysis_id: str, body: CompareRequest, store: ReadStore) -> CompareResponse:
    record = _require_record(store, analysis_id)
    if record.status != "done":
        raise _not_found("Scored zones")
    wanted = list(dict.fromkeys(body.zone_h3_indices))
    if len(wanted) < 2:
        raise AppError(ErrorCode.INVALID_INPUT, "Choose two or three different zones to compare.")
    outcome, config, meta = compute_outcome(store, record)
    by_index = {z.h3_index: z for z in outcome.zones}
    missing = [h for h in wanted if h not in by_index]
    if missing:
        raise AppError(ErrorCode.INVALID_INPUT, f"Unknown zone {missing[0]!r} for this city.")
    hints = {z.h3_index: z.zone_name for z in store.load_recommendations(analysis_id)}
    stored = _stored_from_scores(
        [by_index[h] for h in wanted],
        meta,
        city_name=_city_name(store, record.city_key),
        category=record.category,
        tier_label=config.tier_labels.get(record.tier, record.tier),
        name_hints=hints,
    )
    zones, _ = _recommendations(store, stored)
    leaders: dict[str, str] = {}
    for key in sorted({k for z in zones for k in z.contributions}):
        leaders[key] = max(zones, key=lambda z: z.contributions.get(key, 0.0)).h3_index
    return CompareResponse(analysis_id=record.id, zones=zones, feature_leaders=leaders)


@router.post(
    "/analyses/{analysis_id}/what-if",
    response_model=WhatIfResponse,
    summary="Re-score with a different tier, category or constraints",
)
def what_if(analysis_id: str, body: WhatIfRequest, store: ReadStore) -> WhatIfResponse:
    record = _require_record(store, analysis_id)
    if record.status != "done":
        raise _not_found("Scored zones")
    category = body.category or record.category
    config = _config(category)
    tier = body.tier or record.tier
    if tier not in config.tier_labels:
        raise AppError(ErrorCode.INVALID_INPUT, f"Tier {tier!r} is not offered for {category}.")
    overrides = (
        body.constraints.model_dump(exclude_unset=True, exclude_none=True)
        if body.constraints
        else {}
    )
    baseline, _, _ = compute_outcome(store, record)
    outcome, config, meta = compute_outcome(
        store, record, category=category, tier=tier, constraints=overrides
    )
    city_name = _city_name(store, record.city_key)
    top_n = int(record.constraints.get("top_n", DEFAULT_TOP_N))
    stored = to_stored_zones(
        outcome,
        meta,
        top_n=top_n,
        city_name=city_name,
        category=category,
        tier_label=config.tier_labels.get(tier, tier),
    )
    if not stored:
        raise AppError(
            ErrorCode.NO_CANDIDATES, "No zone passes these constraints. Loosen them and retry."
        )
    recommendations, _ = _recommendations(store, stored)
    return WhatIfResponse(
        analysis_id=record.id,
        category=category,
        tier=tier,
        recommendations=recommendations,
        rank_changes=[
            RankChange(**c) for c in rank_changes(baseline.zones, outcome.zones, meta, top_n)
        ],
        data_notes=data_notes(city_name, outcome.notes),
    )
