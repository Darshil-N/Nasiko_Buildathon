"""Download OSM elements for a whole city, tile by tile, splitting a tile if Overpass times out."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

from pipelines.geo import BBox
from pipelines.osm_config import OsmTagConfig
from pipelines.overpass import OverpassClient, OverpassError, build_query

logger = logging.getLogger(__name__)

MAX_SPLIT_DEPTH = 2  # a failing tile is split into 4 sub-tiles, at most twice (16 pieces)


def fetch_tile(
    client: OverpassClient,
    config: OsmTagConfig,
    group: str,
    tile: BBox,
    label: str,
    *,
    geometry: bool,
    timeout_s: int = 180,
    depth: int = 0,
) -> list[dict[str, Any]]:
    """Fetch one group's elements in one tile; on failure retry as four smaller tiles."""
    query = build_query(
        config.selectors_for_group(group), tile, timeout_s=timeout_s, geometry=geometry
    )
    try:
        payload = client.fetch(label, query)
    except OverpassError as exc:
        if depth >= MAX_SPLIT_DEPTH:
            raise
        logger.warning("%s failed (%s); splitting into 4 sub-tiles", label, exc)
        merged: list[dict[str, Any]] = []
        for index, sub in enumerate(tile.tiles(2, 2)):
            merged += fetch_tile(
                client,
                config,
                group,
                sub,
                f"{label}-s{index}",
                geometry=geometry,
                timeout_s=timeout_s,
                depth=depth + 1,
            )
        return merged
    elements = payload.get("elements", [])
    return elements if isinstance(elements, list) else []


def fetch_group(
    client: OverpassClient,
    config: OsmTagConfig,
    group: str,
    bbox: BBox,
    rows: int,
    cols: int,
    *,
    city_key: str,
    geometry: bool,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a group over the whole ``bbox`` and return de-duplicated elements."""
    tiles = bbox.tiles(rows, cols)
    merged: list[dict[str, Any]] = []
    for number, tile in enumerate(tiles, start=1):
        label = f"{city_key}-{group}-t{number:02d}of{len(tiles):02d}"
        merged += fetch_tile(client, config, group, tile, label, geometry=geometry)
        if on_progress is not None:
            on_progress(group, number, len(tiles))
    return list(_dedupe(merged))


def _dedupe(elements: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    for element in elements:
        key = (element.get("type"), element.get("id"))
        if key not in seen:
            seen.add(key)
            yield element
