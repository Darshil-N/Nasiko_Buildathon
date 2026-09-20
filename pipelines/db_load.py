"""Idempotent loading of a city dataset into PostGIS (plan steps 1.3.4, 1.4.5).

Every statement is an upsert on a natural key, so re-running a load never duplicates rows.
This module only runs when the owner has approved a database write (rule 2, gate G-DB): the CLI
requires an explicit ``--write`` flag and a ``DATABASE_URL``, and defaults to a dry run.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Any

from sqlalchemy import Connection, text

from pipelines.attributes import CellAttributeRow
from pipelines.city_dataset import CityDataset
from pipelines.grid import GridCell
from pipelines.normalise import PoiRecord

BATCH_SIZE = 1000

UPSERT_CITY = text(
    """
    INSERT INTO cities (key, name, state, country, bbox, status)
    VALUES (:key, :name, :state, :country, ST_GeomFromText(:bbox_wkt, 4326), 'ingesting')
    ON CONFLICT (key) DO UPDATE
        SET name = EXCLUDED.name, state = EXCLUDED.state,
            country = EXCLUDED.country, bbox = EXCLUDED.bbox
    RETURNING id
    """
)

UPSERT_CELL = text(
    """
    INSERT INTO cells (h3_index, city_id, centroid, boundary, locality_name, land_use)
    VALUES (:h3_index, :city_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
            ST_GeomFromText(:boundary_wkt, 4326), :locality_name, :land_use)
    ON CONFLICT (h3_index) DO UPDATE
        SET city_id = EXCLUDED.city_id, centroid = EXCLUDED.centroid,
            boundary = EXCLUDED.boundary, locality_name = EXCLUDED.locality_name,
            land_use = EXCLUDED.land_use
    """
)

UPSERT_ATTRIBUTES = text(
    """
    INSERT INTO cell_attributes (h3_index, landuse_residential_share, landuse_commercial_share,
                                 landuse_retail_share, main_road_dist_m, main_road_class,
                                 source_version)
    VALUES (:h3_index, :res, :com, :ret, :road_dist, :road_class, :source_version)
    ON CONFLICT (h3_index) DO UPDATE
        SET landuse_residential_share = EXCLUDED.landuse_residential_share,
            landuse_commercial_share = EXCLUDED.landuse_commercial_share,
            landuse_retail_share = EXCLUDED.landuse_retail_share,
            main_road_dist_m = EXCLUDED.main_road_dist_m,
            main_road_class = EXCLUDED.main_road_class,
            source_version = EXCLUDED.source_version,
            computed_at = now()
    """
)

UPSERT_POI = text(
    """
    INSERT INTO pois (osm_type, osm_id, city_id, category, name, brand, location, h3_index, tags,
                      source)
    VALUES (:osm_type, :osm_id, :city_id, :category, :name, :brand,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :h3_index, CAST(:tags AS JSONB), 'osm')
    ON CONFLICT (osm_type, osm_id) DO UPDATE
        SET city_id = EXCLUDED.city_id, category = EXCLUDED.category, name = EXCLUDED.name,
            brand = EXCLUDED.brand, location = EXCLUDED.location, h3_index = EXCLUDED.h3_index,
            tags = EXCLUDED.tags, fetched_at = now()
    """
)

RECORD_JOB = text(
    """
    INSERT INTO ingest_jobs (city_id, source, purpose, target, status, stats, finished_at)
    VALUES (:city_id, 'osm', :purpose, :target, 'done', CAST(:stats AS JSONB), now())
    """
)


def _batches(rows: Sequence[dict[str, Any]]) -> Iterator[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start : start + BATCH_SIZE]


def _polygon_wkt(cell: GridCell) -> str:
    ring = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in cell.boundary)
    return f"POLYGON(({ring}))"


def city_params(dataset: CityDataset, bbox_wkt: str) -> dict[str, Any]:
    """Parameters for ``UPSERT_CITY``."""
    city = dataset.city
    return {
        "key": city.key,
        "name": city.name,
        "state": city.state,
        "country": city.country,
        "bbox_wkt": bbox_wkt,
    }


def cell_rows(
    cells: Sequence[GridCell], attributes: Sequence[CellAttributeRow], city_id: int
) -> list[dict[str, Any]]:
    """Parameter dicts for ``UPSERT_CELL`` (cells and attributes are parallel lists)."""
    by_id = {a.h3_index: a for a in attributes}
    return [
        {
            "h3_index": c.h3_index,
            "city_id": city_id,
            "lat": c.lat,
            "lon": c.lon,
            "boundary_wkt": _polygon_wkt(c),
            "locality_name": by_id[c.h3_index].locality_name,
            "land_use": by_id[c.h3_index].land_use,
        }
        for c in cells
    ]


def attribute_rows(attributes: Sequence[CellAttributeRow], version: str) -> list[dict[str, Any]]:
    """Parameter dicts for ``UPSERT_ATTRIBUTES``."""
    return [
        {
            "h3_index": a.h3_index,
            "res": a.landuse_residential_share,
            "com": a.landuse_commercial_share,
            "ret": a.landuse_retail_share,
            "road_dist": a.main_road_dist_m,
            "road_class": a.main_road_class,
            "source_version": version,
        }
        for a in attributes
    ]


def poi_rows(
    pois: Sequence[PoiRecord], poi_cells: Sequence[str | None], city_id: int
) -> list[dict[str, Any]]:
    """Parameter dicts for ``UPSERT_POI``; POIs outside the city keep ``h3_index`` NULL."""
    return [
        {
            "osm_type": p.osm_type,
            "osm_id": p.osm_id,
            "city_id": city_id,
            "category": p.category,
            "name": p.name,
            "brand": p.brand,
            "lat": p.lat,
            "lon": p.lon,
            "h3_index": cell,
            "tags": json.dumps(p.tags, ensure_ascii=False),
        }
        for p, cell in zip(pois, poi_cells, strict=True)
    ]


def load_dataset(
    conn: Connection, dataset: CityDataset, bbox_wkt: str, version: str
) -> dict[str, int]:
    """Upsert the whole dataset inside the caller's transaction and return row counts.

    The caller owns the transaction: commit only after the owner has approved the write.
    The city stays in status ``ingesting``: it becomes ``ready`` only once features are built.
    """
    city_id = int(conn.execute(UPSERT_CITY, city_params(dataset, bbox_wkt)).scalar_one())
    for batch in _batches(cell_rows(dataset.cells, dataset.attributes, city_id)):
        conn.execute(UPSERT_CELL, batch)
    for batch in _batches(attribute_rows(dataset.attributes, version)):
        conn.execute(UPSERT_ATTRIBUTES, batch)
    for batch in _batches(poi_rows(dataset.pois, dataset.poi_cells, city_id)):
        conn.execute(UPSERT_POI, batch)
    counts = {
        "cells": len(dataset.cells),
        "cell_attributes": len(dataset.attributes),
        "pois": len(dataset.pois),
    }
    conn.execute(
        RECORD_JOB,
        {
            "city_id": city_id,
            "purpose": "pois+attributes",
            "target": dataset.city.key,
            "stats": json.dumps(counts),
        },
    )
    return counts
