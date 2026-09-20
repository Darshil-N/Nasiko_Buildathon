"""Per-cell attributes derived from OSM geometry (plan steps 1.3.3, 1.5.1, 1.5.2, 1.5.4).

* land-use shares: how much of each cell is residential, commercial or retail land;
* distance to, and class of, the nearest main road;
* a locality name from the nearest named place point;
* a coarse ``land_use`` class for the cell (decision D-30, all thresholds are constants below).

Everything here is pure computation on already-downloaded elements; no network, no database.
Distances and areas use the local projection in ``pipelines.geo`` (accurate to well under 1 %
over a city).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

from pipelines.geo import LocalProjection
from pipelines.grid import cell_polygon, point_to_cell
from pipelines.normalise import PoiRecord, element_point
from pipelines.osm_config import OsmTagConfig

# --- tunable constants (decision D-30; easy to change) ---------------------------------------
LANDUSE_SHARE_MIN = 0.25  # share of a cell that makes it "residential" or "commercial" land
POI_COUNT_MIN = 3  # POIs (or residential buildings) in a cell that make it commercial / residential
LOCALITY_MAX_M = 3000.0  # a place point further than this does not name a cell

COMMERCIAL_POI_CATEGORIES = frozenset(
    {
        "mall", "department_store", "supermarket", "marketplace", "boutique", "clothes", "shoes",
        "jewelry", "tailor", "car_showroom", "cafe", "restaurant", "bank", "atm", "office",
        "coworking",
    }
)  # fmt: skip
RESIDENTIAL_POI_CATEGORY = "residential_building"


@dataclass(frozen=True)
class LandUsePolygon:
    """A land-use area: ``kind`` is ``residential``, ``commercial`` or ``retail``."""

    kind: str
    polygon: BaseGeometry  # lon/lat


@dataclass(frozen=True)
class RoadLine:
    """A main road segment: ``road_class`` is ``trunk``, ``primary`` or ``secondary``."""

    road_class: str
    line: LineString  # lon/lat


@dataclass(frozen=True)
class PlacePoint:
    """A named locality point (suburb, neighbourhood or quarter)."""

    name: str
    lat: float
    lon: float
    place_type: str


@dataclass(frozen=True)
class CellAttributeRow:
    """Derived facts for one cell, ready to load into ``cell_attributes`` and ``cells``."""

    h3_index: str
    landuse_residential_share: float
    landuse_commercial_share: float
    landuse_retail_share: float
    main_road_dist_m: float | None
    main_road_class: str | None
    locality_name: str | None
    land_use: str


# --- parsing OSM elements into shapely geometry -----------------------------------------------
def _ring(geometry: Sequence[Mapping[str, float]]) -> list[tuple[float, float]]:
    return [(float(p["lon"]), float(p["lat"])) for p in geometry]


def _repair(geom: BaseGeometry) -> BaseGeometry | None:
    """Return a valid polygonal geometry, or None if nothing polygonal is left."""
    if geom.is_empty:
        return None
    if not geom.is_valid:
        geom = shapely.make_valid(geom)
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in {"Polygon", "MultiPolygon"}]
    return unary_union(parts) if parts else None


def _element_polygons(element: Mapping[str, Any]) -> list[BaseGeometry]:
    """Polygons of a closed way, or of a relation's outer rings (holes are ignored)."""
    if element.get("type") == "way":
        ring = _ring(element.get("geometry") or [])
        if len(ring) >= 4 and ring[0] == ring[-1]:
            repaired = _repair(Polygon(ring))
            return [repaired] if repaired is not None else []
        return []
    if element.get("type") == "relation":
        outers = [
            LineString(_ring(m["geometry"]))
            for m in element.get("members") or []
            if m.get("role") == "outer" and len(m.get("geometry") or []) >= 2
        ]
        if not outers:
            return []
        return [p for p in polygonize(unary_union(outers)) if not p.is_empty]
    return []


