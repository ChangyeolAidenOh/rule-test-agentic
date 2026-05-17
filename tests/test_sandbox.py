"""Tests for sandbox module - import checker and executor."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandbox.import_checker import check_imports
from sandbox.executor import run_tests


class TestImportChecker:
    """Test AST-based import validation."""

    def test_allowed_imports_pass(self):
        code = "from decimal import Decimal\nimport math\nimport datetime"
        is_safe, violations = check_imports(code)
        assert is_safe
        assert violations == []

    def test_disallowed_import_os(self):
        code = "import os\nfrom decimal import Decimal"
        is_safe, violations = check_imports(code)
        assert not is_safe
        assert len(violations) == 1
        assert "os" in violations[0]

    def test_disallowed_import_subprocess(self):
        code = "import subprocess"
        is_safe, violations = check_imports(code)
        assert not is_safe

    def test_disallowed_import_requests(self):
        code = "import requests"
        is_safe, violations = check_imports(code)
        assert not is_safe

    def test_syntax_error(self):
        code = "def broken(:\n    pass"
        is_safe, violations = check_imports(code)
        assert not is_safe
        assert "Syntax error" in violations[0]

    def test_empty_code(self):
        code = ""
        is_safe, violations = check_imports(code)
        assert is_safe
        assert violations == []


class TestSandboxExecutor:
    """Test sandbox execution with subprocess."""

    def test_passing_code_and_tests(self):
        code = (
            "from decimal import Decimal\n\n"
            "def apply_rule(x: int) -> int:\n"
            "    return x * 2\n"
        )
        tests = (
            "from generated_module import apply_rule\n\n"
            "def test_normal_double():\n"
            "    assert apply_rule(5) == 10\n\n"
            "def test_normal_zero():\n"
            "    assert apply_rule(0) == 0\n"
        )
        result = run_tests(code, tests)
        assert result["success"]
        assert result["import_safe"]
        assert len(result["results"]) == 2
        assert all(r["passed"] for r in result["results"])

    def test_failing_test(self):
        code = "def apply_rule(x): return x + 1\n"
        tests = (
            "from generated_module import apply_rule\n\n"
            "def test_wrong():\n"
            "    assert apply_rule(5) == 100\n"
        )
        result = run_tests(code, tests)
        assert not result["success"]
        assert len(result["results"]) >= 1

    def test_import_violation_blocked(self):
        code = "import os\ndef apply_rule(): return os.getcwd()\n"
        tests = "from generated_module import apply_rule\ndef test_it(): apply_rule()\n"
        result = run_tests(code, tests)
        assert not result["success"]
        assert not result["import_safe"]
        assert len(result["import_violations"]) > 0
