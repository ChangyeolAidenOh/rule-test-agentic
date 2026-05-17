"""Batch evaluation runner for all scenarios."""

import json
import os
import time

from core.graph import run_pipeline
from evaluation.metrics import compute_metrics
from scenarios.definitions import get_all_scenarios


def run_all_scenarios(output_dir: str = "results") -> list[dict]:
    """Run pipeline on all scenarios and compute metrics."""
    os.makedirs(output_dir, exist_ok=True)
    scenarios = get_all_scenarios()
    all_results = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        print(f"Running {sid} ({scenario['complexity']})...")
        start = time.time()

        try:
            final_state = run_pipeline(
                raw_rule=scenario["raw_rule"],
                scenario_id=sid,
                complexity=scenario["complexity"],
            )
            metrics = compute_metrics(final_state)
            elapsed = time.time() - start
            metrics["elapsed_seconds"] = round(elapsed, 2)

            # Save individual result
            result_path = os.path.join(output_dir, f"{sid}_result.json")
            with open(result_path, "w") as f:
                json.dump(
                    {"metrics": metrics, "state": _serialize_state(final_state)},
                    f, indent=2, ensure_ascii=False, default=str,
                )
            print(f"  {sid} done in {elapsed:.1f}s - {'PASS' if metrics['final_success'] else 'FAIL'}")
        except Exception as e:
            metrics = {
                "scenario_id": sid,
                "complexity": scenario["complexity"],
                "status": "error",
                "error": str(e),
            }
            print(f"  {sid} error: {e}")

        all_results.append(metrics)

    # Save summary
    summary_path = os.path.join(output_dir, "evaluation_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSummary saved to {summary_path}")

    return all_results


def _serialize_state(state: dict) -> dict:
    """Make state JSON-serializable."""
    serializable = {}
    for key, value in state.items():
        try:
            json.dumps(value, default=str)
            serializable[key] = value
        except (TypeError, ValueError):
            serializable[key] = str(value)
    return serializable


if __name__ == "__main__":
    results = run_all_scenarios()
    print("\n=== Evaluation Summary ===")
    for r in results:
        sid = r.get("scenario_id", "?")
        status = r.get("status", "unknown")
        fix = r.get("self_fix_count", 0)
        print(f"  {sid}: {status} (self-fix: {fix}x)")