def landuse_polygons(
    elements: Iterable[Mapping[str, Any]], config: OsmTagConfig
) -> list[LandUsePolygon]:
    """Extract land-use polygons (kinds without the ``landuse_`` prefix)."""
    result: list[LandUsePolygon] = []
    for element in elements:
        category = config.classify(element.get("tags") or {}, kind="area")
        if category is None:
            continue
        kind = category.removeprefix("landuse_")
        result += [LandUsePolygon(kind, poly) for poly in _element_polygons(element)]
    return result


def road_lines(elements: Iterable[Mapping[str, Any]], config: OsmTagConfig) -> list[RoadLine]:
    """Extract main-road lines (classes without the ``road_`` prefix)."""
    result: list[RoadLine] = []
    for element in elements:
        category = config.classify(element.get("tags") or {}, kind="line")
        coords = _ring(element.get("geometry") or []) if element.get("type") == "way" else []
        if category is not None and len(coords) >= 2:
            result.append(RoadLine(category.removeprefix("road_"), LineString(coords)))
    return result


def place_points(elements: Iterable[Mapping[str, Any]], config: OsmTagConfig) -> list[PlacePoint]:
    """Extract named place points; unnamed places and elements without a location are skipped."""
    result: list[PlacePoint] = []
    for element in elements:
        tags = element.get("tags") or {}
        category = config.classify(tags, kind="place")
        point = element_point(element)
        name = tags.get("name")
        if category is not None and point is not None and name:
            result.append(PlacePoint(name, point[0], point[1], category.removeprefix("place_")))
    return result


# --- metric helpers ----------------------------------------------------------------------------
def _scale(projection: LocalProjection) -> np.ndarray:
    x_per_deg, _ = projection.xy(0.0, 1.0)
    _, y_per_deg = projection.xy(1.0, 0.0)
    return np.array([x_per_deg, y_per_deg])


def _to_metres(geom: BaseGeometry, scale: np.ndarray) -> BaseGeometry:
    return shapely.transform(geom, lambda coords: coords * scale)


# --- land-use shares ---------------------------------------------------------------------------
def landuse_shares(
    cells: Iterable[str], polygons: Sequence[LandUsePolygon], ref_lat: float
) -> dict[str, dict[str, float]]:
    """Share (0..1) of each cell covered by each land-use kind.

    Polygons of one kind are merged first, so overlapping mapping never counts an area twice.
    """
    scale = _scale(LocalProjection(ref_lat))
    trees: dict[str, tuple[STRtree, np.ndarray]] = {}
    for kind in {p.kind for p in polygons}:
        merged = unary_union([p.polygon for p in polygons if p.kind == kind])
        parts = shapely.get_parts(_to_metres(merged, scale))
        trees[kind] = (STRtree(parts), parts)

    result: dict[str, dict[str, float]] = {}
    for cell in cells:
        cell_m = _to_metres(cell_polygon(cell), scale)
        shares = {"residential": 0.0, "commercial": 0.0, "retail": 0.0}
        for kind, (tree, parts) in trees.items():
            covered = sum(cell_m.intersection(parts[i]).area for i in tree.query(cell_m))
            shares[kind] = min(1.0, covered / cell_m.area)
        result[cell] = shares
    return result


# --- nearest main road -------------------------------------------------------------------------
def nearest_roads(
    centroids: Mapping[str, tuple[float, float]], roads: Sequence[RoadLine], ref_lat: float
) -> dict[str, tuple[float, str] | None]:
    """Distance in metres and class of the nearest main road for each cell centroid (lat, lon)."""
    if not roads:
        return dict.fromkeys(centroids)
    scale = _scale(LocalProjection(ref_lat))
    lines = np.array([_to_metres(r.line, scale) for r in roads], dtype=object)
    tree = STRtree(lines)
    ids = list(centroids)
    points = shapely.points(np.array([[centroids[c][1], centroids[c][0]] for c in ids]) * scale)
    pairs, distances = tree.query_nearest(points, return_distance=True, all_matches=False)
    out: dict[str, tuple[float, str] | None] = dict.fromkeys(ids)
    for point_idx, road_idx, dist in zip(pairs[0], pairs[1], distances, strict=True):
        out[ids[int(point_idx)]] = (float(dist), roads[int(road_idx)].road_class)
    return out


