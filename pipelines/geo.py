"""Small geometry helpers shared by the ingestion pipeline (no external projection library).

Distances use a local equirectangular approximation around a reference latitude. Over a city
(tens of kilometres) the error is well under one percent, which is enough for cell-level features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class BBox:
    """A latitude/longitude bounding box in degrees (south < north, west < east)."""

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        if not (self.south < self.north and self.west < self.east):
            raise ValueError(f"degenerate bbox: {self}")
        if not (self.south >= -90 and self.north <= 90 and self.west >= -180 and self.east <= 180):
            raise ValueError(f"bbox out of range: {self}")

    def overpass(self) -> str:
        """Render as Overpass ``(south,west,north,east)`` text."""
        return f"{self.south:.6f},{self.west:.6f},{self.north:.6f},{self.east:.6f}"

    def contains(self, lat: float, lon: float) -> bool:
        """True if the point lies inside or on the edge of the box."""
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def tiles(self, rows: int, cols: int) -> list[BBox]:
        """Split into ``rows * cols`` equal tiles, ordered south-to-north then west-to-east."""
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        dlat = (self.north - self.south) / rows
        dlon = (self.east - self.west) / cols
        return [
            BBox(
                self.south + r * dlat,
                self.west + c * dlon,
                self.south + (r + 1) * dlat,
                self.west + (c + 1) * dlon,
            )
            for r in range(rows)
            for c in range(cols)
        ]

    def expanded(self, metres: float) -> BBox:
        """Grow the box by ``metres`` on every side (clamped to valid coordinates)."""
        mid_lat = (self.south + self.north) / 2
        dlat = metres / metres_per_degree_lat()
        dlon = metres / metres_per_degree_lon(mid_lat)
        return BBox(
            max(-90.0, self.south - dlat),
            max(-180.0, self.west - dlon),
            min(90.0, self.north + dlat),
            min(180.0, self.east + dlon),
        )


def metres_per_degree_lat() -> float:
    """Metres in one degree of latitude."""
    return math.pi * EARTH_RADIUS_M / 180.0


def metres_per_degree_lon(lat: float) -> float:
    """Metres in one degree of longitude at latitude ``lat`` (degrees)."""
    return metres_per_degree_lat() * math.cos(math.radians(lat))


@dataclass(frozen=True)
class LocalProjection:
    """Project (lat, lon) degrees to local (x, y) metres around a reference latitude."""

    ref_lat: float

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        """Return ``(x_east_m, y_north_m)`` for a point."""
        return lon * metres_per_degree_lon(self.ref_lat), lat * metres_per_degree_lat()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two points given in degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
