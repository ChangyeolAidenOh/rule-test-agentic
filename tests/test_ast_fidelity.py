"""Tests for the deterministic fidelity checker and the hybrid wrapper.

Includes regression cases reconstructed from the v1 evaluation:
  - S2 C2: Haiku judged `days_used < 180` as incorrect while its own evidence
           said it was correct (judge error). AST must say faithful.
  - S4 C1: spec `total_paid_premium gt 0`, code only rejects `< 0`
           (allows 0). AST must say incorrect.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ast_fidelity import (  # noqa: E402
    boundary,
    check_conditions_ast,
    extract_comparisons,
    name_similarity,
)
from decimal import Decimal  # noqa: E402


def cond(cid, param, op, value, unit=""):
    return {"condition_id": cid, "parameter": param, "operator": op, "value": value, "unit": unit}


def verdict(code, condition):
    return check_conditions_ast([condition], code)[0]


# --- v1 regressions --------------------------------------------------------

S2_CODE = '''
from decimal import Decimal
WAITING_PERIOD_DAYS = 90
ANNUAL_LIMIT_DAYS = 180
MINIMUM_CLAIM_DAYS = 1

def is_waiting_period_over(days_since_inception: int) -> bool:
    return days_since_inception > WAITING_PERIOD_DAYS

def has_annual_capacity(annual_hospitalization_days_used: int) -> bool:
    return annual_hospitalization_days_used < ANNUAL_LIMIT_DAYS

def validate(claimed_hospitalization_days: int) -> None:
    if claimed_hospitalization_days < MINIMUM_CLAIM_DAYS:
        raise ValueError("at least one day")
'''

S4_CODE = '''
from decimal import Decimal
ZERO = Decimal("0")

def apply_rule(total_paid_premium, risk_premium_accumulated):
    if total_paid_premium < ZERO:
        raise ValueError("negative")
    if risk_premium_accumulated < ZERO:
        raise ValueError("negative")
    return total_paid_premium - risk_premium_accumulated
'''


def test_s2_c1_waiting_period_faithful():
    r = verdict(S2_CODE, cond("C1", "days_since_inception", "gt", "90", "days"))
    assert r["verdict"] == "faithful"


def test_s2_c2_regression_haiku_false_negative():
    """v1 Haiku verdict was incorrect=False although the code is correct."""
    r = verdict(S2_CODE, cond("C2", "annual_hospitalization_days_used", "lt", "180", "days"))
    assert r["verdict"] == "faithful"
    assert r["matched_by"] == "name"


def test_s2_c3_raise_guard_faithful():
    r = verdict(S2_CODE, cond("C3", "claimed_hospitalization_days", "ge", "1", "days"))
    assert r["verdict"] == "faithful"


def test_s4_c1_regression_gt_vs_ge_incorrect():
    """spec gt 0 but code allows 0 -> incorrect."""
    r = verdict(S4_CODE, cond("C1", "total_paid_premium", "gt", "0", "KRW"))
    assert r["verdict"] == "incorrect"


def test_s4_c2_ge_zero_faithful():
    r = verdict(S4_CODE, cond("C2", "risk_premium_accumulated", "ge", "0", "KRW"))
    assert r["verdict"] == "faithful"


# --- equivalences ----------------------------------------------------------

def test_swapped_operands():
    code = "def f(age):\n    return 65 <= age\n"
    assert verdict(code, cond("C1", "age", "ge", 65, "years"))["verdict"] == "faithful"


def test_integer_domain_equivalence():
    code = "def f(days_since_inception):\n    return days_since_inception >= 91\n"
    assert verdict(code, cond("C1", "days_since_inception", "gt", 90, "days"))["verdict"] == "faithful"


def test_no_integer_equivalence_for_money():
    code = "from decimal import Decimal\ndef f(amount):\n    return amount >= Decimal('91')\n"
    r = verdict(code, cond("C1", "amount", "gt", 90, "KRW"))
    assert r["verdict"] == "undetermined"  # 91 is not the 90 boundary for continuous money


def test_chained_comparison():
    code = "def f(days_used):\n    return 0 <= days_used < 180\n"
    assert verdict(code, cond("C1", "days_used", "lt", 180, "days"))["verdict"] == "faithful"


def test_inclusive_vs_exclusive_boundary_incorrect():
    code = "LIMIT = 180\ndef f(days_between):\n    return days_between < LIMIT\n"
    r = verdict(code, cond("C1", "days_between", "le", 180, "days"))
    assert r["verdict"] == "incorrect"


def test_value_fallback_when_names_differ():
    code = (
        "READMISSION_WINDOW_DAYS = 180\n"
        "def f(days_gap):\n    return days_gap <= READMISSION_WINDOW_DAYS\n"
    )
    r = verdict(code, cond("C2", "days_between_discharge_and_readmission", "le", 180, "days"))
    assert r["verdict"] == "faithful"
    assert r["matched_by"] == "value"


def test_zero_threshold_without_name_match_is_undetermined():
    code = "def f(x):\n    if x < 0:\n        raise ValueError\n"
    r = verdict(code, cond("C1", "total_paid_premium", "gt", 0, "KRW"))
    assert r["verdict"] == "undetermined"


def test_percent_unit():
    code = "from decimal import Decimal\nRATE = Decimal('0.8')\ndef f(disability_rate):\n    return disability_rate >= RATE\n"
    r = verdict(code, cond("C1", "disability_rate", "ge", 80, "percent"))
    assert r["verdict"] == "faithful"


# --- routed to LLM ----------------------------------------------------------

def test_non_numeric_threshold_undetermined():
    r = verdict("def f(x, limit):\n    return x <= limit\n",
                cond("C3", "cumulative_annual_benefit", "le", "annual_benefit_limit", "KRW"))
    assert r["verdict"] == "undetermined"


def test_boolean_condition_undetermined():
    r = verdict("def f(m):\n    return m\n", cond("C1", "disease_code_match", "eq", "true", "boolean"))
    assert r["verdict"] == "undetermined"


def test_mixed_boundaries_undetermined():
    code = "def f(age):\n    a = age >= 65\n    b = age > 65\n    return a, b\n"
    assert verdict(code, cond("C1", "age", "ge", 65))["verdict"] == "undetermined"


def test_unparseable_code():
    r = check_conditions_ast([cond("C1", "age", "ge", 65)], "def broken(:\n")
    assert r[0]["verdict"] == "undetermined"
    assert "does not parse" in r[0]["evidence"]


# --- helpers -----------------------------------------------------------------

def test_boundary_model():
    assert boundary("ge", Decimal(65), True) == boundary("lt", Decimal(65), True)
    assert boundary("gt", Decimal(90), True) == boundary("ge", Decimal(91), True)
    assert boundary("gt", Decimal(90), False) != boundary("ge", Decimal(91), False)


def test_name_similarity():
    assert name_similarity("age_at_renewal", "age_at_renewal") == 1.0
    assert name_similarity("age", "age_at_renewal") >= 0.5
    assert name_similarity("days_gap", "days_between_discharge_and_readmission") < 0.5


def test_extract_resolves_decimal_constants():
    comps = extract_comparisons("from decimal import Decimal\nZ = Decimal('0')\ndef f(x):\n    return x < Z\n")
    assert comps[0].value == Decimal("0") and comps[0].op == "lt"


# --- hybrid wrapper with a fake LLM -----------------------------------------

def test_hybrid_routes_only_undetermined_to_llm(monkeypatch):
    calls = {}

    def fake_invoke_llm(node_name, system_prompt, user_prompt, temperature=0.0):
        calls["prompt"] = user_prompt
        return '[{"condition_id": "C9", "evidence": "line 2 returns m", "verdict": "faithful"}]'

    fake_llm = types.ModuleType("core.llm")
    fake_llm.invoke_llm = fake_invoke_llm
    monkeypatch.setitem(sys.modules, "core.llm", fake_llm)

    from evaluation.fidelity import check_fidelity

    spec = {"conditions": [
        {**cond("C1", "age", "ge", 65, "years"), "source": "rule"},
        {**cond("C9", "disease_code_match", "eq", "true", "boolean"), "source": "derived"},
    ]}
    code = "def f(age, m):\n    return age >= 65 and m\n"
    out = check_fidelity(spec, code)

    by_id = {r["condition_id"]: r for r in out["fidelity_results"]}
    assert by_id["C1"]["method"] == "ast" and by_id["C1"]["verdict"] == "faithful"
    assert by_id["C9"]["method"] == "llm" and by_id["C9"]["verdict"] == "faithful"
    assert by_id["C1"]["source"] == "rule" and by_id["C9"]["source"] == "derived"
    assert '"C1"' not in calls["prompt"]          # AST-decided conditions are not sent to the LLM
    assert "   1: def f(age, m):" in calls["prompt"]  # judge sees line numbers
    assert out["fidelity_score"] == 1.0


def test_hybrid_invalid_llm_verdict_becomes_undetermined(monkeypatch):
    fake_llm = types.ModuleType("core.llm")
    fake_llm.invoke_llm = lambda **kw: "not json at all"
    monkeypatch.setitem(sys.modules, "core.llm", fake_llm)

    from evaluation.fidelity import check_fidelity

    spec = {"conditions": [cond("C1", "disease_code_match", "eq", "true", "boolean")]}
    out = check_fidelity(spec, "def f(m):\n    return m\n")
    r = out["fidelity_results"][0]
    assert r["verdict"] == "undetermined"
    assert r["correct"] is False
    assert out["fidelity_score"] == 0.0


def test_evidence_marks_equivalent_boundary():
    """Code `days_used > 180` vs spec `le 180`: same boundary, shown as equivalent."""
    code = "LIMIT = 180\ndef f(annual_hospitalization_days_used):\n    if annual_hospitalization_days_used > LIMIT:\n        raise ValueError\n"
    r = verdict(code, cond("C2", "annual_hospitalization_days_used", "le", 180, "days"))
    assert r["verdict"] == "faithful"
    assert r["evidence"].startswith("spec: annual_hospitalization_days_used le 180")
    assert "(equivalent boundary)" in r["evidence"]


def test_evidence_same_form_has_no_equivalence_note():
    code = "def f(age):\n    return age >= 65\n"
    r = verdict(code, cond("C1", "age", "ge", 65, "years"))
    assert "(equivalent boundary)" not in r["evidence"]
