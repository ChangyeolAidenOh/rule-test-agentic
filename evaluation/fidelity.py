"""Business Rule Fidelity — hybrid checker.

Separates "code that runs" from "code that is correct" by checking every
condition of the structured rule spec against the generated code.

Two stages:
  1. AST check (evaluation/ast_fidelity.py) — deterministic, for numeric
     threshold conditions. No LLM, fully reproducible.
  2. LLM judge — only for conditions the AST check returns as `undetermined`
     (non-numeric thresholds, booleans, mixed boundaries, unmatched names).
     The judge sees line-numbered code and must write evidence BEFORE the
     verdict, so the verdict is conditioned on the evidence (v1 used
     verdict-first output and produced a self-contradictory verdict on S2 C2).

Result schema per condition:
  condition_id, method (ast | llm | none), verdict (faithful | incorrect |
  missing | undetermined), evidence, matched_by, source (rule | derived |
  unknown), implemented, correct  (the last two kept for backward compatibility)
"""

from __future__ import annotations

import json

from evaluation.ast_fidelity import (
    VERDICT_FAITHFUL,
    VERDICT_INCORRECT,
    VERDICT_UNDETERMINED,
    check_conditions_ast,
)

VERDICT_MISSING = "missing"
LLM_VERDICTS = {VERDICT_FAITHFUL, VERDICT_INCORRECT, VERDICT_MISSING}

JUDGE_SYSTEM_PROMPT = """You are an insurance business rule auditor. Decide whether generated Python code implements each condition of a business rule specification.

The code is given with line numbers. For EACH condition, first write the evidence, then the verdict.

Output ONLY a valid JSON array, no markdown. Keys MUST appear in this order:
[
    {
        "condition_id": "C1",
        "evidence": "Quote the exact code line(s) with line numbers and explain how they relate to the condition's operator and threshold.",
        "verdict": "faithful"
    }
]

Verdict definitions:
- "faithful": the code implements the condition with the same boundary as the spec.
  Equivalent forms count as faithful, e.g. `x > 90` for spec `gt 90`;
  `if x < 0: raise ValueError` enforces `x >= 0`; for whole-number quantities
  `x >= 91` is equivalent to `x > 90`.
- "incorrect": the condition is implemented but the operator or threshold differs
  from the spec (e.g. spec `gt 0`, code only rejects `x < 0` so x == 0 is allowed).
- "missing": the code does not implement the condition at all.

Rules:
- The verdict MUST follow from your evidence. If your evidence concludes the
  implementation is correct, the verdict is "faithful".
- Judge against the specification as written, not against what you think the
  business rule should be.
"""


def number_lines(code: str) -> str:
    return "\n".join(f"{i:4d}: {line}" for i, line in enumerate(code.split("\n"), 1))


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in judge response")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("judge response is not a list")
    return data


def judge_conditions_llm(
    conditions: list[dict],
    code: str,
    node_name: str = "fidelity_judge",
    temperature: float | None = None,
) -> dict[str, dict]:
    """Ask the LLM judge about `conditions`. Returns {condition_id: result}.

    Conditions the judge fails to answer (or answers with an invalid verdict)
    come back as `undetermined`.
    """
    if not conditions:
        return {}

    from core.llm import invoke_llm  # lazy: keeps the AST path importable without the API stack
    from config.settings import TEMPERATURE_JUDGE

    user_prompt = (
        "Conditions to verify:\n"
        f"{json.dumps(conditions, indent=2, ensure_ascii=False)}\n\n"
        "Generated code (line-numbered):\n"
        f"{number_lines(code)}\n"
    )
    response = invoke_llm(
        node_name=node_name,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_JUDGE if temperature is None else temperature,
    )

    results: dict[str, dict] = {}
    try:
        items = _parse_json_array(response)
    except (ValueError, json.JSONDecodeError) as e:
        items = []
        parse_error = str(e)
    else:
        parse_error = None

    for item in items:
        cid = item.get("condition_id")
        verdict = str(item.get("verdict", "")).strip().lower()
        if cid is None:
            continue
        results[cid] = {
            "condition_id": cid,
            "method": "llm",
            "verdict": verdict if verdict in LLM_VERDICTS else VERDICT_UNDETERMINED,
            "evidence": item.get("evidence", ""),
            "matched_by": None,
        }

    for c in conditions:
        cid = c.get("condition_id")
        if cid not in results:
            results[cid] = {
                "condition_id": cid,
                "method": "llm",
                "verdict": VERDICT_UNDETERMINED,
                "evidence": f"judge gave no valid answer ({parse_error or 'condition omitted'})",
                "matched_by": None,
            }
    return results


def check_fidelity(rule_spec: dict, generated_code: str, use_llm: bool = True) -> dict:
    """Hybrid fidelity check: AST first, LLM judge for undetermined conditions.

    Returns:
        {
            "fidelity_results": [ per-condition result dicts ],
            "fidelity_score": faithful / total conditions,
        }
    """
    conditions = rule_spec.get("conditions", [])
    if not conditions:
        return {"fidelity_results": [], "fidelity_score": 1.0}

    ast_results = check_conditions_ast(conditions, generated_code)

    pending = [
        c for c, r in zip(conditions, ast_results)
        if r["verdict"] == VERDICT_UNDETERMINED
    ]
    llm_results = judge_conditions_llm(pending, generated_code) if (pending and use_llm) else {}

    results = []
    for cond, ast_r in zip(conditions, ast_results):
        cid = cond.get("condition_id")
        if ast_r["verdict"] != VERDICT_UNDETERMINED:
            r = dict(ast_r)
        elif cid in llm_results:
            r = dict(llm_results[cid])
            r["ast_note"] = ast_r["evidence"]
        else:
            r = dict(ast_r)
            r["method"] = "none"
        r["source"] = cond.get("source", "unknown")
        r["implemented"] = r["verdict"] in (VERDICT_FAITHFUL, VERDICT_INCORRECT)
        r["correct"] = r["verdict"] == VERDICT_FAITHFUL
        results.append(r)

    faithful = sum(1 for r in results if r["verdict"] == VERDICT_FAITHFUL)
    return {
        "fidelity_results": results,
        "fidelity_score": round(faithful / len(results), 4),
    }
