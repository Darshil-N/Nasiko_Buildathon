"""Typed loader for ``config/osm_tags.yaml`` and the OSM-tag classifier built on it."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

DEFAULT_PATH = Path("config/osm_tags.yaml")

Kind = Literal["poi", "area", "line", "place"]


class Selector(BaseModel):
    """One OSM tag filter: ``key=value`` (exact) or ``key`` (tag exists)."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: str | None = None

    @classmethod
    def parse(cls, text: str) -> Selector:
        """Parse ``"amenity=school"`` or ``"office"``."""
        key, sep, value = text.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"empty tag key in selector {text!r}")
        return cls(key=key, value=value.strip() if sep else None)

    def matches(self, tags: Mapping[str, str]) -> bool:
        """Return True if ``tags`` satisfy this selector."""
        if self.key not in tags:
            return False
        return self.value is None or tags[self.key] == self.value

    def overpass(self) -> str:
        """Render as an Overpass tag filter, e.g. ``["amenity"="school"]``."""
        if self.value is None:
            return f'["{self.key}"]'
        return f'["{self.key}"="{self.value}"]'


class CategoryRule(BaseModel):
    """An internal category and the OSM selectors that define it."""

    model_config = ConfigDict(frozen=True)

    name: str
    group: str
    kind: Kind
    selectors: tuple[Selector, ...]

    def matches(self, tags: Mapping[str, str]) -> bool:
        """True if any selector matches (selectors are OR-ed)."""
        return any(s.matches(tags) for s in self.selectors)


class OsmTagConfig(BaseModel):
    """The whole tag mapping, with categories in classification-priority order."""

    model_config = ConfigDict(frozen=True)

    version: str
    keep_tags: tuple[str, ...]
    categories: tuple[CategoryRule, ...]

    @model_validator(mode="after")
    def _unique_names(self) -> OsmTagConfig:
        names = [c.name for c in self.categories]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate categories: {sorted(dupes)}")
        return self

    def classify(self, tags: Mapping[str, str], kind: Kind = "poi") -> str | None:
        """Return the first category of ``kind`` whose selectors match ``tags``, else None."""
        for rule in self.categories:
            if rule.kind == kind and rule.matches(tags):
                return rule.name
        return None

    def groups(self, kind: Kind = "poi") -> list[str]:
        """Group names of the given kind, in first-appearance order."""
        seen: dict[str, None] = {}
        for rule in self.categories:
            if rule.kind == kind:
                seen.setdefault(rule.group)
        return list(seen)

    def selectors_for_group(self, group: str) -> Iterator[Selector]:
        """Yield the distinct selectors of every category in ``group``."""
        emitted: set[Selector] = set()
        for rule in self.categories:
            if rule.group == group:
                for selector in rule.selectors:
                    if selector not in emitted:
                        emitted.add(selector)
                        yield selector

    def filter_tags(self, tags: Mapping[str, str]) -> dict[str, str]:
        """Keep only the tags listed in ``keep_tags``."""
        return {k: v for k, v in tags.items() if k in self.keep_tags}


class _RawCategory(BaseModel):
    group: str
    kind: Kind = "poi"
    selectors: list[str]

    @field_validator("selectors")
    @classmethod
    def _non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("a category needs at least one selector")
        return value


class _RawConfig(BaseModel):
    version: str
    keep_tags: list[str]
    categories: dict[str, _RawCategory]


def load_osm_tags(path: Path = DEFAULT_PATH) -> OsmTagConfig:
    """Load and validate the OSM tag mapping.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        pydantic.ValidationError: if the YAML does not match the expected shape.
    """
    raw = _RawConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    rules = tuple(
        CategoryRule(
            name=name,
            group=cat.group,
            kind=cat.kind,
            selectors=tuple(Selector.parse(s) for s in cat.selectors),
        )
        for name, cat in raw.categories.items()
    )
    return OsmTagConfig(version=raw.version, keep_tags=tuple(raw.keep_tags), categories=rules)
