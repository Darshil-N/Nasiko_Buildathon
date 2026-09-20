"""City boundary: load a saved GeoJSON polygon, measure it, and derive a download bounding box."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from pipelines.geo import BBox, LocalProjection

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "SiteScout-MVP/0.1 (personal hackathon project; single lookup)"


class BoundaryError(RuntimeError):
    """Raised when a boundary cannot be loaded or does not match what was requested."""


def load_boundary(path: Path) -> BaseGeometry:
    """Load a Polygon or MultiPolygon from a GeoJSON file (Feature or bare geometry)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    geometry = data.get("geometry", data) if isinstance(data, dict) else None
    if not isinstance(geometry, dict):
        raise BoundaryError(f"{path} does not contain a GeoJSON geometry")
    geom = shape(geometry)
    if geom.geom_type not in {"Polygon", "MultiPolygon"} or geom.is_empty:
        raise BoundaryError(f"{path} must contain a non-empty Polygon or MultiPolygon")
    if not geom.is_valid:
        geom = _polygonal_part(shapely.make_valid(geom))
    return geom


def _polygonal_part(geom: BaseGeometry) -> BaseGeometry:
    """Keep only the polygons of a repaired geometry (make_valid may add stray lines/points)."""
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in {"Polygon", "MultiPolygon"}]
    if not parts:
        raise BoundaryError("boundary has no polygonal area after repair")
    return shapely.union_all(parts)


def area_km2(geom: BaseGeometry) -> float:
    """Approximate area in square kilometres using a local equirectangular projection."""
    _, min_lat, _, max_lat = geom.bounds
    projection = LocalProjection((min_lat + max_lat) / 2)
    metres_per_deg_lon, _ = projection.xy(0.0, 1.0)  # x for one degree of longitude
    _, metres_per_deg_lat = projection.xy(1.0, 0.0)  # y for one degree of latitude
    scale = np.array([metres_per_deg_lon, metres_per_deg_lat])
    projected = shapely.transform(geom, lambda coords: coords * scale)
    return float(projected.area) / 1_000_000.0


def city_bbox(geom: BaseGeometry, buffer_m: float = 0.0) -> BBox:
    """Bounding box of ``geom`` grown by ``buffer_m`` metres on every side."""
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    box = BBox(min_lat, min_lon, max_lat, max_lon)
    return box.expanded(buffer_m) if buffer_m > 0 else box


def fetch_nominatim_boundary(
    query: str,
    osm_type: str,
    osm_id: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Look up a boundary polygon on Nominatim and return it as a GeoJSON Feature.

    One request, identified by a User-Agent, as the usage policy requires. The result is only
    accepted if it is the exact OSM object that was asked for.

    Raises:
        BoundaryError: if no result matches ``osm_type`` and ``osm_id``.
    """
    http = client or httpx.Client(timeout=60, headers={"User-Agent": NOMINATIM_USER_AGENT})
    response = http.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "polygon_geojson": 1, "limit": 5},
    )
    response.raise_for_status()
    for hit in response.json():
        if hit.get("osm_type") == osm_type and hit.get("osm_id") == osm_id and "geojson" in hit:
            return {
                "type": "Feature",
                "properties": {"osm_type": osm_type, "osm_id": osm_id, "query": query},
                "geometry": hit["geojson"],
            }
    raise BoundaryError(f"no {osm_type}/{osm_id} in Nominatim results for {query!r}")
