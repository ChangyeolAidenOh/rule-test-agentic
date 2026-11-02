"""Evaluation metrics for the agentic coding pipeline."""

from core.state import PipelineState


def _fidelity_breakdown(fidelity_results: list[dict]) -> dict:
    """Fidelity overall, by condition source, and by judging method."""

    def is_faithful(r: dict) -> bool:
        # v2 results carry `verdict`; v1 results only have implemented/correct.
        if "verdict" in r:
            return r["verdict"] == "faithful"
        return bool(r.get("implemented") and r.get("correct"))

    total = len(fidelity_results)
    faithful = sum(1 for r in fidelity_results if is_faithful(r))

    rule_conds = [r for r in fidelity_results if r.get("source") == "rule"]
    rule_faithful = sum(1 for r in rule_conds if is_faithful(r))

    method_counts: dict[str, int] = {}
    for r in fidelity_results:
        m = r.get("method", "llm_v1")
        method_counts[m] = method_counts.get(m, 0) + 1

    return {
        "total_conditions": total,
        "faithful_conditions": faithful,
        "rule_conditions": len(rule_conds),
        "rule_faithful_conditions": rule_faithful,
        "fidelity_rule_score": (
            round(rule_faithful / len(rule_conds), 4) if rule_conds else None
        ),
        "fidelity_method_counts": method_counts,
        "undetermined_conditions": sum(
            1 for r in fidelity_results if r.get("verdict") == "undetermined"
        ),
    }


def compute_metrics(state: PipelineState) -> dict:
    """Compute evaluation metrics from a completed pipeline run."""
    test_results = state.get("test_results", [])
    compliance_flags = state.get("compliance_flags", [])
    fix_attempt = state.get("fix_attempt", 0)

    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r.get("passed"))

    # First-pass success: did it pass all tests on the first attempt?
    first_pass_success = fix_attempt == 0 and state.get("all_tests_passed", False)

    # Final success rate
    final_success = state.get("all_tests_passed", False)

    # Self-fix convergence
    self_fix_count = fix_attempt

    # Test coverage by category (parsed from test_id naming convention)
    categories = {"normal": 0, "boundary": 0, "exception": 0, "error": 0}
    for r in test_results:
        test_id = r.get("test_id", "").lower()
        for cat in categories:
            if cat in test_id:
                categories[cat] += 1
                break

    # Compliance risk flags
    critical_flags = sum(
        1 for f in compliance_flags if f.get("severity") == "critical"
    )
    warning_flags = sum(
        1 for f in compliance_flags if f.get("severity") == "warning"
    )

    # Business Rule Fidelity
    fidelity_results = state.get("fidelity_results", [])
    fidelity = _fidelity_breakdown(fidelity_results)

    return {
        "scenario_id": state.get("scenario_id", ""),
        "complexity": state.get("complexity", ""),
        "first_pass_success": first_pass_success,
        "final_success": final_success,
        "self_fix_count": self_fix_count,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "test_pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
        "test_coverage_by_category": categories,
        "critical_flags": critical_flags,
        "warning_flags": warning_flags,
        "total_flags": len(compliance_flags),
        "fidelity_score": state.get("fidelity_score", 0.0),
        **fidelity,
        "fidelity_results": fidelity_results,
        "status": state.get("status", "unknown"),
    }
