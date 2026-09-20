"""Scoring CLI (step 3.9.3) to test scoring outside the pipeline."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from scoring.score import ScoreEngine
from shared.config import load_category_config
from shared.contracts import CellFeatures


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Test scoring for a single cell feature payload.")
    parser.add_argument("category", help="Category to score against (e.g. cafe, clothing)")
    parser.add_argument("tier", help="Tier to score against (e.g. premium, mid, budget)")
    parser.add_argument(
        "payload_file", help="Path to JSON file containing CellFeatures. Use '-' for stdin."
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_category_config(args.category)
    except Exception as e:
        print(f"Failed to load config for '{args.category}': {e}", file=sys.stderr)
        sys.exit(1)

    # Read payload
    try:
        if args.payload_file == "-":
            data = json.load(sys.stdin)
        else:
            data = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read payload: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse cell features
    try:
        features = CellFeatures.model_validate(data)
    except ValidationError as e:
        print(f"Invalid CellFeatures payload: {e}", file=sys.stderr)
        sys.exit(1)

    # Score
    # Score
    engine = ScoreEngine(config, args.tier)
    zone_scores = engine.rank([features])
    zone_score = zone_scores[0]

    # Print results
    print("\n--- SCORING RESULT ---")
    print(f"Category: {args.category} | Tier: {args.tier}")
    print(f"Score:    {zone_score.score:.1f} / 100")
    if zone_score.excluded:
        print(f"Status:   EXCLUDED ({zone_score.exclusion_reason})")
    elif zone_score.greyed:
        print(f"Status:   GREYED (low confidence: {zone_score.confidence:.2f})")
    else:
        print(f"Confidence: {zone_score.confidence:.2f}")

    print("\nContributions:")
    for key, val in zone_score.contributions.items():
        print(f"  {key}: {val:+.1f}")

    print("\nTop Drivers:")
    for d in zone_score.top_drivers:
        print(f"  + {d}")

    print("\nTop Risks:")
    for r in zone_score.top_risks:
        print(f"  - {r}")


if __name__ == "__main__":
    run_cli()
