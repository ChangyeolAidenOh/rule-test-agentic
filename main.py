"""Main entry point for the insurance agentic dev pipeline."""

import argparse
import json
import sys

from core.graph import run_pipeline
from evaluation.metrics import compute_metrics
from evaluation.runner import run_all_scenarios
from scenarios.definitions import get_all_scenarios, get_scenario


def run_single(scenario_id: str) -> None:
    """Run pipeline on a single scenario."""
    scenario = get_scenario(scenario_id)
    print(f"Running scenario {scenario_id}: {scenario['description']}")
    print(f"Complexity: {scenario['complexity']}")
    print(f"Rule: {scenario['raw_rule']}")
    print("-" * 60)

    final_state = run_pipeline(
        raw_rule=scenario["raw_rule"],
        scenario_id=scenario_id,
        complexity=scenario["complexity"],
    )

    metrics = compute_metrics(final_state)
    print(f"\nStatus: {final_state.get('status')}")
    print(f"Tests passed: {metrics['passed_tests']}/{metrics['total_tests']}")
    print(f"Self-fix attempts: {metrics['self_fix_count']}")
    print(f"Compliance flags: {metrics['total_flags']}")
    print(f"Business Rule Fidelity: {metrics['fidelity_score']:.0%} ({metrics['faithful_conditions']}/{metrics['total_conditions']} conditions)")

    if final_state.get("generated_code"):
        print(f"\n--- Generated Code ---\n{final_state['generated_code']}")

    if final_state.get("documentation"):
        print(f"\n--- Documentation ---\n{final_state['documentation']}")


def run_custom(rule_text: str) -> None:
    """Run pipeline on a custom business rule."""
    print(f"Running custom rule: {rule_text}")
    print("-" * 60)

    final_state = run_pipeline(
        raw_rule=rule_text,
        scenario_id="custom",
        complexity="custom",
    )

    metrics = compute_metrics(final_state)
    print(f"\nStatus: {final_state.get('status')}")
    print(f"Tests passed: {metrics['passed_tests']}/{metrics['total_tests']}")


def main():
    parser = argparse.ArgumentParser(
        description="Insurance Rule-to-Test Agentic Coding PoC"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Single scenario
    single_parser = subparsers.add_parser("run", help="Run a single scenario")
    single_parser.add_argument("scenario_id", help="Scenario ID (S1-S5)")

    # Batch evaluation
    subparsers.add_parser("eval", help="Run all scenarios for evaluation")

    # Custom rule
    custom_parser = subparsers.add_parser("custom", help="Run a custom rule")
    custom_parser.add_argument("rule", help="Business rule text")

    # List scenarios
    subparsers.add_parser("list", help="List all scenarios")

    args = parser.parse_args()

    if args.command == "run":
        run_single(args.scenario_id)
    elif args.command == "eval":
        run_all_scenarios()
    elif args.command == "custom":
        run_custom(args.rule)
    elif args.command == "list":
        for s in get_all_scenarios():
            print(f"  {s['scenario_id']} [{s['complexity']}] {s['raw_rule']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
