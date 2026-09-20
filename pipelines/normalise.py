"""Turn raw Overpass elements into clean, classified point-of-interest records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pipelines.osm_config import OsmTagConfig


@dataclass(frozen=True)
class PoiRecord:
    """A classified OSM point of interest (nodes as-is, ways and relations at their centre)."""

    osm_type: str
    osm_id: int
    category: str
    lat: float
    lon: float
    name: str | None = None
    brand: str | None = None
    tags: dict[str, str] = field(default_factory=dict)


def element_point(element: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return (lat, lon) for a node, or the ``center`` of a way or relation; None if unknown."""
    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        center = element.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
    if isinstance(lat, int | float) and isinstance(lon, int | float):
        return float(lat), float(lon)
    return None


def normalise_elements(
    elements: Iterable[Mapping[str, Any]], config: OsmTagConfig
) -> list[PoiRecord]:
    """Classify elements as POIs, dropping unclassified or location-less ones.

    Elements are de-duplicated on ``(osm_type, osm_id)`` because ways that cross a map-tile
    edge are returned by both tiles. The output is sorted for reproducibility.
    """
    seen: dict[tuple[str, int], PoiRecord] = {}
    for element in elements:
        osm_type, osm_id = element.get("type"), element.get("id")
        tags: Mapping[str, str] = element.get("tags") or {}
        if not isinstance(osm_type, str) or not isinstance(osm_id, int):
            continue
        category = config.classify(tags, kind="poi")
        point = element_point(element)
        if category is None or point is None or (osm_type, osm_id) in seen:
            continue
        kept = config.filter_tags(tags)
        seen[(osm_type, osm_id)] = PoiRecord(
            osm_type=osm_type,
            osm_id=osm_id,
            category=category,
            lat=point[0],
            lon=point[1],
            name=kept.get("name"),
            brand=kept.get("brand"),
            tags=kept,
        )
    return sorted(seen.values(), key=lambda p: (p.osm_type, p.osm_id))
