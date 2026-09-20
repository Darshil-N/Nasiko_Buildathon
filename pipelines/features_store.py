"""Storing and reading ``cell_features`` (plan step 3.8.1).

One row per (cell, category, feature version). The ``features`` JSON holds the full
``CellFeatures`` for each tier plus the per-category anchor sums, so an analysis can pick its tier,
or re-weight F1 for questionnaire answers, without touching the raw data again.

Writing is a database change: it runs only from the CLI's ``--write`` after the owner approves.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from pipelines.build_features import CategoryFeatureSet
from shared.contracts import CellFeatures

BATCH_SIZE = 500

UPSERT_CELL_FEATURES = text(
    """
    INSERT INTO cell_features (h3_index, category, feature_version, features, affluence,
                               rent_per_sqft_est, rent_is_estimated, confidence)
    VALUES (:h3_index, :category, :feature_version, CAST(:features AS JSONB), :affluence,
            NULL, NULL, :confidence)
    ON CONFLICT (h3_index, category, feature_version) DO UPDATE
        SET features = EXCLUDED.features, affluence = EXCLUDED.affluence,
            confidence = EXCLUDED.confidence, computed_at = now()
    """
)
SELECT_CITY_ID = text("SELECT id FROM cities WHERE key = :key")
MARK_READY = text("UPDATE cities SET status = 'ready', last_full_refresh = now() WHERE key = :key")
SELECT_BUNDLE = text(
    """
    SELECT h3_index,
           features -> 'tiers' -> CAST(:tier AS TEXT) AS tier_features,
           features -> 'anchor_components' AS anchor_components
    FROM cell_features
    WHERE category = :category AND feature_version = :feature_version
    ORDER BY h3_index
    """
)
SELECT_FEATURES = text(
    """
    SELECT h3_index, features -> 'tiers' -> CAST(:tier AS TEXT) AS tier_features
    FROM cell_features
    WHERE category = :category AND feature_version = :feature_version
    ORDER BY h3_index
    """
)


def feature_rows(feature_set: CategoryFeatureSet, city_id: int) -> list[dict[str, Any]]:
    """Parameter dicts for ``UPSERT_CELL_FEATURES`` (one per cell)."""
    rows: list[dict[str, Any]] = []
    for i, cell_id in enumerate(feature_set.cell_ids):
        per_tier = {}
        for tier, features in feature_set.tiers.items():
            dumped = features[i].model_dump(mode="json")
            dumped["city_id"] = city_id
            per_tier[tier] = dumped
        middle = feature_set.tiers["mid"][i]
        payload = {
            "config_version": feature_set.config_version,
            "tiers": per_tier,
            "anchor_components": feature_set.anchor_components[cell_id],
        }
        rows.append(
            {
                "h3_index": cell_id,
                "category": feature_set.category,
                "feature_version": feature_set.feature_version,
                "features": json.dumps(payload),
                "affluence": middle.affluence,
                "confidence": middle.confidence,
            }
        )
    return rows


def _batches(rows: Sequence[dict[str, Any]]) -> Iterator[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start : start + BATCH_SIZE]


def store_feature_set(conn: Connection, feature_set: CategoryFeatureSet, city_key: str) -> int:
    """Upsert one category's features inside the caller's transaction; return the row count."""
    city_id = conn.execute(SELECT_CITY_ID, {"key": city_key}).scalar_one()
    rows = feature_rows(feature_set, int(city_id))
    for batch in _batches(rows):
        conn.execute(UPSERT_CELL_FEATURES, batch)
    return len(rows)


def load_tier_features(
    session: Session, category: str, tier: str, feature_version: int = 1
) -> list[CellFeatures]:
    """Read one category's stored features for a tier (read-only)."""
    result = session.execute(
        SELECT_FEATURES, {"category": category, "tier": tier, "feature_version": feature_version}
    )
    return [CellFeatures.model_validate(row.tier_features) for row in result.all()]


def mark_city_ready(conn: Connection, city_key: str) -> None:
    """A city is ready once its features are stored (architecture section 4.4, step 7)."""
    conn.execute(MARK_READY, {"key": city_key})


@dataclass(frozen=True)
class FeatureBundle:
    """One cell's features for a tier, plus its per-category anchor sums."""

    features: CellFeatures
    anchor_components: dict[str, float]


def load_tier_bundle(
    session: Session, category: str, tier: str, feature_version: int = 1
) -> list[FeatureBundle]:
    """Like ``load_tier_features`` but also returns the anchor sums (read-only)."""
    result = session.execute(
        SELECT_BUNDLE, {"category": category, "tier": tier, "feature_version": feature_version}
    )
    return [
        FeatureBundle(
            features=CellFeatures.model_validate(row.tier_features),
            anchor_components=dict(row.anchor_components or {}),
        )
        for row in result.all()
    ]
