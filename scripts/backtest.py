"""Back-testing CLI for evaluating scoring models (step 7.2.1)."""

import argparse
import os
import time
from typing import Any

import httpx

API_URL = "http://localhost:8000/v1"


def _headers() -> dict[str, str]:
    api_key = os.environ.get("BACKEND_API_KEY")
    if not api_key:
        raise SystemExit("Set BACKEND_API_KEY in the environment before running this script.")
    return {"X-API-Key": api_key, "X-User-Id": "backtest"}


def run_analysis(category: str, tier: str = "premium") -> dict[str, Any]:
    payload = {
        "city": "bengaluru",
        "category": category,
        "tier": tier,
        "constraints": {},
        "top_n": 10,
    }
    print(f"\n--- Running Analysis for {category} ({tier}) ---")

    with httpx.Client(base_url=API_URL, headers=_headers(), timeout=60.0) as client:
        # Create analysis
        try:
            resp = client.post("/analyses", json=payload)
            resp.raise_for_status()
            analysis_id = resp.json()["analysis_id"]
        except Exception as e:
            print(f"Failed to create analysis: {e}")
            if "resp" in locals():
                print(resp.text)
            return {}

        print(f"Created analysis {analysis_id}. Polling...")

        # Poll
        for _ in range(30):
            try:
                status_resp = client.get(f"/analyses/{analysis_id}")
                status_resp.raise_for_status()
                data: dict[str, Any] = status_resp.json()
                if data.get("status") == "done":
                    return data
                elif data.get("status") == "failed":
                    print("Analysis failed.")
                    return {}
            except Exception as e:
                print(f"Failed during polling: {e}")
                return {}
            time.sleep(1.0)

        print("Timeout waiting for analysis.")
        return {}


def run_backtest(category: str) -> None:
    """Run back-test for a category by creating an analysis on the live backend."""
    start_time = time.time()

    # Run a premium tier analysis
    result = run_analysis(category, tier="premium")
    if not result:
        return

    latency = time.time() - start_time

    recs = result.get("recommendations", [])
    print(f"\nTop Recommendations for {category.upper()} (Latency: {latency:.2f}s):")

    conf_sum = 0.0
    for i, rec in enumerate(recs[:10], start=1):
        zone = rec.get("zone_name", "Unknown")
        score = rec.get("score", 0.0)
        conf = rec.get("confidence", 0.0)
        conf_sum += conf
        drivers = rec.get("top_drivers", [])

        print(f"{i}. {zone} (Score: {score:.1f}, Conf: {conf:.2f})")
        if drivers:
            print(f"   Drivers: {', '.join(drivers[:2])}")

    avg_conf = conf_sum / len(recs) if recs else 0.0
    print(f"\nAverage Confidence of Top {len(recs)}: {avg_conf:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scoring back-tests against the live backend.")
    parser.add_argument("--category", default="all", help="Category to test (or 'all')")

    args = parser.parse_args()
    categories = ["cafe", "clothing", "pharmacy"] if args.category == "all" else [args.category]

    for cat in categories:
        run_backtest(cat)
