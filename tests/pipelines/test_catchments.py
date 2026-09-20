"""Tests for catchment generation (pure computation, no I/O)."""

from __future__ import annotations

import h3
import numpy as np
import pytest

from pipelines.catchments import (
    haversine_many_m,
    index_pois_by_cell,
    iter_catchments,
    poi_row,
)
from pipelines.geo import haversine_m
from pipelines.grid import describe_cell, point_to_cell
from pipelines.normalise import PoiRecord

LAT, LON = 12.9716, 77.5946
CELL = point_to_cell(LAT, LON, 9)
INFO = describe_cell(CELL)
DEG_LAT_M = 110_574.0


def poi(osm_id: int, lat: float, lon: float, category: str = "cafe") -> PoiRecord:
    return PoiRecord("node", osm_id, category, lat, lon, name=f"p{osm_id}")


def test_vectorised_haversine_matches_the_scalar_version() -> None:
    lats = np.array([12.98, 12.95, 13.0])
    lons = np.array([77.60, 77.55, 77.70])
    many = haversine_many_m(LAT, LON, lats, lons)
    for got, la, lo in zip(many, lats, lons, strict=True):
        assert got == pytest.approx(haversine_m(LAT, LON, float(la), float(lo)), rel=1e-9)


def test_index_groups_by_containing_cell() -> None:
    index = index_pois_by_cell([poi(1, INFO.lat, INFO.lon), poi(2, INFO.lat, INFO.lon)], 9)
    assert list(index) == [CELL]
    assert len(index[CELL]) == 2


def test_catchment_contains_only_pois_within_the_k_ring_with_distances() -> None:
    near = poi(1, INFO.lat + 0.001, INFO.lon)  # ~110 m away, same or adjacent cell
    ring_two = poi(2, INFO.lat + 0.004, INFO.lon)  # ~440 m: inside k=2, outside k=0
    far = poi(3, INFO.lat + 0.05, INFO.lon)  # ~5.5 km: outside any small k
    ((cell, rows),) = iter_catchments([INFO], [near, ring_two, far], k=2, resolution=9, city_id=1)
    assert cell.h3_index == CELL
    assert {r.osm_id for r in rows} == {1, 2}
    by_id = {r.osm_id: r for r in rows}
    assert by_id[1].distance_m == pytest.approx(0.001 * DEG_LAT_M, rel=0.02)
    assert by_id[2].distance_m == pytest.approx(0.004 * DEG_LAT_M, rel=0.02)
    assert all(r.city_id == 1 for r in rows)


def test_k_zero_is_the_cell_itself() -> None:
    inside = poi(1, INFO.lat, INFO.lon)
    neighbour_cell = next(c for c in h3.grid_ring(CELL, 1))
    n_lat, n_lon = h3.cell_to_latlng(neighbour_cell)
    ((_, rows),) = iter_catchments(
        [INFO], [inside, poi(2, n_lat, n_lon)], k=0, resolution=9, city_id=1
    )
    assert [r.osm_id for r in rows] == [1]


def test_pois_outside_the_city_still_count_for_edge_cells() -> None:
    outside = poi(9, INFO.lat + 0.002, INFO.lon)
    ((_, rows),) = iter_catchments([INFO], [outside], k=2, resolution=9, city_id=1)
    assert len(rows) == 1
    # the row records which cell it is in, even if that cell is not one of the city's cells
    assert rows[0].h3_index == point_to_cell(outside.lat, outside.lon, 9)


def test_empty_catchment_and_max_distance_cutoff() -> None:
    ((_, rows),) = iter_catchments([INFO], [], k=2, resolution=9, city_id=1)
    assert rows == []
    near = poi(1, INFO.lat + 0.001, INFO.lon)
    ((_, kept),) = iter_catchments([INFO], [near], k=2, resolution=9, city_id=1, max_distance_m=50)
    assert kept == []


def test_generator_is_lazy_and_rejects_negative_k() -> None:
    generator = iter_catchments([INFO], [], k=1, resolution=9, city_id=1)
    assert iter(generator) is generator  # a generator, not a list
    with pytest.raises(ValueError, match="k must be"):
        list(iter_catchments([INFO], [], k=-1, resolution=9, city_id=1))


def test_poi_row_carries_fields_and_rounds_distance() -> None:
    row = poi_row(poi(1, LAT, LON), city_id=3, h3_index=CELL, distance_m=123.456)
    assert (row.category, row.name, row.city_id, row.h3_index) == ("cafe", "p1", 3, CELL)
    assert row.distance_m == 123.5
