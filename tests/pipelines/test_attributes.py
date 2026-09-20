"""Tests for per-cell attributes: land-use shares, main roads, localities, land-use class."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import LineString, box

from pipelines.attributes import (
    CellAttributeRow,
    LandUsePolygon,
    PlacePoint,
    RoadLine,
    assign_localities,
    build_cell_attributes,
    classify_land_use,
    landuse_polygons,
    landuse_shares,
    nearest_roads,
    place_points,
    poi_counts_by_cell,
    road_lines,
)
from pipelines.grid import cell_polygon, describe_cell, point_to_cell
from pipelines.normalise import PoiRecord
from pipelines.osm_config import OsmTagConfig, load_osm_tags

CELL = point_to_cell(12.9716, 77.5946, 9)
INFO = describe_cell(CELL)
REF_LAT = INFO.lat


@pytest.fixture(scope="module")
def config() -> OsmTagConfig:
    return load_osm_tags(Path("config/osm_tags.yaml"))


def geometry_of(points: list[tuple[float, float]]) -> list[dict[str, float]]:
    return [{"lon": lon, "lat": lat} for lon, lat in points]


# --- parsing ---------------------------------------------------------------------------------
def test_closed_way_becomes_a_landuse_polygon(config: OsmTagConfig) -> None:
    ring = [(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98), (77.59, 12.97)]
    way = {"type": "way", "tags": {"landuse": "residential"}, "geometry": geometry_of(ring)}
    open_way = {"type": "way", "tags": {"landuse": "retail"}, "geometry": geometry_of(ring[:3])}
    other = {"type": "way", "tags": {"landuse": "forest"}, "geometry": geometry_of(ring)}
    result = landuse_polygons([way, open_way, other], config)
    assert [p.kind for p in result] == ["residential"]
    assert result[0].polygon.area > 0


def test_relation_outer_members_are_assembled_into_a_polygon(config: OsmTagConfig) -> None:
    west = [(77.59, 12.97), (77.59, 12.98), (77.595, 12.98), (77.595, 12.97), (77.59, 12.97)]
    # two half-rings that only form a polygon once joined
    half_a = [(77.59, 12.97), (77.60, 12.97), (77.60, 12.98)]
    half_b = [(77.60, 12.98), (77.59, 12.98), (77.59, 12.97)]
    relation: dict[str, Any] = {
        "type": "relation",
        "tags": {"landuse": "commercial"},
        "members": [
            {"role": "outer", "geometry": geometry_of(half_a)},
            {"role": "outer", "geometry": geometry_of(half_b)},
            {"role": "inner", "geometry": geometry_of(west)},
        ],
    }
    result = landuse_polygons([relation], config)
    assert len(result) == 1
    assert result[0].kind == "commercial"
    assert result[0].polygon.bounds == pytest.approx((77.59, 12.97, 77.60, 12.98))


def test_road_lines_keep_only_main_roads(config: OsmTagConfig) -> None:
    coords = [(77.59, 12.97), (77.60, 12.97)]
    elements = [
        {"type": "way", "tags": {"highway": "primary"}, "geometry": geometry_of(coords)},
        {"type": "way", "tags": {"highway": "residential"}, "geometry": geometry_of(coords)},
        {"type": "way", "tags": {"highway": "trunk"}, "geometry": geometry_of(coords[:1])},
    ]
    assert [r.road_class for r in road_lines(elements, config)] == ["primary"]


def test_place_points_need_a_name_and_location(config: OsmTagConfig) -> None:
    named = {"place": "suburb", "name": "Indiranagar"}
    elements = [
        {"type": "node", "lat": 12.97, "lon": 77.59, "tags": named},
        {"type": "node", "lat": 12.97, "lon": 77.59, "tags": {"place": "suburb"}},  # no name
        {"type": "way", "tags": {"place": "quarter", "name": "NoCentre"}},  # no location
        {
            "type": "way",
            "center": {"lat": 12.9, "lon": 77.5},
            "tags": {"place": "quarter", "name": "Q"},
        },
    ]
    result = place_points(elements, config)
    assert [(p.name, p.place_type) for p in result] == [("Indiranagar", "suburb"), ("Q", "quarter")]


# --- land-use shares -------------------------------------------------------------------------
def test_share_is_full_when_a_polygon_covers_the_cell() -> None:
    covering = box(INFO.lon - 0.01, INFO.lat - 0.01, INFO.lon + 0.01, INFO.lat + 0.01)
    shares = landuse_shares([CELL], [LandUsePolygon("residential", covering)], REF_LAT)
    assert shares[CELL]["residential"] == pytest.approx(1.0, abs=1e-6)
    assert shares[CELL]["commercial"] == 0.0


def test_share_is_about_half_for_a_half_covered_cell() -> None:
    poly = cell_polygon(CELL)
    half = box(poly.bounds[0] - 0.01, INFO.lat, poly.bounds[2] + 0.01, poly.bounds[3] + 0.01)
    shares = landuse_shares([CELL], [LandUsePolygon("commercial", half)], REF_LAT)
    assert shares[CELL]["commercial"] == pytest.approx(0.5, abs=0.03)


def test_overlapping_polygons_of_one_kind_are_not_double_counted() -> None:
    a = box(INFO.lon - 0.01, INFO.lat - 0.01, INFO.lon + 0.01, INFO.lat + 0.01)
    shares = landuse_shares(
        [CELL], [LandUsePolygon("retail", a), LandUsePolygon("retail", a)], REF_LAT
    )
    assert shares[CELL]["retail"] == pytest.approx(1.0, abs=1e-6)


def test_no_polygons_gives_zero_shares() -> None:
    assert landuse_shares([CELL], [], REF_LAT)[CELL] == {
        "residential": 0.0,
        "commercial": 0.0,
        "retail": 0.0,
    }


# --- main roads ------------------------------------------------------------------------------
def test_distance_to_the_nearest_road_and_its_class() -> None:
    # a road 0.01 degrees of latitude (about 1,106 m) north of the cell centre
    road = RoadLine(
        "primary",
        LineString([(INFO.lon - 0.02, INFO.lat + 0.01), (INFO.lon + 0.02, INFO.lat + 0.01)]),
    )
    far = RoadLine(
        "trunk",
        LineString([(INFO.lon - 0.02, INFO.lat + 0.05), (INFO.lon + 0.02, INFO.lat + 0.05)]),
    )
    result = nearest_roads({CELL: (INFO.lat, INFO.lon)}, [far, road], REF_LAT)
    dist, road_class = result[CELL] or (0.0, "")
    assert dist == pytest.approx(1105.7, rel=0.01)
    assert road_class == "primary"


def test_no_roads_gives_none() -> None:
    assert nearest_roads({CELL: (INFO.lat, INFO.lon)}, [], REF_LAT) == {CELL: None}


# --- localities ------------------------------------------------------------------------------
def test_locality_is_the_nearest_place_within_range() -> None:
    near = PlacePoint("Near", INFO.lat + 0.005, INFO.lon, "suburb")  # ~550 m
    far = PlacePoint("Far", INFO.lat + 0.02, INFO.lon, "suburb")
    assert assign_localities({CELL: (INFO.lat, INFO.lon)}, [far, near], REF_LAT) == {CELL: "Near"}


def test_locality_is_none_beyond_the_maximum_distance() -> None:
    far = PlacePoint("Far", INFO.lat + 0.1, INFO.lon, "suburb")  # ~11 km
    assert assign_localities({CELL: (INFO.lat, INFO.lon)}, [far], REF_LAT) == {CELL: None}
    assert assign_localities({CELL: (INFO.lat, INFO.lon)}, [], REF_LAT) == {CELL: None}


# --- POI counts and land-use class -----------------------------------------------------------
def poi(category: str, lat: float = INFO.lat, lon: float = INFO.lon, osm_id: int = 1) -> PoiRecord:
    return PoiRecord("node", osm_id, category, lat, lon)


def test_poi_counts_ignore_pois_outside_the_cells() -> None:
    pois = [poi("cafe", osm_id=1), poi("cafe", osm_id=2), poi("cafe", 20.0, 70.0, osm_id=3)]
    assert poi_counts_by_cell(pois, {CELL}, 9) == {CELL: Counter({"cafe": 2})}


@pytest.mark.parametrize(
    ("shares", "counts", "expected"),
    [
        ({"residential": 0.6}, {}, "residential"),
        ({"commercial": 0.2, "retail": 0.1}, {}, "commercial"),  # 0.3 combined >= 0.25
        ({"residential": 0.5, "commercial": 0.5}, {}, "mixed"),
        ({}, {"cafe": 2, "office": 1}, "commercial"),  # 3 commercial POIs
        ({}, {"cafe": 2}, "other"),  # below the POI threshold
        ({}, {"residential_building": 3}, "residential"),
        ({"residential": 0.1}, {}, "other"),
        ({}, {"cafe": 3, "residential_building": 4}, "mixed"),
        ({}, {"park": 50, "school": 9}, "other"),  # non-commercial POIs never count
    ],
)
def test_classify_land_use(shares: dict[str, float], counts: dict[str, int], expected: str) -> None:
    assert classify_land_use(shares, counts) == expected


def test_build_cell_attributes_combines_everything() -> None:
    covering = box(INFO.lon - 0.01, INFO.lat - 0.01, INFO.lon + 0.01, INFO.lat + 0.01)
    rows = build_cell_attributes(
        [CELL],
        {CELL: (INFO.lat, INFO.lon)},
        polygons=[LandUsePolygon("residential", covering)],
        roads=[
            RoadLine(
                "secondary",
                LineString(
                    [(INFO.lon - 0.02, INFO.lat + 0.01), (INFO.lon + 0.02, INFO.lat + 0.01)]
                ),
            )
        ],
        places=[PlacePoint("Somewhere", INFO.lat, INFO.lon, "suburb")],
        poi_counts={CELL: {"cafe": 5}},
        ref_lat=REF_LAT,
    )
    assert rows == [
        CellAttributeRow(
            h3_index=CELL,
            landuse_residential_share=1.0,
            landuse_commercial_share=0.0,
            landuse_retail_share=0.0,
            main_road_dist_m=rows[0].main_road_dist_m,
            main_road_class="secondary",
            locality_name="Somewhere",
            land_use="mixed",  # residential land plus 5 commercial POIs
        )
    ]
    assert rows[0].main_road_dist_m == pytest.approx(1105.7, rel=0.01)
