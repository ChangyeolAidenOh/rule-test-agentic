"""Deterministic (AST-based) Business Rule Fidelity check for threshold conditions.

What it verifies
----------------
*Boundary placement*: for a spec condition such as ``age ge 65``, does the code
compare the same variable against the same threshold with the threshold value
falling on the same side of the boundary?

Equivalences handled
--------------------
- Operand order:      ``65 <= age``            == ``age >= 65``
- Negation/guards:    ``if x < 0: raise``      has the same boundary as ``x >= 0``
                      (negating a comparison never moves the boundary, so raise
                      guards and else-branches need no special handling)
- Integer domain:     ``days > 90``            == ``days >= 91``   (days, years, age, ...)
- Chained compares:   ``0 <= x < 180``         -> (x ge 0), (x lt 180)
- Named constants:    ``AGE_THRESHOLD = 65``, ``ZERO = Decimal("0")``

What it does NOT verify
-----------------------
- Branch direction (which side of the boundary is eligible). That is covered by
  the generated tests and by the LLM judge.
- Non-numeric thresholds (``value == "annual_benefit_limit"``), booleans,
  ``in`` / ``between`` operators, and off-by-one *constant* errors on a variable
  whose name does not match the spec. These are returned as ``undetermined``
  and routed to the LLM judge.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

AST_OPS = {
    ast.GtE: "ge", ast.Gt: "gt", ast.LtE: "le",
    ast.Lt: "lt", ast.Eq: "eq", ast.NotEq: "ne",
}
SWAP = {"ge": "le", "gt": "lt", "le": "ge", "lt": "gt", "eq": "eq", "ne": "ne"}
SPEC_OP_ALIASES = {
    "ge": "ge", ">=": "ge", "gte": "ge",
    "gt": "gt", ">": "gt",
    "le": "le", "<=": "le", "lte": "le",
    "lt": "lt", "<": "lt",
    "eq": "eq", "==": "eq", "=": "eq",
    "ne": "ne", "!=": "ne",
}
INTEGER_UNITS = {
    "day", "days", "year", "years", "age", "month", "months",
    "count", "times", "admissions", "visits",
}
PERCENT_UNITS = {"percent", "%", "pct"}
STOPWORDS = {"the", "of", "a", "an", "and", "or", "in", "is", "to", "for", "at", "by"}
NAME_SIM_THRESHOLD = 0.5
NON_DISTINCTIVE_VALUES = {Decimal("0"), Decimal("1")}

VERDICT_FAITHFUL = "faithful"
VERDICT_INCORRECT = "incorrect"
VERDICT_UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class Comparison:
    """A single `variable <op> threshold` comparison found in the code."""
    var: str | None   # variable / attribute / dict-key name, if identifiable
    expr: str         # source text of the variable side (for evidence)
    op: str           # normalised so the variable is on the left
    value: Decimal
    line: int


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def to_decimal(value) -> Decimal | None:
    """Convert a spec/code literal to Decimal; None if not numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("_", "")
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _resolve(node: ast.AST, consts: dict[str, Decimal]) -> Decimal | None:
    """Resolve an expression to a numeric constant if possible."""
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
        if isinstance(node.value, (int, float)):
            return Decimal(str(node.value))
        return None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _resolve(node.operand, consts)
        return -inner if inner is not None else None
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords:
        func = node.func
        fname = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else None)
        if fname in ("Decimal", "int", "float"):
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                return to_decimal(arg.value)
            return _resolve(arg, consts)
    return None


def _collect_constants(tree: ast.AST) -> dict[str, Decimal]:
    """Collect `NAME = <numeric>` assignments (module or function level)."""
    consts: dict[str, Decimal] = {}
    for _ in range(3):  # a few passes so A = B chains resolve
        changed = False
        for node in ast.walk(tree):
            targets, value = [], None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            for t in targets:
                if isinstance(t, ast.Name) and t.id not in consts:
                    v = _resolve(value, consts)
                    if v is not None:
                        consts[t.id] = v
                        changed = True
        if not changed:
            break
    return consts


def _var_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
    return None


def extract_comparisons(code: str) -> list[Comparison]:
    """Extract all `variable <op> numeric` comparisons from source code.

    Raises SyntaxError if the code does not parse.
    """
    tree = ast.parse(code)
    consts = _collect_constants(tree)
    found: list[Comparison] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left] + list(node.comparators)
        for left, op_node, right in zip(operands, node.ops, operands[1:]):
            op = AST_OPS.get(type(op_node))
            if op is None:
                continue
            lv, rv = _resolve(left, consts), _resolve(right, consts)
            if (lv is None) == (rv is None):
                continue  # both or neither numeric: not a threshold comparison
            if rv is not None:
                var_node, value, norm_op = left, rv, op
            else:
                var_node, value, norm_op = right, lv, SWAP[op]
            found.append(Comparison(
                var=_var_name(var_node),
                expr=ast.unparse(var_node),
                op=norm_op,
                value=value,
                line=node.lineno,
            ))
    return found


