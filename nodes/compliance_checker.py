"""Node 5: Compliance Checker - rule-based security checks + Business Rule Fidelity."""

import ast
import re

from core.state import ComplianceFlag, PipelineState
from evaluation.fidelity import check_fidelity


# PII-related variable name patterns
PII_PATTERNS = [
    r"(주민등록|resident_id|ssn|social_security)",
    r"(전화번호|phone|mobile|cell)",
    r"(주소|address|addr)",
    r"(이메일|email)",
    r"(성명|full_name|customer_name)",
    r"(계좌번호|account_number|bank_account)",
    r"(카드번호|card_number|credit_card)",
]

# Magic number detection - numbers that should be constants
MAGIC_NUMBER_THRESHOLD = 2  # numbers appearing as literals > this are flagged


def compliance_checker(state: PipelineState) -> dict:
    """Run compliance checks on generated code."""
    code = state["generated_code"]
    flags: list[ComplianceFlag] = []

    flag_counter = 0

    # Check 1: PII variable logging
    pii_flags = _check_pii_exposure(code)
    for f in pii_flags:
        flag_counter += 1
        f["flag_id"] = f"CF{flag_counter:03d}"
        flags.append(f)

    # Check 2: Float arithmetic for monetary values
    float_flags = _check_float_arithmetic(code)
    for f in float_flags:
        flag_counter += 1
        f["flag_id"] = f"CF{flag_counter:03d}"
        flags.append(f)

    # Check 3: Magic numbers
    magic_flags = _check_magic_numbers(code)
    for f in magic_flags:
        flag_counter += 1
        f["flag_id"] = f"CF{flag_counter:03d}"
        flags.append(f)

    # Check 4: Missing exception handling
    exception_flags = _check_exception_handling(code)
    for f in exception_flags:
        flag_counter += 1
        f["flag_id"] = f"CF{flag_counter:03d}"
        flags.append(f)

    # Check 5: Business Rule Fidelity
    rule_spec = state.get("rule_spec", {})
    fidelity = check_fidelity(rule_spec, code)

    return {
        "compliance_flags": flags,
        "fidelity_results": fidelity["fidelity_results"],
        "fidelity_score": fidelity["fidelity_score"],
        "status": "compliance_checked",
    }


def _check_pii_exposure(code: str) -> list[dict]:
    """Detect PII-related variables in print/log statements."""
    flags = []
    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if any(kw in stripped for kw in ["print(", "logging.", "logger."]):
            for pattern in PII_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    flags.append({
                        "severity": "critical",
                        "category": "pii",
                        "description": f"Potential PII variable in log/print statement",
                        "line_number": i,
                        "suggestion": "Remove PII variables from logging statements",
                    })
                    break
    return flags


def _check_float_arithmetic(code: str) -> list[dict]:
    """Detect float usage in monetary calculations."""
    flags = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return flags

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            # Check if it looks like a monetary or percentage value
            flags.append({
                "severity": "warning",
                "category": "float_arithmetic",
                "description": (
                    f"Float literal {node.value} detected. "
                    "Use Decimal for monetary calculations."
                ),
                "line_number": node.lineno,
                "suggestion": f'Use Decimal("{node.value}") instead',
            })
    return flags


def _check_magic_numbers(code: str) -> list[dict]:
    """Detect hardcoded numeric constants that should be named."""
    flags = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return flags

    # Find numbers used inline (not in assignments at module level)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                    val = child.value
                    # Skip common non-magic numbers
                    if val in (0, 1, -1, 2, 100, True, False):
                        continue
                    # Skip Decimal string arguments
                    flags.append({
                        "severity": "warning",
                        "category": "magic_number",
                        "description": (
                            f"Hardcoded number {val} inside function body"
                        ),
                        "line_number": child.lineno,
                        "suggestion": "Define as a module-level constant with a descriptive name",
                    })
    return flags


def _check_exception_handling(code: str) -> list[dict]:
    """Check for missing input validation."""
    flags = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return flags

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "apply_rule":
            # Check if function has any raise statements
            has_raise = any(
                isinstance(child, ast.Raise) for child in ast.walk(node)
            )
            if not has_raise:
                flags.append({
                    "severity": "warning",
                    "category": "missing_exception",
                    "description": (
                        "apply_rule() has no input validation (no raise statements)"
                    ),
                    "line_number": node.lineno,
                    "suggestion": "Add ValueError checks for invalid inputs",
                })
    return flags
