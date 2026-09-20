"""Tests for the OSM tag configuration loader and classifier."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pipelines.osm_config import CategoryRule, OsmTagConfig, Selector, load_osm_tags


@pytest.fixture(scope="module")
def config() -> OsmTagConfig:
    return load_osm_tags(Path("config/osm_tags.yaml"))


def test_selector_parse_exact_and_exists() -> None:
    assert Selector.parse("amenity=school") == Selector(key="amenity", value="school")
    assert Selector.parse("office") == Selector(key="office", value=None)
    with pytest.raises(ValueError, match="empty tag key"):
        Selector.parse("=school")


def test_selector_overpass_rendering() -> None:
    assert Selector.parse("amenity=school").overpass() == '["amenity"="school"]'
    assert Selector.parse("office").overpass() == '["office"]'


def test_all_appendix_a_categories_present(config: OsmTagConfig) -> None:
    names = {c.name for c in config.categories}
    expected = {
        "school", "college", "university", "mall", "department_store", "supermarket",
        "marketplace", "hospital", "clinic", "doctors", "diagnostic_lab", "pharmacy", "cafe",
        "restaurant", "clothes", "boutique", "shoes", "jewelry", "tailor", "bank", "atm",
        "bus_stop", "rail_or_metro", "place_of_worship", "cinema", "gym", "park", "coworking",
        "office", "parking", "car_showroom", "hotel", "residential_building",
    }  # fmt: skip
    assert expected <= names


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"amenity": "cafe", "name": "X"}, "cafe"),
        ({"amenity": "coworking_space"}, "coworking"),
        ({"office": "coworking"}, "coworking"),  # specific beats the generic office rule
        ({"office": "it"}, "office"),
        ({"shop": "boutique"}, "boutique"),
        ({"shop": "clothes"}, "clothes"),
        ({"railway": "station"}, "rail_or_metro"),
        ({"public_transport": "station"}, "rail_or_metro"),
        ({"building": "apartments"}, "residential_building"),
        ({"amenity": "unknown_thing"}, None),
        ({}, None),
    ],
)
def test_classify_poi(config: OsmTagConfig, tags: dict[str, str], expected: str | None) -> None:
    assert config.classify(tags) == expected


def test_classify_area_is_separate_from_poi(config: OsmTagConfig) -> None:
    assert config.classify({"landuse": "residential"}, kind="area") == "landuse_residential"
    assert config.classify({"landuse": "residential"}, kind="poi") is None


def test_groups_and_selectors(config: OsmTagConfig) -> None:
    assert "health" in config.groups("poi")
    assert config.groups("area") == ["landuse"]
    health = {s.overpass() for s in config.selectors_for_group("health")}
    assert '["amenity"="pharmacy"]' in health
    assert '["healthcare"="laboratory"]' in health


def test_filter_tags_drops_unlisted_keys(config: OsmTagConfig) -> None:
    kept = config.filter_tags({"name": "A", "amenity": "cafe", "phone": "123", "brand": "B"})
    assert kept == {"name": "A", "brand": "B"}


def test_category_without_selectors_is_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text(
        'version: "x"\nkeep_tags: [name]\ncategories:\n  a: {group: g, selectors: []}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="at least one selector"):
        load_osm_tags(empty)


def test_duplicate_category_names_are_rejected() -> None:
    rule = CategoryRule(name="a", group="g", kind="poi", selectors=(Selector.parse("k=v"),))
    with pytest.raises(ValidationError, match="duplicate categories"):
        OsmTagConfig(version="x", keep_tags=("name",), categories=(rule, rule))
