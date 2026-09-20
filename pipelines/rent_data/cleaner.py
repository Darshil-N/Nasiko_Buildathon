"""Cleaning and validation logic for listings (step 2.1.3)."""

from typing import Any

import pandas as pd
from pydantic import ValidationError

from pipelines.rent_data.schemas import RawListing


def parse_and_validate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Parse CSV rows into RawListing models, catching invalid rows."""
    valid_rows = []
    rejected_rows = []

    for idx, row in df.iterrows():
        try:
            listing = RawListing(**row.to_dict())  # type: ignore[arg-type]
            # Normalise price to monthly for rent
            if listing.type == "rent" and listing.period == "yearly":
                listing.price_inr = listing.price_inr / 12.0
                listing.period = "monthly"
            valid_rows.append(listing.model_dump())
        except ValidationError as e:
            rejected_rows.append({"index": idx, "reason": "validation", "details": str(e)})

    return pd.DataFrame(valid_rows), rejected_rows


def reject_outliers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Reject prices beyond 5 standard deviations of the locality median."""
    if df.empty:
        return df, []

    rejected = []

    # Calculate median and std per locality and type
    stats = (
        df.groupby(["locality", "type", "property_type"])["price_inr"]
        .agg(["median", "std"])
        .reset_index()
    )
    # Fill NaN std (groups with 1 item) with infinity so they are never rejected
    stats["std"] = stats["std"].fillna(float("inf"))

    merged = df.merge(stats, on=["locality", "type", "property_type"], how="left")

    # A price is valid if std is inf (single item), or if it's within 5 stds of median
    # If std is 0 (all same price), any deviation is 0 which is within 5*0
    mask = (merged["std"] == float("inf")) | (
        abs(merged["price_inr"] - merged["median"]) <= 5 * merged["std"]
    )

    valid_df = df[mask].copy()
    outlier_df = df[~mask]

    for idx, row in outlier_df.iterrows():
        rejected.append(
            {
                "index": idx,
                "reason": "outlier",
                "details": (
                    f"Price {row['price_inr']} is outside 5 std devs " f"of median {row['median']}"
                ),
            }
        )

    return valid_df, rejected


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Remove exact duplicates based on key fields."""
    if df.empty:
        return df, []

    subset = ["type", "property_type", "price_inr", "area_sqft", "locality"]

    # Identify duplicates (keeping the first)
    duplicates_mask = df.duplicated(subset=subset, keep="first")

    valid_df = df[~duplicates_mask].copy()
    duplicates_df = df[duplicates_mask]

    rejected = []
    for idx, _ in duplicates_df.iterrows():
        rejected.append(
            {
                "index": idx,
                "reason": "duplicate",
                "details": "Exact match on type, property_type, price, area, and locality.",
            }
        )

    return valid_df, rejected


def clean_listings(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Run the full cleaning pipeline: validate -> deduplicate -> outliers."""
    if df.empty:
        return df, []

    df, rejected_validation = parse_and_validate(df)
    df, rejected_dups = deduplicate(df)
    df, rejected_outliers = reject_outliers(df)

    return df, rejected_validation + rejected_dups + rejected_outliers
