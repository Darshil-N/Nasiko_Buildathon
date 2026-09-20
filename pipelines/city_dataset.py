"""Assemble downloaded OSM data into one in-memory dataset for a city (plan steps 1.3-1.5).

``build_dataset`` reads ``data/raw/osm/<city>/latest/<group>.json`` and returns cells, cell
attributes and classified POIs. It never touches a database or the network, so it doubles as the
dry run that is shown to the owner before any data is loaded.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipelines.attributes import (
    CellAttributeRow,
    build_cell_attributes,
    landuse_polygons,
    place_points,
    poi_counts_by_cell,
    road_lines,
)
from pipelines.boundary import area_km2, load_boundary
from pipelines.city_config import CityConfig
from pipelines.grid import GridCell, describe_cell, point_to_cell, polyfill
from pipelines.normalise import PoiRecord, normalise_elements
from pipelines.osm_config import OsmTagConfig

ATTRIBUTE_GROUPS = ("landuse", "roads", "places")


class MissingDataError(RuntimeError):
    """Raised when a required downloaded group is not on disk yet."""


@dataclass(frozen=True)
class CityDataset:
    """Everything derived for one city, ready to inspect or load."""

    city: CityConfig
    boundary_km2: float
    cells: list[GridCell]
    attributes: list[CellAttributeRow]
    pois: list[PoiRecord]
    poi_cells: list[
        str | None
    ]  # parallel to ``pois``: containing cell, or None if outside the city
    fetched_at: dict[str, str]  # group -> ISO timestamp of its download


def read_group(raw_dir: Path, group: str) -> tuple[list[dict[str, Any]], str]:
    """Return the elements and download timestamp of one group.

    Raises:
        MissingDataError: if the group has not been downloaded.
    """
    path = raw_dir / f"{group}.json"
    if not path.exists():
        raise MissingDataError(f"group {group!r} not downloaded yet ({path})")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["elements"]), str(payload.get("fetched_at", ""))


def build_dataset(city: CityConfig, tags: OsmTagConfig, raw_dir: Path) -> CityDataset:
    """Build the dataset for ``city`` from downloaded groups in ``raw_dir``.

    Raises:
        MissingDataError: listing every group that is not downloaded yet.
    """
    needed = [*tags.groups("poi"), *ATTRIBUTE_GROUPS]
    missing = [g for g in needed if not (raw_dir / f"{g}.json").exists()]
    if missing:
        raise MissingDataError(f"not downloaded yet: {', '.join(missing)}")

    boundary = load_boundary(city.boundary_file)
    cell_ids = polyfill(boundary, city.h3_resolution)
    cells = [describe_cell(c) for c in cell_ids]
    centroids = {c.h3_index: (c.lat, c.lon) for c in cells}
    ref_lat = (boundary.bounds[1] + boundary.bounds[3]) / 2

    fetched_at: dict[str, str] = {}
    pois: dict[tuple[str, int], PoiRecord] = {}
    for group in tags.groups("poi"):
        elements, stamp = read_group(raw_dir, group)
        fetched_at[group] = stamp
        for poi in normalise_elements(elements, tags):
            pois.setdefault((poi.osm_type, poi.osm_id), poi)
    poi_list = sorted(pois.values(), key=lambda p: (p.osm_type, p.osm_id))

    geometry: dict[str, list[dict[str, Any]]] = {}
    for group in ATTRIBUTE_GROUPS:
        geometry[group], fetched_at[group] = read_group(raw_dir, group)

    id_set = set(cell_ids)
    counts = poi_counts_by_cell(poi_list, id_set, city.h3_resolution)
    attributes = build_cell_attributes(
        cell_ids,
        centroids,
        polygons=landuse_polygons(geometry["landuse"], tags),
        roads=road_lines(geometry["roads"], tags),
        places=place_points(geometry["places"], tags),
        poi_counts=counts,
        ref_lat=ref_lat,
    )
    poi_cells = [
        cell if (cell := point_to_cell(p.lat, p.lon, city.h3_resolution)) in id_set else None
        for p in poi_list
    ]
    return CityDataset(
        city=city,
        boundary_km2=area_km2(boundary),
        cells=cells,
        attributes=attributes,
        pois=poi_list,
        poi_cells=poi_cells,
        fetched_at=fetched_at,
    )


def qa_summary(dataset: CityDataset) -> Mapping[str, Any]:
    """Counts a human can sanity-check before anything is loaded (plan step 1.6.3)."""
    attrs = dataset.attributes
    by_category = Counter(p.category for p in dataset.pois)
    inside = sum(1 for c in dataset.poi_cells if c is not None)
    return {
        "city": dataset.city.name,
        "boundary_km2": round(dataset.boundary_km2),
        "cells": len(dataset.cells),
        "pois_total": len(dataset.pois),
        "pois_inside_city_cells": inside,
        "pois_in_buffer_only": len(dataset.pois) - inside,
        "pois_by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "cells_without_any_poi": len(dataset.cells) - len({c for c in dataset.poi_cells if c}),
        "cells_with_locality": sum(1 for a in attrs if a.locality_name),
        "distinct_localities": len({a.locality_name for a in attrs if a.locality_name}),
        "cells_with_main_road": sum(1 for a in attrs if a.main_road_dist_m is not None),
        "land_use_counts": dict(Counter(a.land_use for a in attrs)),
        "cells_with_any_landuse_polygon": sum(
            1
            for a in attrs
            if a.landuse_residential_share + a.landuse_commercial_share + a.landuse_retail_share > 0
        ),
        "downloaded_at": dict(sorted(dataset.fetched_at.items())),
    }
