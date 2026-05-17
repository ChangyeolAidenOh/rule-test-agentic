"""Sandbox executor - run generated code + tests in isolated temp directory."""

import json
import os
import subprocess
import tempfile

from config.settings import SANDBOX_TIMEOUT_SECONDS
from sandbox.import_checker import check_imports


def run_tests(generated_code: str, test_code: str) -> dict:
    """Execute generated code and tests in a sandboxed temp directory.

    Returns:
        {
            "success": bool,
            "import_safe": bool,
            "import_violations": [...],
            "test_output": str,
            "return_code": int,
            "results": [
                {"test_id": str, "passed": bool, "error_message": str}
            ]
        }
    """
    # Step 1: Import safety check
    code_safe, code_violations = check_imports(generated_code)
    test_extra = {"generated_module", "pytest"}
    test_safe, test_violations = check_imports(test_code, extra_allowed=test_extra)

    all_violations = code_violations + test_violations
    if not (code_safe and test_safe):
        return {
            "success": False,
            "import_safe": False,
            "import_violations": all_violations,
            "test_output": "Import check failed",
            "return_code": -1,
            "results": [],
        }

    # Step 2: Write files to temp directory and run pytest
    with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
        module_path = os.path.join(tmpdir, "generated_module.py")
        test_path = os.path.join(tmpdir, "test_generated.py")
        result_path = os.path.join(tmpdir, "test_results.json")

        with open(module_path, "w") as f:
            f.write(generated_code)

        with open(test_path, "w") as f:
            f.write(test_code)

        # Run pytest with JSON report
        cmd = [
            "python", "-m", "pytest",
            test_path,
            "-v",
            "--tb=short",
            f"--rootdir={tmpdir}",
            "--no-header",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT_SECONDS,
                cwd=tmpdir,
                env={**os.environ, "PYTHONPATH": tmpdir},
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "import_safe": True,
                "import_violations": [],
                "test_output": f"Timeout: execution exceeded {SANDBOX_TIMEOUT_SECONDS}s",
                "return_code": -2,
                "results": [],
            }

        output = proc.stdout + proc.stderr
        results = _parse_pytest_output(output)

        all_passed = all(r["passed"] for r in results) if results else False

        return {
            "success": all_passed,
            "import_safe": True,
            "import_violations": [],
            "test_output": output,
            "return_code": proc.returncode,
            "results": results,
        }


def _parse_pytest_output(output: str) -> list[dict]:
    """Parse pytest verbose output into structured results."""
    results = []
    for line in output.split("\n"):
        line = line.strip()
        if " PASSED" in line:
            test_name = line.split(" PASSED")[0].strip()
            # Remove file path prefix
            if "::" in test_name:
                test_name = test_name.split("::")[-1]
            results.append({
                "test_id": test_name,
                "passed": True,
                "error_message": "",
            })
        elif " FAILED" in line:
            test_name = line.split(" FAILED")[0].strip()
            if "::" in test_name:
                test_name = test_name.split("::")[-1]
            results.append({
                "test_id": test_name,
                "passed": False,
                "error_message": _extract_error(output, test_name),
            })
    return results


def _extract_error(full_output: str, test_name: str) -> str:
    """Extract error details for a specific failed test."""
    lines = full_output.split("\n")
    capturing = False
    error_lines = []
    for line in lines:
        if test_name in line and "FAILED" in line:
            capturing = True
            continue
        if capturing:
            if line.startswith("FAILED") or line.startswith("="):
                break
            error_lines.append(line)

    # Fallback: return all stderr-like content
    if not error_lines:
        for line in lines:
            if "Error" in line or "assert" in line.lower():
                error_lines.append(line)

    return "\n".join(error_lines[:20])
