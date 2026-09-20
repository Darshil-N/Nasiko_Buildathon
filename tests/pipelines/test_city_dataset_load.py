"""Tests for the dataset builder and the database loader (the loader is tested with a fake
connection, so no database is touched)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pipelines import db_load
from pipelines.city_config import CityConfig, load_city
from pipelines.city_dataset import (
    ATTRIBUTE_GROUPS,
    CityDataset,
    MissingDataError,
    build_dataset,
    qa_summary,
)
from pipelines.grid import describe_cell, point_to_cell
from pipelines.osm_config import OsmTagConfig, load_osm_tags

CENTRE = (12.9716, 77.5946)  # central Bengaluru


@pytest.fixture(scope="module")
def tags() -> OsmTagConfig:
    return load_osm_tags(Path("config/osm_tags.yaml"))


@pytest.fixture(scope="module")
def city() -> CityConfig:
    return load_city(Path("config/cities/bengaluru.yaml"))


def node(osm_id: int, lat: float, lon: float, **tags: str) -> dict[str, Any]:
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": tags}


def write_group(raw_dir: Path, group: str, elements: list[dict[str, Any]]) -> None:
    payload = {"group": group, "fetched_at": "2026-09-20T12:00:00+00:00", "elements": elements}
    (raw_dir / f"{group}.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory: pytest.TempPathFactory, tags: OsmTagConfig) -> Path:
    """A tiny synthetic download around central Bengaluru: 4 POIs, 1 place, 1 road."""
    directory = tmp_path_factory.mktemp("raw")
    lat, lon = CENTRE
    for group in tags.groups("poi"):
        write_group(directory, group, [])
    write_group(
        directory,
        "food",
        [
            node(1, lat, lon, amenity="cafe", name="A"),
            node(2, lat, lon, amenity="cafe", name="B"),
            node(3, lat, lon, amenity="restaurant"),
            node(9, 13.5, 77.0, amenity="cafe"),  # far outside the city
        ],
    )
    write_group(directory, "landuse", [])
    write_group(
        directory,
        "roads",
        [
            {
                "type": "way",
                "id": 100,
                "tags": {"highway": "primary"},
                "geometry": [
                    {"lat": lat + 0.01, "lon": lon - 0.02},
                    {"lat": lat + 0.01, "lon": lon + 0.02},
                ],
            }
        ],
    )
    write_group(directory, "places", [node(200, lat, lon, place="suburb", name="Centre")])
    return directory


@pytest.fixture(scope="module")
def dataset(city: CityConfig, tags: OsmTagConfig, raw_dir: Path) -> CityDataset:
    return build_dataset(city, tags, raw_dir)


def test_missing_groups_are_reported_together(
    city: CityConfig, tags: OsmTagConfig, tmp_path: Path
) -> None:
    write_group(tmp_path, "food", [])
    with pytest.raises(MissingDataError) as excinfo:
        build_dataset(city, tags, tmp_path)
    message = str(excinfo.value)
    assert "health" in message
    assert all(g in message for g in ATTRIBUTE_GROUPS)
    assert "food" not in message


def test_dataset_cells_and_pois(dataset: CityDataset) -> None:
    assert 6000 < len(dataset.cells) < 7600
    assert len(dataset.attributes) == len(dataset.cells)
    assert [p.osm_id for p in dataset.pois] == [1, 2, 3, 9]  # sorted, de-duplicated
    centre_cell = point_to_cell(*CENTRE, 9)
    assert dataset.poi_cells == [centre_cell, centre_cell, centre_cell, None]  # far POI is outside


def test_dataset_attributes_for_the_centre_cell(dataset: CityDataset) -> None:
    centre_cell = point_to_cell(*CENTRE, 9)
    row = next(a for a in dataset.attributes if a.h3_index == centre_cell)
    assert row.locality_name == "Centre"
    assert row.land_use == "commercial"  # three commercial POIs (2 cafes + 1 restaurant)
    assert row.main_road_class == "primary"
    centroid_lat = describe_cell(centre_cell).lat
    expected_m = (CENTRE[0] + 0.01 - centroid_lat) * 110_574  # road is 0.01 degree north of CENTRE
    assert row.main_road_dist_m == pytest.approx(expected_m, rel=0.01)


def test_qa_summary_counts(dataset: CityDataset) -> None:
    report = qa_summary(dataset)
    assert report["pois_total"] == 4
    assert report["pois_inside_city_cells"] == 3
    assert report["pois_in_buffer_only"] == 1
    assert report["pois_by_category"] == {"cafe": 3, "restaurant": 1}
    assert report["cells_with_locality"] > 0
    assert report["distinct_localities"] == 1
    assert report["land_use_counts"]["commercial"] == 1


# --- loader (fake connection) ------------------------------------------------------------------
class FakeResult:
    def scalar_one(self) -> int:
        return 7


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, statement: Any, params: Any = None) -> FakeResult:
        self.calls.append((str(statement).split()[2], params))  # the table name after INSERT INTO
        return FakeResult()


def test_load_dataset_runs_statements_in_dependency_order(
    dataset: CityDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_load, "BATCH_SIZE", 3000)
    conn = FakeConnection()
    counts = db_load.load_dataset(conn, dataset, "POLYGON((0 0, 1 0, 1 1, 0 0))", "v1")  # type: ignore[arg-type]
    order = [name for name, _ in conn.calls]
    assert order[0] == "cities"
    assert order.index("cells") < order.index("cell_attributes") < order.index("pois")
    assert order[-1] == "ingest_jobs"
    assert counts == {"cells": len(dataset.cells), "cell_attributes": len(dataset.cells), "pois": 4}
    # every cell/POI row got the city id returned by the city upsert
    cell_calls = [p for name, p in conn.calls if name == "cells"]
    assert all(row["city_id"] == 7 for batch in cell_calls for row in batch)


def test_loader_batches_large_inputs(dataset: CityDataset, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_load, "BATCH_SIZE", 2500)
    conn = FakeConnection()
    db_load.load_dataset(conn, dataset, "POLYGON((0 0, 1 0, 1 1, 0 0))", "v1")  # type: ignore[arg-type]
    cell_batches = [p for name, p in conn.calls if name == "cells"]
    assert len(cell_batches) == -(-len(dataset.cells) // 2500)
    assert sum(len(b) for b in cell_batches) == len(dataset.cells)


def test_row_builders_produce_valid_parameters(dataset: CityDataset) -> None:
    cells = db_load.cell_rows(dataset.cells[:2], dataset.attributes[:2], city_id=1)
    assert cells[0]["boundary_wkt"].startswith("POLYGON((")
    assert cells[0]["boundary_wkt"].count(",") == 6  # closed ring of 7 points
    pois = db_load.poi_rows(dataset.pois, dataset.poi_cells, city_id=1)
    assert pois[-1]["h3_index"] is None  # outside the city
    assert json.loads(pois[0]["tags"])["name"] == "A"
    attrs = db_load.attribute_rows(dataset.attributes[:1], "v1")
    assert attrs[0]["source_version"] == "v1"


def test_cell_geometry_matches_h3(dataset: CityDataset) -> None:
    sample = dataset.cells[0]
    assert describe_cell(sample.h3_index).boundary == sample.boundary


def test_upsert_statements_are_idempotent_by_construction() -> None:
    for statement in (
        db_load.UPSERT_CITY,
        db_load.UPSERT_CELL,
        db_load.UPSERT_ATTRIBUTES,
        db_load.UPSERT_POI,
    ):
        assert "ON CONFLICT" in str(statement)
