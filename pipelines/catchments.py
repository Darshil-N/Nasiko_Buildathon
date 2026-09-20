"""Catchments: for each cell, the POIs within its H3 k-ring, each with a distance (plan step 3.8).

The scoring library's per-feature functions (``scoring.features``) take "the POIs in a cell's
catchment, each with ``distance_m``". This module produces exactly that input, one cell at a
time (a generator), because materialising every cell's catchment at once would need millions
of objects. Distances are metres from the cell centroid to the POI (great-circle).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Sequence

import h3
import numpy as np

from pipelines.geo import EARTH_RADIUS_M
from pipelines.grid import GridCell, point_to_cell
from pipelines.normalise import PoiRecord
from shared.contracts import POIRow


def index_pois_by_cell(pois: Sequence[PoiRecord], resolution: int) -> dict[str, list[PoiRecord]]:
    """Group POIs by the H3 cell that contains them (including cells outside the city)."""
    index: dict[str, list[PoiRecord]] = defaultdict(list)
    for poi in pois:
        index[point_to_cell(poi.lat, poi.lon, resolution)].append(poi)
    return index


def haversine_many_m(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Great-circle distances in metres from one point to many points (degrees in)."""
    p1, p2 = np.radians(lat), np.radians(lats)
    dphi = p2 - p1
    dlmb = np.radians(lons - lon)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return np.asarray(2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)))


def poi_row(poi: PoiRecord, city_id: int, h3_index: str | None, distance_m: float) -> POIRow:
    """Convert a normalised POI to the shared contract row, with its distance filled in."""
    return POIRow(
        osm_type=poi.osm_type,
        osm_id=poi.osm_id,
        city_id=city_id,
        category=poi.category,
        name=poi.name,
        brand=poi.brand,
        lat=poi.lat,
        lon=poi.lon,
        h3_index=h3_index,
        distance_m=round(distance_m, 1),
    )


def iter_catchments(
    cells: Sequence[GridCell],
    pois: Sequence[PoiRecord],
    *,
    k: int,
    resolution: int,
    city_id: int,
    max_distance_m: float | None = None,
) -> Iterator[tuple[GridCell, list[POIRow]]]:
    """Yield ``(cell, POIs in its k-ring with distance_m)`` for every cell, lazily.

    Args:
        cells: the city's cells.
        pois: all POIs (POIs just outside the city are welcome: edge cells need them).
        k: k-ring radius; the catchment is the cell plus rings 1..k.
        resolution: H3 resolution of ``cells``.
        city_id: stored on each yielded row.
        max_distance_m: optional extra cut-off; POIs further than this are dropped.
    """
    if k < 0:
        raise ValueError("k must be >= 0")
    by_cell = index_pois_by_cell(pois, resolution)
    for cell in cells:
        nearby: list[PoiRecord] = []
        for ring_cell in h3.grid_disk(cell.h3_index, k):
            nearby.extend(by_cell.get(ring_cell, ()))
        if not nearby:
            yield cell, []
            continue
        lats = np.fromiter((p.lat for p in nearby), dtype=float, count=len(nearby))
        lons = np.fromiter((p.lon for p in nearby), dtype=float, count=len(nearby))
        distances = haversine_many_m(cell.lat, cell.lon, lats, lons)
        rows = [
            poi_row(p, city_id, point_to_cell(p.lat, p.lon, resolution), float(d))
            for p, d in zip(nearby, distances, strict=True)
            if max_distance_m is None or d <= max_distance_m
        ]
        yield cell, rows
