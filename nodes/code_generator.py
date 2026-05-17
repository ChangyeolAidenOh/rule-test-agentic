"""Node 2: Code Generator - structured rule spec to Python function code."""

import json

from core.llm import invoke_llm
from core.state import PipelineState


SYSTEM_PROMPT = """You are a senior Python developer specializing in insurance systems. Generate a Python module that implements the given business rule specification.

Requirements:
1. Use `from decimal import Decimal, ROUND_HALF_UP` for ALL monetary calculations. Never use float for money.
2. Use `from datetime import date, timedelta` for date calculations.
3. Include type hints for all function parameters and return values.
4. Include docstrings explaining the business rule.
5. Raise `ValueError` with descriptive messages for invalid inputs.
6. No hardcoded magic numbers - define them as module-level constants with descriptive names.
7. Only use Python standard library imports.
8. The main function name should be `apply_rule`.
9. Helper functions are encouraged for complex rules.

Output ONLY the Python code. No markdown fences, no explanation.

Example structure:
```
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

# Constants
SOME_THRESHOLD = Decimal("0.15")

def apply_rule(param1: Decimal, param2: int) -> Decimal:
    \"\"\"Apply the business rule.\"\"\"
    ...
```
"""

SELF_FIX_PROMPT = """The previously generated code failed tests. Fix the code based on the error information below.

Previous code:
{previous_code}

Error details:
{error_details}

Original rule specification:
{rule_spec}

Output ONLY the corrected Python code. No markdown fences, no explanation.
Focus on fixing the specific error while preserving correct logic.
"""


def code_generator(state: PipelineState) -> dict:
    """Generate Python code from structured rule specification."""
    rule_spec = state["rule_spec"]
    fix_attempt = state.get("fix_attempt", 0)

    if fix_attempt > 0 and state.get("fix_history"):
        # Self-correction mode
        last_fix = state["fix_history"][-1]
        user_prompt = SELF_FIX_PROMPT.format(
            previous_code=last_fix["previous_code"],
            error_details=last_fix["error"],
            rule_spec=json.dumps(rule_spec, indent=2, ensure_ascii=False),
        )
    else:
        user_prompt = (
            "Generate Python code for the following business rule specification:\n\n"
            f"{json.dumps(rule_spec, indent=2, ensure_ascii=False)}"
        )

    response = invoke_llm(
        node_name="code_generator",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,
    )

    # Strip markdown fences if present
    code = response.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1]
    if code.endswith("```"):
        code = code.rsplit("```", 1)[0]
    code = code.strip()

    return {
        "generated_code": code,
        "status": "code_generated",
    }
