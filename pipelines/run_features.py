"""CLI for the feature build (plan step 3.8).

    python -m pipelines.run_features --city config/cities/bengaluru.yaml            # dry run
    python -m pipelines.run_features --city config/cities/bengaluru.yaml --demo-tier premium

A dry run computes everything and prints a summary plus the top zones per category, and writes
nothing. Storing the features (``--write``) is a database change and needs the owner's approval.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pipelines.build_features import (
    TIERS,
    CategoryFeatureSet,
    build_category_features,
    load_premium_brands,
)
from pipelines.catchment_sums import PoiArrays
from pipelines.city_config import load_city
from pipelines.city_dataset import CityDataset, build_dataset
from pipelines.features_store import mark_city_ready, store_feature_set
from pipelines.osm_config import load_osm_tags
from scoring.score import ScoreEngine
from shared.config import list_available_categories, load_category_config

logger = logging.getLogger("run_features")
RAW_ROOT = Path("data/raw/osm")
BRANDS_PATH = Path("config/brands_premium.yaml")


def dataset_age_days(dataset: CityDataset) -> float:
    """Age of the oldest downloaded group, in days (feeds the recency confidence input)."""
    stamps = [datetime.fromisoformat(s) for s in dataset.fetched_at.values() if s]
    if not stamps:
        return 0.0
    return max(0.0, (datetime.now(UTC) - min(stamps)).total_seconds() / 86400)


def describe_top_zones(
    feature_set: CategoryFeatureSet, dataset: CityDataset, tier: str, top_n: int = 10
) -> list[str]:
    """Human-readable top zones for a tier, ranked by the scoring engine."""
    config = load_category_config(feature_set.category)
    localities = {a.h3_index: a.locality_name or "?" for a in dataset.attributes}
    land_uses: dict[str, str | None] = {a.h3_index: a.land_use for a in dataset.attributes}
    zones = ScoreEngine(config, tier).rank(
        feature_set.tiers[tier], top_n=top_n, land_uses=land_uses
    )
    return [
        f"  #{z.rank:<2} {z.score:5.1f}  conf {z.confidence:.2f}  "
        f"{localities.get(z.h3_index, '?'):<28} {z.h3_index}"
        for z in zones
        if not z.excluded and not z.greyed
    ][:top_n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SiteScout feature build")
    parser.add_argument("--city", type=Path, required=True)
    parser.add_argument("--categories", nargs="*", help="default: every configured category")
    parser.add_argument("--demo-tier", choices=TIERS, default="mid")
    parser.add_argument("--write", action="store_true", help="store features (needs approval)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    city = load_city(args.city)
    dataset = build_dataset(city, load_osm_tags(), RAW_ROOT / city.key / "latest")
    arrays = PoiArrays.from_pois(dataset.pois, city.h3_resolution)
    attributes = {a.h3_index: a for a in dataset.attributes}
    brands = load_premium_brands(BRANDS_PATH)
    age_days = dataset_age_days(dataset)
    categories = args.categories or list_available_categories()
    logger.info(
        "building %s for %d cells; data age %.2f days", categories, len(dataset.cells), age_days
    )

    built: list[CategoryFeatureSet] = []
    for category in categories:
        started = time.time()
        feature_set = build_category_features(
            city_id=0,  # replaced by the real city id when stored
            cells=dataset.cells,
            attributes=attributes,
            pois=dataset.pois,
            arrays=arrays,
            config=load_category_config(category),
            premium_brands=brands,
            age_days=age_days,
        )
        built.append(feature_set)
        sys.stdout.write(f"\n=== {category} ({time.time() - started:.1f}s) ===\n")
        sys.stdout.write(json.dumps(feature_set.summary, indent=2) + "\n")
        sys.stdout.write(f"top zones, tier '{args.demo_tier}':\n")
        sys.stdout.write("\n".join(describe_top_zones(feature_set, dataset, args.demo_tier)) + "\n")

    if not args.write:
        logger.info("DRY RUN: nothing was stored. --write needs the owner's approval (gate G-DB).")
        return 0
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set; refusing to guess a database")
    from sqlalchemy import create_engine

    engine = create_engine(url)
    with engine.begin() as conn:  # one transaction: all or nothing
        for feature_set in built:
            logger.info(
                "stored %s: %d rows",
                feature_set.category,
                store_feature_set(conn, feature_set, city.key),
            )
        mark_city_ready(conn, city.key)
        logger.info("city %s is now ready", city.key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
