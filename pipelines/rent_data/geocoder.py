"""Geocoder client (steps 2.2.1 - 2.2.3)."""
# ruff: noqa: T201

import time
from functools import lru_cache
from typing import Any

import h3
import httpx
import pandas as pd


@lru_cache(maxsize=1024)
def geocode_locality(locality: str, city: str = "Pune") -> tuple[float, float] | None:
    """Geocode a locality using Nominatim (cached)."""
    # Respect Nominatim rate limit (~1 req/s)
    time.sleep(1.1)

    query = f"{locality}, {city}, India"
    url = "https://nominatim.openstreetmap.org/search"

    headers = {"User-Agent": "SiteScout/1.0 (internal test)"}
    params: dict[str, str | int] = {"q": query, "format": "json", "limit": 1}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed for {query}: {e}")

    return None


def assign_cells(df: pd.DataFrame, city: str = "Pune") -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Geocode and assign H3 indices (step 2.2.3)."""
    unassignable = []

    def process_row(row: pd.Series) -> pd.Series:
        if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
            row["precision"] = "exact"
            row["h3_index"] = h3.latlng_to_cell(row["lat"], row["lon"], 9)
        else:
            coords = geocode_locality(row["locality"], city)
            if coords:
                row["lat"], row["lon"] = coords
                row["precision"] = "locality"
                row["h3_index"] = h3.latlng_to_cell(coords[0], coords[1], 9)
            else:
                row["precision"] = None
                row["h3_index"] = None
        return row

    if df.empty:
        return df, []

    df = df.apply(process_row, axis=1)

    mask = df["h3_index"].isna()
    unassignable_df = df[mask]

    for idx, row in unassignable_df.iterrows():
        unassignable.append(
            {"index": idx, "locality": row["locality"], "reason": "Geocoding failed"}
        )

    valid_df = df[~mask].copy()
    return valid_df, unassignable
