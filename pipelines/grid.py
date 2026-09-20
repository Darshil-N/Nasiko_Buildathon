"""H3 grid helpers: cover a city polygon with cells and describe each cell."""

from __future__ import annotations

from dataclasses import dataclass

import h3
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class GridCell:
    """One H3 cell: its index, centroid and boundary ring (lon, lat order, closed)."""

    h3_index: str
    lat: float
    lon: float
    boundary: tuple[tuple[float, float], ...]


def polyfill(geom: BaseGeometry, resolution: int) -> list[str]:
    """Return the H3 cells whose centres fall inside ``geom`` (Polygon or MultiPolygon).

    The result is sorted so repeated runs are identical (idempotent ingestion).
    """
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"expected a Polygon or MultiPolygon, got {geom.geom_type}")
    return sorted(h3.geo_to_cells(geom, resolution))


def point_to_cell(lat: float, lon: float, resolution: int) -> str:
    """H3 index of the cell containing the point."""
    return str(h3.latlng_to_cell(lat, lon, resolution))


def describe_cell(h3_index: str) -> GridCell:
    """Centroid and closed boundary ring (lon, lat) of a cell."""
    lat, lon = h3.cell_to_latlng(h3_index)
    ring = [(lng, la) for la, lng in h3.cell_to_boundary(h3_index)]
    ring.append(ring[0])
    return GridCell(h3_index, lat, lon, tuple(ring))


def cell_polygon(h3_index: str) -> Polygon:
    """The cell boundary as a shapely Polygon in (lon, lat)."""
    return Polygon(describe_cell(h3_index).boundary)
