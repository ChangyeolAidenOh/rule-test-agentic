"""Node 3: Test Generator - generate pytest test cases from rule spec + code."""

import json

from core.llm import invoke_llm
from core.state import PipelineState


SYSTEM_PROMPT = """You are a QA engineer specializing in insurance systems. Generate comprehensive pytest test cases for the given business rule implementation.

Requirements:
1. Import the `apply_rule` function from a module called `generated_module`.
2. Use `from decimal import Decimal` for all monetary test values.
3. Cover these test categories:
   - **normal**: typical valid inputs with expected outputs
   - **boundary**: edge values at exact thresholds (e.g., exactly 65 years old, exactly 90 days)
   - **exception**: invalid inputs that should raise ValueError
   - **error**: type errors, missing parameters
4. Each test function should have a descriptive name: `test_<category>_<description>`.
5. Use `pytest.raises(ValueError)` for exception tests.
6. Use `pytest.approx` or direct Decimal comparison for monetary values.
7. Include at least 2 tests per category.
8. Add a brief docstring to each test explaining what it verifies.
9. IMPORTANT: Keep the total number of tests between 8-15. Prioritize quality over quantity.
   - 3-4 normal tests (representative cases)
   - 3-4 boundary tests (exact threshold values)
   - 2-3 exception tests (invalid inputs)
   - 1-2 error tests (type errors)
10. Each test should be concise - no more than 10 lines per test function.

Output ONLY the Python test code. No markdown fences, no explanation.

Example:
```
import pytest
from decimal import Decimal
from generated_module import apply_rule

def test_normal_basic_case():
    \"\"\"Verify basic rule application with typical inputs.\"\"\"
    result = apply_rule(...)
    assert result == Decimal("...")

def test_boundary_exact_threshold():
    \"\"\"Verify behavior at exact boundary value.\"\"\"
    ...

def test_exception_invalid_input():
    \"\"\"Verify ValueError for invalid input.\"\"\"
    with pytest.raises(ValueError):
        apply_rule(...)
```
"""


def test_generator(state: PipelineState) -> dict:
    """Generate pytest test cases from rule spec and generated code."""
    rule_spec = state["rule_spec"]
    generated_code = state["generated_code"]

    user_prompt = (
        "Business rule specification:\n"
        f"{json.dumps(rule_spec, indent=2, ensure_ascii=False)}\n\n"
        "Generated code to test:\n"
        f"{generated_code}\n\n"
        "Generate comprehensive pytest test cases covering "
        "normal, boundary, exception, and error categories."
    )

    response = invoke_llm(
        node_name="test_generator",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
    )

    # Strip markdown fences if present
    test_code = response.strip()
    if test_code.startswith("```"):
        test_code = test_code.split("\n", 1)[1]
    if test_code.endswith("```"):
        test_code = test_code.rsplit("```", 1)[0]
    test_code = test_code.strip()

    return {
        "test_code": test_code,
        "status": "tests_generated",
    }
