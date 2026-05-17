"""Node 4: Test Runner - execute tests and manage self-fix loop."""

from config.settings import MAX_SELF_FIX_ATTEMPTS
from core.state import PipelineState
from sandbox.executor import run_tests


def test_runner(state: PipelineState) -> dict:
    """Run tests in sandbox. On failure, prepare state for self-fix."""
    generated_code = state["generated_code"]
    test_code = state["test_code"]
    fix_attempt = state.get("fix_attempt", 0)
    fix_history = list(state.get("fix_history", []))

    result = run_tests(generated_code, test_code)

    test_results = [
        {
            "test_id": r["test_id"],
            "passed": r["passed"],
            "error_message": r["error_message"],
            "stdout": "",
        }
        for r in result["results"]
    ]

    if result["success"]:
        return {
            "test_results": test_results,
            "all_tests_passed": True,
            "fix_attempt": fix_attempt,
            "fix_history": fix_history,
            "status": "tests_passed",
        }

    # Build error summary for self-fix
    error_summary = _build_error_summary(result)

    fix_history.append({
        "attempt": fix_attempt + 1,
        "error": error_summary,
        "previous_code": generated_code,
        "fixed_code": "",
    })

    new_attempt = fix_attempt + 1
    if new_attempt >= MAX_SELF_FIX_ATTEMPTS:
        status = "manual_required"
    else:
        status = "fix_needed"

    return {
        "test_results": test_results,
        "all_tests_passed": False,
        "fix_attempt": new_attempt,
        "fix_history": fix_history,
        "status": status,
    }


def _build_error_summary(result: dict) -> str:
    """Build a concise error summary for the code generator."""
    parts = []

    if not result["import_safe"]:
        parts.append("Import violations:")
        for v in result["import_violations"]:
            parts.append(f"  - {v}")
        return "\n".join(parts)

    if result["return_code"] == -2:
        return "Execution timed out (exceeded sandbox timeout limit)"

    failed = [r for r in result["results"] if not r["passed"]]
    if failed:
        parts.append(f"{len(failed)} test(s) failed:")
        for f in failed:
            parts.append(f"  - {f['test_id']}: {f['error_message']}")

    # Include raw output for context
    if result["test_output"]:
        parts.append("\nFull test output (last 50 lines):")
        lines = result["test_output"].strip().split("\n")
        parts.extend(lines[-50:])

    return "\n".join(parts)
