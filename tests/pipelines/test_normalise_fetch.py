"""Tests for POI normalisation and the tiled, self-splitting fetcher (no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from pipelines.geo import BBox
from pipelines.ingest_city import all_groups, group_needs_geometry
from pipelines.normalise import element_point, normalise_elements
from pipelines.osm_config import OsmTagConfig, load_osm_tags
from pipelines.osm_fetch import fetch_group, fetch_tile
from pipelines.overpass import OverpassClient


@pytest.fixture(scope="module")
def config() -> OsmTagConfig:
    return load_osm_tags(Path("config/osm_tags.yaml"))


def test_element_point_for_node_and_way_centre() -> None:
    assert element_point({"type": "node", "lat": 12.9, "lon": 77.5}) == (12.9, 77.5)
    assert element_point({"type": "way", "center": {"lat": 13.0, "lon": 77.6}}) == (13.0, 77.6)
    assert element_point({"type": "way"}) is None
    assert element_point({"type": "node", "lat": "x", "lon": 1}) is None


def test_normalise_classifies_dedupes_and_filters(config: OsmTagConfig) -> None:
    elements: list[dict[str, Any]] = [
        {"type": "node", "id": 1, "lat": 12.9, "lon": 77.5,
         "tags": {"amenity": "cafe", "name": "Third Wave", "brand": "TW", "phone": "999"}},
        {"type": "node", "id": 1, "lat": 12.9, "lon": 77.5, "tags": {"amenity": "cafe"}},  # dup
        {"type": "way", "id": 2, "center": {"lat": 13.0, "lon": 77.6},
         "tags": {"building": "apartments"}},
        {"type": "node", "id": 3, "lat": 12.8, "lon": 77.4, "tags": {"amenity": "bench"}},  # n/a
        {"type": "way", "id": 4, "tags": {"amenity": "school"}},  # no location
        {"type": "node", "id": 5, "lat": 12.9, "lon": 77.5, "tags": {"landuse": "residential"}},
    ]  # fmt: skip
    pois = normalise_elements(elements, config)
    assert [(p.osm_type, p.osm_id, p.category) for p in pois] == [
        ("node", 1, "cafe"),
        ("way", 2, "residential_building"),
    ]
    cafe = pois[0]
    assert cafe.name == "Third Wave"
    assert cafe.brand == "TW"
    assert "phone" not in cafe.tags  # only whitelisted tags are kept (privacy and size)


def test_group_helpers(config: OsmTagConfig) -> None:
    groups = all_groups(config)
    assert groups[0] == "food"
    assert set(groups) >= {"health", "retail", "roads", "landuse", "places"}
    assert group_needs_geometry(config, "landuse")
    assert group_needs_geometry(config, "roads")
    assert not group_needs_geometry(config, "food")
    assert not group_needs_geometry(config, "places")


class Recorder:
    """Fake transport: fails the first request with 400 (non-retryable), then succeeds."""

    def __init__(self, fail_first: int = 0) -> None:
        self.queries: list[str] = []
        self.fail_first = fail_first

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.queries.append(request.content.decode())
        if len(self.queries) <= self.fail_first:
            return httpx.Response(400, text="query too big")
        n = len(self.queries)
        return httpx.Response(
            200, json={"elements": [{"type": "node", "id": n, "lat": 1, "lon": 1}]}
        )


def make_client(tmp_path: Path, transport: Recorder) -> OverpassClient:
    return OverpassClient(
        tmp_path,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
        sleep=lambda s: None,
        min_interval_s=0,
    )


def test_failed_tile_is_split_into_four_subtiles(tmp_path: Path, config: OsmTagConfig) -> None:
    transport = Recorder(fail_first=1)
    client = make_client(tmp_path, transport)
    tile = BBox(12.9, 77.5, 13.0, 77.6)
    elements = fetch_tile(client, config, "food", tile, "t", geometry=False)
    assert len(transport.queries) == 5  # 1 failure + 4 sub-tiles
    assert len(elements) == 4


def test_split_depth_is_bounded(tmp_path: Path, config: OsmTagConfig) -> None:
    from pipelines.overpass import OverpassError

    client = make_client(tmp_path, Recorder(fail_first=10_000))
    with pytest.raises(OverpassError):
        fetch_tile(client, config, "food", BBox(12.9, 77.5, 13.0, 77.6), "t", geometry=False)


def test_fetch_group_tiles_and_dedupes(tmp_path: Path, config: OsmTagConfig) -> None:
    class SameElement(Recorder):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            self.queries.append(request.content.decode())
            return httpx.Response(200, json={"elements": [{"type": "node", "id": 7}]})

    transport = SameElement()
    client = make_client(tmp_path, transport)
    progress: list[tuple[str, int, int]] = []
    result = fetch_group(
        client, config, "food", BBox(12.9, 77.5, 13.0, 77.6), 2, 2,
        city_key="x", geometry=False, on_progress=lambda g, n, t: progress.append((g, n, t)),
    )  # fmt: skip
    assert len(transport.queries) == 4
    assert result == [{"type": "node", "id": 7}]
    assert progress[-1] == ("food", 4, 4)
