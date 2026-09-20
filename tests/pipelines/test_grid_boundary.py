"""Tests for the boundary, H3 grid and city-config modules."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from shapely.geometry import Point, Polygon, box

from pipelines.boundary import (
    BoundaryError,
    area_km2,
    city_bbox,
    fetch_nominatim_boundary,
    load_boundary,
)
from pipelines.city_config import CityConfig, load_city
from pipelines.grid import cell_polygon, describe_cell, point_to_cell, polyfill

CITY_YAML = Path("config/cities/bengaluru.yaml")


def test_area_of_a_tenth_of_a_degree_square() -> None:
    # 0.1 deg x 0.1 deg at latitude ~13: about 10.85 km x 11.06 km = ~120 km2
    assert area_km2(box(77.5, 12.95, 77.6, 13.05)) == pytest.approx(120.0, rel=0.02)


def test_city_bbox_buffer_grows_the_box() -> None:
    geom = box(77.5, 12.95, 77.6, 13.05)
    plain, grown = city_bbox(geom), city_bbox(geom, 1000)
    assert grown.south < plain.south
    assert grown.north > plain.north
    assert grown.west < plain.west
    assert grown.east > plain.east


def test_load_boundary_accepts_feature_and_bare_geometry(tmp_path: Path) -> None:
    ring = [[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]
    geometry = {"type": "Polygon", "coordinates": [ring]}
    (tmp_path / "f.geojson").write_text(json.dumps({"type": "Feature", "geometry": geometry}))
    (tmp_path / "g.geojson").write_text(json.dumps(geometry))
    assert load_boundary(tmp_path / "f.geojson").equals(load_boundary(tmp_path / "g.geojson"))


def test_load_boundary_rejects_non_polygons(tmp_path: Path) -> None:
    (tmp_path / "p.geojson").write_text(json.dumps({"type": "Point", "coordinates": [77.5, 12.9]}))
    with pytest.raises(BoundaryError, match="Polygon"):
        load_boundary(tmp_path / "p.geojson")


def test_polyfill_is_sorted_deterministic_and_inside() -> None:
    geom = box(77.55, 12.95, 77.65, 13.05)
    cells = polyfill(geom, 9)
    assert cells == sorted(cells) == polyfill(geom, 9)
    assert 900 < len(cells) < 1300  # ~120 km2 / ~0.105 km2 per cell
    assert all(geom.contains(Point(describe_cell(c).lon, describe_cell(c).lat)) for c in cells)


def test_polyfill_rejects_points() -> None:
    with pytest.raises(ValueError, match="Polygon"):
        polyfill(Point(77.5, 12.9), 9)


def test_cell_round_trip_and_polygon() -> None:
    cell = point_to_cell(12.9716, 77.5946, 9)
    info = describe_cell(cell)
    assert point_to_cell(info.lat, info.lon, 9) == cell
    assert info.boundary[0] == info.boundary[-1]
    assert len(info.boundary) == 7
    poly = cell_polygon(cell)
    assert isinstance(poly, Polygon)
    assert poly.is_valid
    assert poly.contains(Point(info.lon, info.lat))


def test_committed_bengaluru_boundary_and_grid() -> None:
    """Regression guard for the real city data checked into config/cities/."""
    city = load_city(CITY_YAML)
    boundary = load_boundary(city.boundary_file)
    assert 690 < area_km2(boundary) < 740  # OSM relation 7902476, about 716 km2
    cells = polyfill(boundary, city.h3_resolution)
    assert 6000 < len(cells) < 7600
    assert point_to_cell(12.9716, 77.5946, 9) in set(cells)  # central Bengaluru


def test_city_config_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="key"):
        CityConfig(key="Bad Key", name="x", osm_relation_id=1, boundary_file=Path("x"))
    with pytest.raises(ValueError, match="h3_resolution"):
        CityConfig(key="a", name="x", osm_relation_id=1, boundary_file=Path("x"), h3_resolution=99)


def test_fetch_nominatim_boundary_accepts_only_the_requested_object() -> None:
    hits = [
        {"osm_type": "relation", "osm_id": 1, "geojson": {"type": "Point", "coordinates": [0, 0]}},
        {"osm_type": "relation", "osm_id": 2, "geojson": {"type": "Polygon", "coordinates": []}},
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=hits)))
    feature = fetch_nominatim_boundary("x", "relation", 2, client=client)
    assert feature["properties"]["osm_id"] == 2
    with pytest.raises(BoundaryError, match="no relation/99"):
        fetch_nominatim_boundary("x", "relation", 99, client=client)
