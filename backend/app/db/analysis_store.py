"""SQL storage for analyses (plan steps 4.2.2, 4.5).

Writes touch only ``users``, ``analyses`` and ``recommendations``. Read paths are opened in READ
ONLY sessions by ``open_store``; a write session is requested explicitly and only by the
endpoints that create or update an analysis.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.settings import Settings
from backend.app.db.session import get_engine
from backend.app.services.analysis_service import AnalysisRecord, CellMeta, StoredZone
from pipelines.features_store import FeatureBundle, load_tier_bundle


@dataclass(frozen=True)
class CityInfo:
    """A city row."""

    id: int
    key: str
    name: str
    state: str | None
    country: str
    status: str


@dataclass(frozen=True)
class AnalysisListItem:
    """One row of a user's analysis list."""

    id: str
    city_key: str
    category: str
    tier: str
    status: str
    created_at: str | None
    top_zone: str | None


@dataclass(frozen=True)
class NearbyPoi:
    """A point of interest near a zone."""

    category: str
    name: str | None
    brand: str | None
    distance_m: float


class SqlAnalysisStore:
    """Implements ``AnalysisStore`` and the extra queries the API needs, over one session."""

    def __init__(self, session: Session) -> None:
        self._s = session

    # --- cities and cells ------------------------------------------------------------------
    def get_city(self, key: str) -> CityInfo | None:
        row = self._s.execute(
            text("SELECT id, key, name, state, country, status FROM cities WHERE key = :key"),
            {"key": key},
        ).first()
        return None if row is None else CityInfo(*row)

    def list_cities(self) -> list[CityInfo]:
        rows = self._s.execute(
            text("SELECT id, key, name, state, country, status FROM cities ORDER BY name")
        ).all()
        return [CityInfo(*r) for r in rows]

    def cell_meta(self, city_id: int) -> dict[str, CellMeta]:
        rows = self._s.execute(
            text(
                "SELECT h3_index, locality_name, land_use, ST_Y(centroid) AS lat, "
                "ST_X(centroid) AS lon FROM cells WHERE city_id = :city_id"
            ),
            {"city_id": city_id},
        ).all()
        return {
            r.h3_index: CellMeta(r.h3_index, r.locality_name, r.land_use, r.lat, r.lon)
            for r in rows
        }

    def cell_meta_for(self, h3_indexes: Sequence[str]) -> dict[str, CellMeta]:
        rows = self._s.execute(
            text(
                "SELECT h3_index, locality_name, land_use, ST_Y(centroid) AS lat, "
                "ST_X(centroid) AS lon FROM cells WHERE h3_index = ANY(:ids)"
            ),
            {"ids": list(h3_indexes)},
        ).all()
        return {
            r.h3_index: CellMeta(r.h3_index, r.locality_name, r.land_use, r.lat, r.lon)
            for r in rows
        }

    def cell_polygons(self, h3_indexes: Sequence[str]) -> dict[str, dict[str, Any]]:
        rows = self._s.execute(
            text(
                "SELECT h3_index, ST_AsGeoJSON(boundary) AS geometry FROM cells "
                "WHERE h3_index = ANY(:ids)"
            ),
            {"ids": list(h3_indexes)},
        ).all()
        return {r.h3_index: json.loads(r.geometry) for r in rows}

    def nearby_pois(self, lat: float, lon: float, radius_m: float, limit: int) -> list[NearbyPoi]:
        rows = self._s.execute(
            text(
                """
                WITH here AS (SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography AS g)
                SELECT category, name, brand, ST_Distance(location::geography, here.g) AS distance_m
                FROM pois, here
                WHERE ST_DWithin(location::geography, here.g, :radius)
                ORDER BY distance_m LIMIT :limit
                """
            ),
            {"lat": lat, "lon": lon, "radius": radius_m, "limit": limit},
        ).all()
        return [NearbyPoi(r.category, r.name, r.brand, round(float(r.distance_m), 1)) for r in rows]

    # --- features --------------------------------------------------------------------------
    def tier_bundles(self, category: str, tier: str) -> list[FeatureBundle]:
        return load_tier_bundle(self._s, category, tier)

    # --- analyses (writes) -----------------------------------------------------------------
    def upsert_user(self, external_id: str) -> int:
        row = self._s.execute(
            text(
                "INSERT INTO users (external_id) VALUES (:ext) "
                "ON CONFLICT (external_id) DO UPDATE SET external_id = EXCLUDED.external_id "
                "RETURNING id"
            ),
            {"ext": external_id},
        ).one()
        self._s.commit()
        return int(row.id)

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
    ) -> None:
        self._s.execute(
            text(
                "INSERT INTO analyses (id, user_id, city_id, category, tier, answers, "
                "constraints, status) "
                "VALUES (:id, :user_id, :city_id, :category, :tier, CAST(:answers AS JSONB), "
                "CAST(:constraints AS JSONB), 'queued')"
            ),
            {
                "id": analysis_id,
                "user_id": user_id,
                "city_id": city_id,
                "category": category,
                "tier": tier,
                "answers": json.dumps(answers),
                "constraints": json.dumps(constraints),
            },
        )
        self._s.commit()

    def set_status(
        self,
        analysis_id: str,
        status: str,
        *,
        narrative: str | None = None,
        config_version: str | None = None,
    ) -> None:
        self._s.execute(
            text(
                "UPDATE analyses SET status = :status, "
                "summary_narrative = COALESCE(:narrative, summary_narrative), "
                "config_version = COALESCE(:config_version, config_version), "
                "finished_at = CASE WHEN :status IN ('done', 'failed') THEN now() "
                "ELSE finished_at END "
                "WHERE id = :id"
            ),
            {
                "id": analysis_id,
                "status": status,
                "narrative": narrative,
                "config_version": config_version,
            },
        )
        self._s.commit()

    def save_recommendations(self, analysis_id: str, zones: Sequence[StoredZone]) -> None:
        self._s.execute(
            text("DELETE FROM recommendations WHERE analysis_id = :id"), {"id": analysis_id}
        )
        rows = [
            {
                "analysis_id": analysis_id,
                "rank": z.rank,
                "h3_index": z.h3_index,
                "zone_name": z.zone_name,
                "score": z.score,
                "confidence": z.confidence,
                "contributions": json.dumps(z.contributions),
                "top_drivers": json.dumps(z.top_drivers),
                "top_risks": json.dumps(z.top_risks),
                "narrative": z.narrative,
            }
            for z in zones
        ]
        if rows:
            self._s.execute(
                text(
                    "INSERT INTO recommendations (analysis_id, rank, h3_index, zone_name, score, "
                    "confidence, contributions, top_drivers, top_risks, narrative) "
                    "VALUES (:analysis_id, :rank, :h3_index, :zone_name, :score, :confidence, "
                    "CAST(:contributions AS JSONB), CAST(:top_drivers AS JSONB), "
                    "CAST(:top_risks AS JSONB), :narrative)"
                ),
                rows,
            )
        self._s.commit()

    # --- analyses (reads) ------------------------------------------------------------------
    def load_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        row = self._s.execute(
            text(
                "SELECT a.id, a.city_id, c.key AS city_key, a.category, a.tier, a.answers, "
                "a.constraints, a.config_version, a.status, a.summary_narrative, a.created_at, "
                "a.finished_at FROM analyses a JOIN cities c ON c.id = a.city_id WHERE a.id = :id"
            ),
            {"id": analysis_id},
        ).first()
        if row is None:
            return None
        return AnalysisRecord(
            id=row.id,
            city_id=row.city_id,
            city_key=row.city_key,
            category=row.category,
            tier=row.tier,
            answers=dict(row.answers or {}),
            constraints=dict(row.constraints or {}),
            config_version=row.config_version,
            status=row.status,
            summary_narrative=row.summary_narrative,
            created_at=row.created_at,
            finished_at=row.finished_at,
        )

    def load_recommendations(self, analysis_id: str) -> list[StoredZone]:
        rows = self._s.execute(
            text(
                "SELECT rank, h3_index, zone_name, score, confidence, contributions, top_drivers, "
                "top_risks, narrative FROM recommendations WHERE analysis_id = :id ORDER BY rank"
            ),
            {"id": analysis_id},
        ).all()
        return [
            StoredZone(
                rank=r.rank,
                h3_index=r.h3_index,
                zone_name=r.zone_name,
                score=float(r.score),
                confidence=float(r.confidence),
                contributions={k: float(v) for k, v in (r.contributions or {}).items()},
                top_drivers=list(r.top_drivers or []),
                top_risks=list(r.top_risks or []),
                narrative=r.narrative,
            )
            for r in rows
        ]

    def list_analyses(self, external_user_id: str, limit: int = 50) -> list[AnalysisListItem]:
        rows = self._s.execute(
            text(
                "SELECT a.id, c.key AS city_key, a.category, a.tier, a.status, a.created_at, "
                "(SELECT zone_name FROM recommendations r "
                "WHERE r.analysis_id = a.id AND r.rank = 1) "
                "AS top_zone FROM analyses a JOIN cities c ON c.id = a.city_id "
                "JOIN users u ON u.id = a.user_id WHERE u.external_id = :ext "
                "ORDER BY a.created_at DESC LIMIT :limit"
            ),
            {"ext": external_user_id, "limit": limit},
        ).all()
        return [
            AnalysisListItem(
                r.id, r.city_key, r.category, r.tier, r.status,
                r.created_at.isoformat() if r.created_at else None, r.top_zone,
            )
            for r in rows
        ]  # fmt: skip


@contextmanager
def open_store_url(database_url: str, *, write: bool) -> Iterator[SqlAnalysisStore]:
    """A store over a fresh session: READ ONLY unless ``write`` is explicitly requested."""
    engine = get_engine(database_url)
    if not write:
        engine = engine.execution_options(postgresql_readonly=True)
    with Session(engine) as session:
        yield SqlAnalysisStore(session)


def open_store(settings: Settings, *, write: bool) -> AbstractContextManager[SqlAnalysisStore]:
    """Like ``open_store_url`` with the app's configured database."""
    return open_store_url(settings.database_url, write=write)
