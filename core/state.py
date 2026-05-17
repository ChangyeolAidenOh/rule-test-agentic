"""LangGraph state definition for the 6-node pipeline."""

from dataclasses import dataclass, field
from typing import TypedDict


class RuleSpec(TypedDict, total=False):
    """Structured business rule specification (Node 1 output)."""
    rule_id: str
    title: str
    description: str
    conditions: list[dict]
    calculations: list[dict]
    edge_cases: list[dict]
    constraints: list[str]


class TestCase(TypedDict, total=False):
    """Individual test case (Node 3 output)."""
    test_id: str
    category: str  # normal, boundary, exception, error
    description: str
    input_params: dict
    expected_output: dict
    assertion_type: str


class TestResult(TypedDict, total=False):
    """Test execution result (Node 4 output)."""
    test_id: str
    passed: bool
    error_message: str
    stdout: str


class ComplianceFlag(TypedDict, total=False):
    """Compliance risk flag (Node 5 output)."""
    flag_id: str
    severity: str  # warning, critical
    category: str  # pii, float_arithmetic, magic_number, missing_exception
    description: str
    line_number: int
    suggestion: str


class PipelineState(TypedDict, total=False):
    """Central state flowing through all 6 nodes."""
    # Input
    raw_rule: str
    scenario_id: str
    complexity: str

    # Node 1: Rule Interpreter
    rule_spec: RuleSpec

    # Node 2: Code Generator
    generated_code: str

    # Node 3: Test Generator
    test_cases: list[TestCase]
    test_code: str

    # Node 4: Test Runner + Self-Fix
    test_results: list[TestResult]
    all_tests_passed: bool
    fix_attempt: int
    fix_history: list[dict]  # {attempt, error, previous_code, fixed_code}

    # Node 5: Compliance Checker + Fidelity
    compliance_flags: list[ComplianceFlag]
    fidelity_results: list[dict]  # {condition_id, implemented, evidence}
    fidelity_score: float  # 0.0 ~ 1.0

    # Node 6: Documentation Generator
    documentation: str

    # Pipeline metadata
    status: str  # running, success, manual_required, error
    error_message: str