# --- locality names ----------------------------------------------------------------------------
def assign_localities(
    centroids: Mapping[str, tuple[float, float]],
    places: Sequence[PlacePoint],
    ref_lat: float,
    max_m: float = LOCALITY_MAX_M,
) -> dict[str, str | None]:
    """Name each cell after the nearest place point within ``max_m`` metres, else None."""
    ids = list(centroids)
    if not places or not ids:
        return dict.fromkeys(ids)
    projection = LocalProjection(ref_lat)
    place_xy = np.array([projection.xy(p.lat, p.lon) for p in places])
    cell_xy = np.array([projection.xy(*centroids[c]) for c in ids])
    result: dict[str, str | None] = {}
    for start in range(0, len(ids), 1000):  # chunked so memory stays small for big cities
        block = cell_xy[start : start + 1000]
        dist = np.linalg.norm(block[:, None, :] - place_xy[None, :, :], axis=2)
        nearest = dist.argmin(axis=1)
        for offset, idx in enumerate(nearest):
            within = dist[offset, idx] <= max_m
            result[ids[start + offset]] = places[int(idx)].name if within else None
    return result


# --- POI counts and the land-use class ---------------------------------------------------------
def poi_counts_by_cell(
    pois: Iterable[PoiRecord], cell_ids: set[str], resolution: int
) -> dict[str, Counter[str]]:
    """Count POIs per (cell, category); POIs outside the city's cells are ignored."""
    counts: dict[str, Counter[str]] = {}
    for poi in pois:
        cell = point_to_cell(poi.lat, poi.lon, resolution)
        if cell in cell_ids:
            counts.setdefault(cell, Counter())[poi.category] += 1
    return counts


def classify_land_use(shares: Mapping[str, float], poi_counts: Mapping[str, int]) -> str:
    """Coarse land-use class of a cell from land-use shares and POI counts (decision D-30)."""
    commercial_pois = sum(poi_counts.get(c, 0) for c in COMMERCIAL_POI_CATEGORIES)
    commercial = (
        shares.get("commercial", 0.0) + shares.get("retail", 0.0) >= LANDUSE_SHARE_MIN
        or commercial_pois >= POI_COUNT_MIN
    )
    residential = (
        shares.get("residential", 0.0) >= LANDUSE_SHARE_MIN
        or poi_counts.get(RESIDENTIAL_POI_CATEGORY, 0) >= POI_COUNT_MIN
    )
    if commercial and residential:
        return "mixed"
    if commercial:
        return "commercial"
    if residential:
        return "residential"
    return "other"


def build_cell_attributes(
    cell_ids: Sequence[str],
    centroids: Mapping[str, tuple[float, float]],
    *,
    polygons: Sequence[LandUsePolygon],
    roads: Sequence[RoadLine],
    places: Sequence[PlacePoint],
    poi_counts: Mapping[str, Mapping[str, int]],
    ref_lat: float,
) -> list[CellAttributeRow]:
    """Combine every attribute computation into one row per cell, in ``cell_ids`` order."""
    shares = landuse_shares(cell_ids, polygons, ref_lat)
    roads_by_cell = nearest_roads(centroids, roads, ref_lat)
    names = assign_localities(centroids, places, ref_lat)
    rows: list[CellAttributeRow] = []
    for cell in cell_ids:
        s = shares[cell]
        road = roads_by_cell[cell]
        rows.append(
            CellAttributeRow(
                h3_index=cell,
                landuse_residential_share=round(s["residential"], 4),
                landuse_commercial_share=round(s["commercial"], 4),
                landuse_retail_share=round(s["retail"], 4),
                main_road_dist_m=round(road[0], 1) if road else None,
                main_road_class=road[1] if road else None,
                locality_name=names[cell],
                land_use=classify_land_use(s, poi_counts.get(cell, {})),
            )
        )
    return rows
