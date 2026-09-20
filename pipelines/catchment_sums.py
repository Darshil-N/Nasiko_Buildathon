"""Fast numpy aggregation over cell catchments (plan step 3.8).

``pipelines.catchments`` yields shared-contract ``POIRow`` objects, which is convenient but slow
for millions of rows. This module computes the same catchments (each cell's H3 k-ring) with plain
arrays: one distance vector per cell and vectorised decay sums per POI category. Its results are
checked against the scoring library's own per-POI functions in the tests.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import h3
import numpy as np
import numpy.typing as npt

from pipelines.catchments import haversine_many_m
from pipelines.grid import GridCell, point_to_cell
from pipelines.normalise import PoiRecord

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class PoiArrays:
    """All POIs as parallel arrays, plus an index from H3 cell to POI positions."""

    lat: FloatArray
    lon: FloatArray
    category_code: IntArray
    categories: tuple[str, ...]  # code -> category name
    cell_of_poi: tuple[str, ...]  # h3 index of each POI (cells outside the city included)
    by_cell: dict[str, IntArray]

    @classmethod
    def from_pois(cls, pois: Sequence[PoiRecord], resolution: int) -> PoiArrays:
        """Index ``pois`` (any order) by category code and containing cell."""
        categories = tuple(sorted({p.category for p in pois}))
        code = {name: i for i, name in enumerate(categories)}
        cells = tuple(point_to_cell(p.lat, p.lon, resolution) for p in pois)
        groups: dict[str, list[int]] = defaultdict(list)
        for position, cell in enumerate(cells):
            groups[cell].append(position)
        return cls(
            lat=np.array([p.lat for p in pois], dtype=np.float64),
            lon=np.array([p.lon for p in pois], dtype=np.float64),
            category_code=np.array([code[p.category] for p in pois], dtype=np.int64),
            categories=categories,
            cell_of_poi=cells,
            by_cell={c: np.array(v, dtype=np.int64) for c, v in groups.items()},
        )

    def codes_for(self, names: Sequence[str]) -> IntArray:
        """Category codes for the names that exist in this dataset (unknown names are skipped)."""
        known = {n: i for i, n in enumerate(self.categories)}
        return np.array([known[n] for n in names if n in known], dtype=np.int64)


@dataclass(frozen=True)
class Catchment:
    """POI positions inside one cell's k-ring and their distances (metres) from its centroid."""

    idx: IntArray
    dist: FloatArray


def compute_catchments(cells: Sequence[GridCell], arrays: PoiArrays, k: int) -> list[Catchment]:
    """The k-ring catchment of every cell, in the order of ``cells``."""
    if k < 0:
        raise ValueError("k must be >= 0")
    empty = Catchment(np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64))
    result: list[Catchment] = []
    for cell in cells:
        parts = [arrays.by_cell[c] for c in h3.grid_disk(cell.h3_index, k) if c in arrays.by_cell]
        if not parts:
            result.append(empty)
            continue
        idx = np.concatenate(parts)
        dist = haversine_many_m(cell.lat, cell.lon, arrays.lat[idx], arrays.lon[idx])
        result.append(Catchment(idx, dist))
    return result


def decay_sums(
    catchments: Sequence[Catchment], arrays: PoiArrays, decay_lambda_m: float
) -> FloatArray:
    """Matrix ``(cells x categories)`` of ``sum(exp(-d / lambda))`` over each catchment."""
    if decay_lambda_m <= 0:
        raise ValueError("decay_lambda_m must be > 0")
    n_categories = len(arrays.categories)
    out = np.zeros((len(catchments), n_categories), dtype=np.float64)
    for row, catchment in enumerate(catchments):
        if catchment.idx.size:
            out[row] = np.bincount(
                arrays.category_code[catchment.idx],
                weights=np.exp(-catchment.dist / decay_lambda_m),
                minlength=n_categories,
            )
    return out
