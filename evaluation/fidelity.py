"""Business Rule Fidelity checker.

Verifies that generated code correctly implements ALL conditions from the
rule specification. Separates "code that runs" from "code that is correct."

Uses Haiku for lightweight per-condition checking against the generated code.
"""

import json

from core.llm import invoke_llm


SYSTEM_PROMPT = """You are an insurance business rule auditor. Your job is to verify whether generated Python code correctly implements each condition from a business rule specification.

For each condition provided, evaluate:
1. Is the condition implemented in the code? (true/false)
2. What is the evidence? (cite the specific code line or logic)
3. Is the implementation correct? (does it match the operator and threshold exactly?)

Output ONLY valid JSON array, no markdown:
[
    {
        "condition_id": "C1",
        "implemented": true,
        "correct": true,
        "evidence": "Line 15: age_at_renewal >= AGE_SURCHARGE_THRESHOLD where AGE_SURCHARGE_THRESHOLD = 65"
    }
]

Rules:
- "implemented" means the condition EXISTS in the code in some form.
- "correct" means the condition matches the EXACT operator and value from the spec.
- If a condition uses >= but the code uses >, mark correct=false.
- If a threshold is 180 but the code uses 179, mark correct=false.
- Be strict. A condition is correct ONLY if it precisely matches the specification.
"""


def check_fidelity(rule_spec: dict, generated_code: str) -> dict:
    """Check if each condition in rule_spec is implemented in generated code.

    Returns:
        {
            "fidelity_results": [
                {
                    "condition_id": str,
                    "implemented": bool,
                    "correct": bool,
                    "evidence": str
                }
            ],
            "fidelity_score": float  # (implemented AND correct) / total
        }
    """
    conditions = rule_spec.get("conditions", [])
    if not conditions:
        return {
            "fidelity_results": [],
            "fidelity_score": 1.0,
        }

    user_prompt = (
        "Business rule conditions to verify:\n"
        f"{json.dumps(conditions, indent=2, ensure_ascii=False)}\n\n"
        "Generated code:\n"
        f"{generated_code}\n\n"
        "Evaluate each condition."
    )

    response = invoke_llm(
        node_name="compliance_checker",  # Uses Haiku
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,
    )

    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: mark all as unverified
        results = [
            {
                "condition_id": c.get("condition_id", f"C{i+1}"),
                "implemented": False,
                "correct": False,
                "evidence": "Fidelity check failed to parse LLM response",
            }
            for i, c in enumerate(conditions)
        ]

    total = len(conditions)
    faithful = sum(
        1 for r in results
        if r.get("implemented") and r.get("correct")
    )
    score = faithful / total if total > 0 else 0.0

    return {
        "fidelity_results": results,
        "fidelity_score": round(score, 4),
    }
