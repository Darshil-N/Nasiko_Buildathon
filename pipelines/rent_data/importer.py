"""Importer CLI for rent CSV (step 2.1.4)."""
# ruff: noqa: T201

import argparse
import sys

import pandas as pd

from pipelines.rent_data.cleaner import clean_listings


def run_import(csv_path: str, dry_run: bool = False) -> None:
    """Run the CSV importer."""
    print(f"Reading {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    print(f"Loaded {len(df)} raw rows. Cleaning...")
    valid_df, rejected = clean_listings(df)

    print(f"Accepted: {len(valid_df)}")
    print(f"Rejected: {len(rejected)}")

    if rejected:
        print("\nRejection samples:")
        for r in rejected[:5]:
            print(f"  Row {r['index']}: {r['reason']} - {r['details']}")
        if len(rejected) > 5:
            print(f"  ... and {len(rejected) - 5} more.")

    if dry_run:
        print("\nDry run complete. Nothing was written.")
        return

    print("\nDatabase persistence not yet implemented.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import rent/price CSV listings.")
    parser.add_argument("csv_path", help="Path to the listings CSV")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to database")

    args = parser.parse_args()
    run_import(args.csv_path, args.dry_run)
