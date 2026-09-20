"""Rent and price estimation logic (step 2.3)."""

import h3
import pandas as pd


def estimate_cell_rent(df: pd.DataFrame, h3_index: str) -> tuple[float | None, bool]:
    """Estimate rent for a specific cell (step 2.3.1).

    Returns (rent_sqft, rent_is_estimated).
    """
    if df.empty:
        return None, False

    rent_df = df[df["type"] == "rent"].copy()
    if rent_df.empty:
        return None, False

    # Rent per sqft
    rent_df["rent_sqft"] = rent_df["price_inr"] / rent_df["area_sqft"]

    # Check own cell
    cell_rent = rent_df[rent_df["h3_index"] == h3_index]
    if len(cell_rent) >= 3:
        return cell_rent["rent_sqft"].mean(), False

    # k-ring fallback
    disk = h3.grid_disk(h3_index, 2)
    nearby = rent_df[rent_df["h3_index"].isin(disk)].copy()

    if nearby.empty:
        return None, False

    # Inverse distance weighting (simple)
    nearby["distance"] = nearby["h3_index"].apply(lambda h: h3.grid_distance(h3_index, h))
    # Add small epsilon to avoid div by zero
    nearby["weight"] = 1.0 / (nearby["distance"] + 0.1)

    weighted_sum = (nearby["rent_sqft"] * nearby["weight"]).sum()
    total_weight = nearby["weight"].sum()

    return weighted_sum / total_weight, True


def estimate_locality_price(df: pd.DataFrame, locality: str) -> float | None:
    """Aggregate residential price by locality (step 2.3.2)."""
    if df.empty:
        return None

    sale_df = df[(df["type"] == "sale") & (df["property_type"] == "residential")].copy()
    if sale_df.empty:
        return None

    loc_sales = sale_df[sale_df["locality"] == locality]
    if loc_sales.empty:
        return None

    loc_sales["price_sqft"] = loc_sales["price_inr"] / loc_sales["area_sqft"]
    return float(loc_sales["price_sqft"].median())


def compute_coverage(df: pd.DataFrame, cells: list[str]) -> dict[str, float]:
    """Compute listing and price coverage metrics (step 2.3.3)."""
    if df.empty or not cells:
        return {"listing_coverage": 0.0, "price_coverage": 0.0}

    rent_cells = set(df[df["type"] == "rent"]["h3_index"].dropna())
    sale_cells = set(df[df["type"] == "sale"]["h3_index"].dropna())

    listing_cov = len(rent_cells.intersection(cells)) / len(cells)
    price_cov = len(sale_cells.intersection(cells)) / len(cells)

    return {"listing_coverage": min(1.0, listing_cov), "price_coverage": min(1.0, price_cov)}
