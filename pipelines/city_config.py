"""Typed loader for ``config/cities/<city>.yaml``."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class CityConfig(BaseModel):
    """Everything the ingestion pipeline needs to know about one city."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    state: str | None = None
    country: str = "IN"
    osm_relation_id: int = Field(gt=0)
    boundary_file: Path
    h3_resolution: int = Field(default=9, ge=0, le=15)
    fetch_buffer_m: float = Field(default=1500.0, ge=0)
    tile_rows: int = Field(default=3, ge=1)
    tile_cols: int = Field(default=3, ge=1)


def load_city(path: Path) -> CityConfig:
    """Load and validate a city definition.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        pydantic.ValidationError: if the file does not match the schema.
    """
    return CityConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
