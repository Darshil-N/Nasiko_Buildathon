"""City ingestion CLI (architecture section 4.4).

Stages run independently and never touch a database unless a later stage says so:

    python -m pipelines.ingest_city fetch --city config/cities/bengaluru.yaml
    python -m pipelines.ingest_city grid  --city config/cities/bengaluru.yaml
    python -m pipelines.ingest_city build --city config/cities/bengaluru.yaml
    python -m pipelines.ingest_city load  --city config/cities/bengaluru.yaml
    python -m pipelines.ingest_city load  --city config/cities/bengaluru.yaml --write

``fetch`` downloads OSM data tile by tile into ``data/raw/osm/<city>/`` (cached, resumable).
``grid`` builds the H3 cells for the city polygon and prints a summary.
``build`` assembles the downloaded data into cells, attributes and POIs and prints a QA report.
``load`` upserts that dataset into PostGIS. It is a dry run unless ``--write`` is given, and
``--write`` may only be used after the owner has approved the database write (rule 2, G-DB).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from pipelines.boundary import area_km2, city_bbox, load_boundary
from pipelines.city_config import CityConfig, load_city
from pipelines.city_dataset import CityDataset, build_dataset, qa_summary
from pipelines.grid import polyfill
from pipelines.osm_config import DEFAULT_PATH, Kind, OsmTagConfig, load_osm_tags
from pipelines.osm_fetch import fetch_group
from pipelines.overpass import OverpassClient

logger = logging.getLogger("ingest_city")

RAW_ROOT = Path("data/raw/osm")
# Fetch order: the groups the scoring needs most come first.
PREFERRED_ORDER = [
    "food", "health", "retail", "education", "work", "finance",
    "leisure", "transport", "buildings", "places", "roads", "landuse",
]  # fmt: skip
GEOMETRY_KINDS: frozenset[Kind] = frozenset({"area", "line"})


def group_needs_geometry(config: OsmTagConfig, group: str) -> bool:
    """True if any category in ``group`` is a polygon or line that needs full geometry."""
    return any(r.kind in GEOMETRY_KINDS for r in config.categories if r.group == group)


def all_groups(config: OsmTagConfig) -> list[str]:
    """Every group in the tag config, in the preferred fetch order."""
    present = {r.group for r in config.categories}
    ordered = [g for g in PREFERRED_ORDER if g in present]
    return ordered + sorted(present - set(ordered))


def run_fetch(city: CityConfig, config: OsmTagConfig, groups: list[str], *, refresh: bool) -> int:
    """Download the requested groups; return the number of groups written."""
    boundary = load_boundary(city.boundary_file)
    bbox = city_bbox(boundary, city.fetch_buffer_m)
    out_dir = RAW_ROOT / city.key / "latest"
    cache_dir = RAW_ROOT / city.key / "cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OverpassClient(cache_dir)
    written = 0
    for group in groups:
        target = out_dir / f"{group}.json"
        if target.exists() and not refresh:
            logger.info("skip %s (already downloaded; use --refresh to redo)", group)
            continue
        logger.info("fetching group %s over %s", group, bbox)
        elements = fetch_group(
            client,
            config,
            group,
            bbox,
            city.tile_rows,
            city.tile_cols,
            city_key=city.key,
            geometry=group_needs_geometry(config, group),
            on_progress=lambda g, n, total: logger.info("  %s tile %d/%d done", g, n, total),
        )
        meta = {
            "city": city.key,
            "group": group,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "bbox": bbox.overpass(),
            "tag_config_version": config.version,
            "element_count": len(elements),
            "elements": elements,
        }
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta), encoding="utf-8")
        tmp.replace(target)
        logger.info("wrote %s: %d elements", target, len(elements))
        written += 1
    return written


def run_grid(city: CityConfig) -> int:
    """Print the number of H3 cells covering the city polygon."""
    boundary = load_boundary(city.boundary_file)
    cells = polyfill(boundary, city.h3_resolution)
    logger.info(
        "%s: boundary %.0f km2, %d cells at H3 resolution %d (%.3f km2 per cell)",
        city.name,
        area_km2(boundary),
        len(cells),
        city.h3_resolution,
        area_km2(boundary) / len(cells),
    )
    return len(cells)


def run_load(dataset: CityDataset, version: str, *, write: bool) -> None:
    """Dry-run by default; with ``write`` upsert the dataset in a single transaction."""
    if not write:
        logger.info(
            "DRY RUN: would upsert %d cells, %d attribute rows and %d POIs. "
            "Nothing was written. Re-run with --write once the owner has approved.",
            len(dataset.cells),
            len(dataset.attributes),
            len(dataset.pois),
        )
        return
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set; refusing to guess a database")
    from shapely.geometry import box
    from sqlalchemy import create_engine

    from pipelines.db_load import load_dataset

    bbox_wkt = box(*load_boundary(dataset.city.boundary_file).bounds).wkt
    engine = create_engine(url)
    with engine.begin() as conn:  # one transaction: all or nothing
        counts = load_dataset(conn, dataset, bbox_wkt, version)
    logger.info("loaded: %s", counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SiteScout city ingestion")
    parser.add_argument("stage", choices=["fetch", "grid", "build", "load"])
    parser.add_argument(
        "--city", type=Path, required=True, help="path to config/cities/<city>.yaml"
    )
    parser.add_argument("--tags", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--groups", nargs="*", help="only these groups (default: all)")
    parser.add_argument("--refresh", action="store_true", help="re-download groups already on disk")
    parser.add_argument(
        "--write",
        action="store_true",
        help="load: really write to the database (needs owner approval and DATABASE_URL)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    city = load_city(args.city)
    if args.stage == "grid":
        run_grid(city)
        return 0
    config = load_osm_tags(args.tags)
    if args.stage in {"build", "load"}:
        dataset = build_dataset(city, config, RAW_ROOT / city.key / "latest")
        report = qa_summary(dataset)
        report_path = RAW_ROOT / city.key / "qa_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("QA report written to %s", report_path)
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if args.stage == "load":
            run_load(dataset, config.version, write=args.write)
        return 0
    groups = args.groups or all_groups(config)
    unknown = sorted(set(groups) - {r.group for r in config.categories})
    if unknown:
        parser.error(f"unknown groups: {unknown}")
    run_fetch(city, config, groups, refresh=args.refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
