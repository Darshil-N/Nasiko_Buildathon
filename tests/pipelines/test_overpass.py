"""Tests for the Overpass client, query builder and geometry helpers (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pipelines.geo import BBox, haversine_m, metres_per_degree_lon
from pipelines.osm_config import Selector
from pipelines.overpass import OverpassClient, OverpassError, build_query, cache_name

BBOX = BBox(12.83, 77.45, 13.14, 77.78)


class FakeTime:
    """Deterministic clock and sleeper."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(
    tmp_path: Path, handler: httpx.MockTransport, ft: FakeTime, **kw: object
) -> OverpassClient:
    return OverpassClient(
        tmp_path,
        http_client=httpx.Client(transport=handler),
        sleep=ft.sleep,
        clock=ft.clock,
        min_interval_s=5.0,
        backoff_base_s=10.0,
        **kw,  # type: ignore[arg-type]
    )


def test_bbox_validation_and_tiles() -> None:
    with pytest.raises(ValueError, match="degenerate"):
        BBox(1, 1, 1, 2)
    tiles = BBOX.tiles(2, 3)
    assert len(tiles) == 6
    assert tiles[0].south == BBOX.south
    assert tiles[0].west == BBOX.west
    assert tiles[-1].north == pytest.approx(BBOX.north)
    assert tiles[-1].east == pytest.approx(BBOX.east)
    assert all(BBOX.contains((t.south + t.north) / 2, (t.west + t.east) / 2) for t in tiles)


def test_haversine_and_projection_scale() -> None:
    d = haversine_m(12.9716, 77.5946, 12.9716, 77.6946)  # 0.1 degree of longitude
    assert d == pytest.approx(0.1 * metres_per_degree_lon(12.9716), rel=1e-3)


def test_build_query_centre_and_geometry() -> None:
    sel = [Selector.parse("amenity=cafe"), Selector.parse("office")]
    q = build_query(sel, BBOX)
    assert "[out:json][timeout:180];" in q
    assert 'nwr["amenity"="cafe"](12.830000,77.450000,13.140000,77.780000);' in q
    assert 'nwr["office"]' in q
    assert q.rstrip().endswith("out center tags;")
    assert build_query(sel, BBOX, geometry=True).rstrip().endswith("out geom tags;")
    with pytest.raises(ValueError, match="at least one selector"):
        build_query([], BBOX)


def test_cache_name_depends_on_query() -> None:
    assert cache_name("a b", "q1") != cache_name("a b", "q2")
    assert cache_name("a b", "q1").startswith("a_b-")


def test_fetch_caches_to_disk_and_second_call_hits_cache(tmp_path: Path) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"elements": [{"id": 1}]})

    ft = FakeTime()
    client = make_client(tmp_path, httpx.MockTransport(handler), ft)
    assert client.fetch("t", "Q")["elements"] == [{"id": 1}]
    assert client.fetch("t", "Q")["elements"] == [{"id": 1}]
    assert len(calls) == 1
    assert (tmp_path / cache_name("t", "Q")).exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_retries_on_429_then_succeeds_with_backoff(tmp_path: Path) -> None:
    responses = iter(
        [httpx.Response(429), httpx.Response(504), httpx.Response(200, json={"elements": []})]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    ft = FakeTime()
    client = make_client(tmp_path, httpx.MockTransport(handler), ft)
    assert client.fetch("t", "Q") == {"elements": []}
    assert 10.0 in ft.sleeps
    assert 20.0 in ft.sleeps


def test_retry_after_header_is_honoured(tmp_path: Path) -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"elements": []}),
        ]
    )
    ft = FakeTime()
    client = make_client(tmp_path, httpx.MockTransport(lambda r: next(responses)), ft)
    client.fetch("t", "Q")
    assert 7.0 in ft.sleeps


def test_pacing_between_requests(tmp_path: Path) -> None:
    ft = FakeTime()
    client = make_client(
        tmp_path, httpx.MockTransport(lambda r: httpx.Response(200, json={"elements": []})), ft
    )
    client.fetch("a", "Q1")
    client.fetch("b", "Q2")
    assert ft.sleeps == [5.0]  # second request waited the full minimum interval


def test_runtime_error_remark_is_not_cached_and_raises(tmp_path: Path) -> None:
    body = {"elements": [], "remark": 'runtime error: Query timed out in "query" at line 1'}
    ft = FakeTime()
    client = make_client(
        tmp_path, httpx.MockTransport(lambda r: httpx.Response(200, json=body)), ft, max_attempts=2
    )
    with pytest.raises(OverpassError, match="gave up after 2 attempts"):
        client.fetch("t", "Q")
    assert not list(tmp_path.glob("*.json"))


def test_non_retryable_status_raises_immediately(tmp_path: Path) -> None:
    ft = FakeTime()
    client = make_client(
        tmp_path, httpx.MockTransport(lambda r: httpx.Response(400, text="bad query")), ft
    )
    with pytest.raises(OverpassError, match="HTTP 400"):
        client.fetch("t", "Q")
    assert ft.sleeps == []


def test_corrupt_json_response_raises(tmp_path: Path) -> None:
    ft = FakeTime()
    client = make_client(
        tmp_path, httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")), ft
    )
    with pytest.raises(OverpassError, match="not JSON"):
        client.fetch("t", "Q")


def test_cache_file_round_trips_json(tmp_path: Path) -> None:
    ft = FakeTime()
    client = make_client(
        tmp_path, httpx.MockTransport(lambda r: httpx.Response(200, json={"elements": [1, 2]})), ft
    )
    client.fetch("t", "Q")
    stored = json.loads((tmp_path / cache_name("t", "Q")).read_text(encoding="utf-8"))
    assert stored == {"elements": [1, 2]}
