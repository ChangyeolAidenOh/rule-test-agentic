"""Node 6: Documentation Generator - generate developer review document."""

import json

from core.llm import invoke_llm
from core.state import PipelineState


SYSTEM_PROMPT = """You are a technical documentation writer for an insurance IT team. Generate a developer review document for auto-generated code.

The document must include:
1. **Business Rule Summary**: What the rule does in plain language.
2. **Implementation Overview**: Key functions, data types, constants used.
3. **Test Coverage Summary**: Which test categories (normal/boundary/exception/error) are covered.
4. **Compliance Flags**: Any security or regulatory concerns found.
5. **Developer Review Checklist**: A checklist of items the developer must verify before approving.
   - [ ] Business logic matches the original rule
   - [ ] All edge cases are handled correctly
   - [ ] Decimal arithmetic used for all monetary values
   - [ ] No PII in logging statements
   - [ ] Error messages are descriptive
   - [ ] Constants are properly named
6. **Self-Correction History** (if any): What was fixed and why.

Use Markdown format. Include the disclaimer:
> ⚠️ This document is auto-generated. All code and tests require developer review and approval before deployment.

Output ONLY the Markdown document.
"""


def doc_generator(state: PipelineState) -> dict:
    """Generate developer review documentation."""
    rule_spec = state.get("rule_spec", {})
    generated_code = state.get("generated_code", "")
    test_code = state.get("test_code", "")
    test_results = state.get("test_results", [])
    compliance_flags = state.get("compliance_flags", [])
    fix_history = state.get("fix_history", [])

    # Build context for LLM
    passed_count = sum(1 for r in test_results if r.get("passed"))
    failed_count = sum(1 for r in test_results if not r.get("passed"))

    flags_summary = ""
    if compliance_flags:
        flag_lines = []
        for f in compliance_flags:
            flag_lines.append(
                f"- [{f.get('severity', 'info')}] {f.get('category', '')}: "
                f"{f.get('description', '')} (line {f.get('line_number', '?')})"
            )
        flags_summary = "\n".join(flag_lines)
    else:
        flags_summary = "No compliance flags detected."

    fix_summary = ""
    if fix_history:
        fix_lines = []
        for fh in fix_history:
            fix_lines.append(f"Attempt {fh.get('attempt', '?')}: {fh.get('error', '')[:200]}")
        fix_summary = "\n".join(fix_lines)
    else:
        fix_summary = "No self-correction needed. Code passed on first attempt."

    # Fidelity summary
    fidelity_results = state.get("fidelity_results", [])
    fidelity_score = state.get("fidelity_score", 0.0)
    if fidelity_results:
        fid_lines = [f"Fidelity Score: {fidelity_score:.0%}"]
        for fr in fidelity_results:
            status = "FAITHFUL" if fr.get("implemented") and fr.get("correct") else "ISSUE"
            fid_lines.append(
                f"- {fr.get('condition_id', '?')}: [{status}] {fr.get('evidence', '')[:150]}"
            )
        fidelity_summary = "\n".join(fid_lines)
    else:
        fidelity_summary = "No fidelity data available."

    user_prompt = (
        f"Rule Specification:\n{json.dumps(rule_spec, indent=2, ensure_ascii=False)}\n\n"
        f"Generated Code:\n{generated_code}\n\n"
        f"Test Results: {passed_count} passed, {failed_count} failed\n\n"
        f"Compliance Flags:\n{flags_summary}\n\n"
        f"Business Rule Fidelity:\n{fidelity_summary}\n\n"
        f"Self-Correction History:\n{fix_summary}\n\n"
        "Generate the developer review document."
    )

    response = invoke_llm(
        node_name="doc_generator",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    return {
        "documentation": response.strip(),
        "status": "completed",
    }
