"""Node 1: Rule Interpreter - natural language to structured business rule spec."""

import json

from core.llm import invoke_llm
from core.state import PipelineState


SYSTEM_PROMPT = """You are an insurance business rule analyst. Your job is to parse a natural language business rule into a structured JSON specification.

Output ONLY valid JSON with the following schema (no markdown, no explanation):

{
    "rule_id": "<scenario_id from input>",
    "title": "<concise English title>",
    "description": "<one-line summary of the rule>",
    "conditions": [
        {
            "condition_id": "C1",
            "description": "<what this condition checks>",
            "parameter": "<variable name>",
            "operator": "<ge|gt|le|lt|eq|ne|in|between>",
            "value": "<threshold or list>",
            "unit": "<years|days|KRW|percent|etc>"
        }
    ],
    "calculations": [
        {
            "calc_id": "CALC1",
            "description": "<what is being calculated>",
            "formula": "<plain-text formula>",
            "output_variable": "<result variable name>",
            "output_type": "<Decimal|int|bool>",
            "depends_on": ["C1"]
        }
    ],
    "edge_cases": [
        {
            "edge_id": "E1",
            "description": "<boundary or exceptional scenario>",
            "test_values": {"<param>": "<value>"}
        }
    ],
    "constraints": [
        "<business constraint or validation rule>"
    ]
}

Guidelines:
- All monetary amounts must use Decimal type, never float.
- Identify ALL boundary values (ages, days, amounts) as edge cases.
- Include at least one edge case per condition.
- The formula field should be human-readable, not code.
- Keep parameter names in snake_case English.
- Conditions should be atomic (one check per condition).
"""


def rule_interpreter(state: PipelineState) -> dict:
    """Parse natural language rule into structured specification."""
    raw_rule = state["raw_rule"]
    scenario_id = state.get("scenario_id", "unknown")

    user_prompt = (
        f"Scenario ID: {scenario_id}\n"
        f"Business Rule (Korean):\n{raw_rule}\n\n"
        "Parse this into the structured JSON specification."
    )

    response = invoke_llm(
        node_name="rule_interpreter",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,
    )

    # Strip markdown fences if present
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    rule_spec = json.loads(text)

    return {
        "rule_spec": rule_spec,
        "status": "rule_interpreted",
    }