# ---------------------------------------------------------------------------
# Boundary model
# ---------------------------------------------------------------------------

def boundary(op: str, value: Decimal, integer: bool) -> tuple[str, Decimal]:
    """Canonical boundary of a comparison.

    ("split", v)       -> v belongs to the upper side   (x >= v  /  x < v)
    ("split_open", v)  -> v belongs to the lower side   (x > v   /  x <= v)
    ("point", v)       -> equality boundary             (x == v  /  x != v)

    In an integer domain ("split_open", v) is rewritten as ("split", v + 1).
    """
    if op in ("eq", "ne"):
        return ("point", value)
    closed = op in ("ge", "lt")
    if closed:
        return ("split", value)
    if integer and value == value.to_integral_value():
        return ("split", value + 1)
    return ("split_open", value)


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", name.lower()) if t and t not in STOPWORDS}


def name_similarity(a: str, b: str) -> float:
    """Jaccard similarity over snake_case tokens (stopwords removed)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _is_integer_domain(condition: dict, value: Decimal) -> bool:
    unit = str(condition.get("unit", "")).strip().lower()
    return unit in INTEGER_UNITS and value == value.to_integral_value()


def _fmt(c: Comparison) -> str:
    return f"line {c.line}: {c.expr} {c.op} {c.value}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_condition(condition: dict, comparisons: list[Comparison]) -> dict:
    """Judge one spec condition against the extracted comparisons."""
    cid = condition.get("condition_id", "?")
    base = {"condition_id": cid, "method": "ast"}

    def undetermined(reason: str) -> dict:
        return {**base, "verdict": VERDICT_UNDETERMINED, "evidence": reason, "matched_by": None}

    op = SPEC_OP_ALIASES.get(str(condition.get("operator", "")).strip().lower())
    if op is None:
        return undetermined(f"operator '{condition.get('operator')}' not supported by AST check")

    value = to_decimal(condition.get("value"))
    if value is None:
        return undetermined(f"non-numeric threshold '{condition.get('value')}'")

    integer = _is_integer_domain(condition, value)
    unit = str(condition.get("unit", "")).strip().lower()
    spec_values = {value}
    if unit in PERCENT_UNITS:
        spec_values.add(value / Decimal("100"))

    targets = {boundary(op, v, integer) for v in spec_values}
    target_points = {t[1] for t in targets} | spec_values

    relevant = [
        c for c in comparisons
        if c.value in spec_values or boundary(c.op, c.value, integer)[1] in target_points
    ]

    param = str(condition.get("parameter", ""))
    named = [c for c in relevant if c.var and name_similarity(c.var, param) >= NAME_SIM_THRESHOLD]

    if named:
        candidates, matched_by = named, "name"
    elif relevant and not (spec_values & NON_DISTINCTIVE_VALUES):
        candidates, matched_by = relevant, "value"
    else:
        return undetermined(
            f"no comparison of '{param}' against {condition.get('value')} found"
        )

    matches = [c for c in candidates if boundary(c.op, c.value, integer) in targets]
    mismatches = [c for c in candidates if c not in matches]

    if matches and not mismatches:
        verdict = VERDICT_FAITHFUL
        evidence = "boundary matches spec — " + "; ".join(_fmt(c) for c in matches)
    elif mismatches and not matches:
        verdict = VERDICT_INCORRECT
        evidence = (
            f"spec requires {param} {op} {condition.get('value')}, code has "
            + "; ".join(_fmt(c) for c in mismatches)
        )
    else:
        return undetermined(
            "mixed boundaries — match: " + "; ".join(_fmt(c) for c in matches)
            + " | mismatch: " + "; ".join(_fmt(c) for c in mismatches)
        )

    return {**base, "verdict": verdict, "evidence": evidence, "matched_by": matched_by}


def check_conditions_ast(conditions: list[dict], code: str) -> list[dict]:
    """Run the AST check for every condition. Unparseable code -> all undetermined."""
    try:
        comparisons = extract_comparisons(code)
    except SyntaxError as e:
        return [
            {
                "condition_id": c.get("condition_id", f"C{i + 1}"),
                "method": "ast",
                "verdict": VERDICT_UNDETERMINED,
                "evidence": f"code does not parse: {e}",
                "matched_by": None,
            }
            for i, c in enumerate(conditions)
        ]
    return [check_condition(c, comparisons) for c in conditions]
