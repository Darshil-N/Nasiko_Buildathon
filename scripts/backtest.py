"""Back-testing CLI for evaluating scoring models (step 7.2.1)."""

import argparse
import json
from pathlib import Path

# Note: In a real run, this would load cells, score them, and compare
# against expected_ranking from data/backtest/*.json


def run_backtest(category: str, data_dir: Path) -> None:
    """Run back-test for a category."""
    case_file = data_dir / f"{category}_cases.json"
    if not case_file.exists():
        print(f"No back-test cases found for {category} at {case_file}.")
        return

    with open(case_file, encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Running back-test for {category} ({len(cases)} cases)...")

    # Fake implementation for now
    hit_count = 0
    total = len(cases)

    for _case in cases:
        # Score the city, get the rank of case["zone_name"]
        # If in top 3, hit_count += 1
        pass

    hit_rate = (hit_count / total) * 100 if total > 0 else 0
    print(f"Top-3 hit rate: {hit_rate:.1f}%")
    print("Pass: False")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scoring back-tests.")
    parser.add_argument("--category", default="all", help="Category to test (or 'all')")
    parser.add_argument("--data-dir", default="data/backtest", help="Directory containing cases")

    args = parser.parse_args()
    data_path = Path(args.data_dir)

    categories = ["cafe", "clothing", "pharmacy"] if args.category == "all" else [args.category]

    for cat in categories:
        run_backtest(cat, data_path)
