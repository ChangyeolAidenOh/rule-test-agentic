"""Tests for evaluation/judge_reliability.py — statistics and the full workflow, no API calls."""

import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import judge_reliability as jr  # noqa: E402


# --- statistics ---------------------------------------------------------------

def test_wilson_interval_known_values():
    lo, hi = jr.wilson_interval(15, 17)
    assert 0.65 < lo < 0.67 and 0.96 < hi < 0.98
    assert jr.wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = jr.wilson_interval(10, 10)
    assert hi == 1.0 and lo < 1.0  # never collapses to a point at p = 1


def test_majority_and_ties():
    assert jr.majority(["faithful", "faithful", "incorrect"]) == "faithful"
    assert jr.majority(["faithful", "incorrect"]) == "undetermined"
    assert jr.majority([]) == "undetermined"


def test_score_judge_counts():
    pairs = [
        ("faithful", "faithful"),
        ("faithful", "incorrect"),      # false alarm
        ("incorrect", "incorrect"),     # caught
        ("missing", "undetermined"),    # caught (undetermined is a conservative flag)
        ("faithful", "undetermined"),   # false alarm
    ]
    s = jr.score_judge(pairs)
    assert s["n"] == 5
    assert s["accuracy"] == pytest.approx(2 / 5)
    assert s["coverage"] == pytest.approx(3 / 5)
    assert s["accuracy_on_decided"] == pytest.approx(2 / 3)
    assert (s["gold_problems"], s["problems_caught"], s["false_alarms"]) == (2, 2, 2)
    assert s["recall"] == 1.0 and s["precision"] == pytest.approx(0.5)


def test_self_consistency():
    assert jr.self_consistency([["a", "a", "a"], ["a", "b", "a"]]) == 0.5
    assert jr.self_consistency([["a"], ["b"]]) is None  # k = 1 carries no information


def test_stored_verdict_maps_v1_flags():
    assert jr.stored_verdict({"implemented": True, "correct": True}) == "faithful"
    assert jr.stored_verdict({"implemented": True, "correct": False}) == "incorrect"
    assert jr.stored_verdict({"implemented": False, "correct": False}) == "missing"
    assert jr.stored_verdict({"verdict": "undetermined"}) == "undetermined"
    assert jr.stored_verdict(None) == "undetermined"


# --- end-to-end workflow on a synthetic snapshot -----------------------------------

CODE = (
    "from decimal import Decimal\n"
    "ZERO = Decimal('0')\n"
    "def apply_rule(age, premium):\n"
    "    if premium < ZERO:\n"
    "        raise ValueError\n"
    "    return age >= 65\n"
)
CONDS = [
    {"condition_id": "C1", "parameter": "age", "operator": "ge", "value": "65", "unit": "years"},
    {"condition_id": "C2", "parameter": "premium", "operator": "gt", "value": "0", "unit": "KRW"},
]


@pytest.fixture
def snapshot(tmp_path):
    snap = tmp_path / "results_snapshot_test"
    snap.mkdir()
    state = {
        "scenario_id": "S1",
        "raw_rule": "65세 이상",
        "rule_spec": {"conditions": CONDS},
        "generated_code": CODE,
    }
    # v1-style stored verdicts: C1 wrongly flagged (judge error), C2 passed (missed problem)
    metrics = {"fidelity_results": [
        {"condition_id": "C1", "implemented": True, "correct": False},
        {"condition_id": "C2", "implemented": True, "correct": True},
    ]}
    (snap / "S1_result.json").write_text(json.dumps({"metrics": metrics, "state": state}), encoding="utf-8")
    return str(snap)


def _fill_gold(snapshot_dir, labels):
    path = os.path.join(snapshot_dir, "gold", "gold_labels.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())
    for row in rows:
        row["gold_verdict"], row["gold_source"] = labels[row["condition_id"]]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_export_is_blind_and_never_overwrites(snapshot):
    jr.cmd_export(snapshot)
    gold_csv = os.path.join(snapshot, "gold", "gold_labels.csv")
    with open(gold_csv, encoding="utf-8-sig") as f:
        text = f.read()
    assert "implemented" not in text and "faithful" not in text  # no judge output leaks in
    assert os.path.exists(os.path.join(snapshot, "gold", "code", "S1.txt"))

    _fill_gold(snapshot, {"C1": ("faithful", "rule"), "C2": ("incorrect", "derived")})
    jr.cmd_export(snapshot)  # second export must keep the labels
    with open(gold_csv, encoding="utf-8-sig") as f:
        assert "incorrect" in f.read()


def test_run_and_score_end_to_end(snapshot, monkeypatch):
    import evaluation.fidelity as fid

    def fake_judge(conditions, code, node_name="fidelity_judge", temperature=None):
        verdict = {"judge_haiku": "faithful", "judge_sonnet": "incorrect"}[node_name]
        return {c["condition_id"]: {"verdict": verdict} for c in conditions}

    monkeypatch.setattr(fid, "judge_conditions_llm", fake_judge)

    jr.cmd_export(snapshot)
    _fill_gold(snapshot, {"C1": ("faithful", "rule"), "C2": ("incorrect", "derived")})
    jr.cmd_run(snapshot, k=2, temperature=0.0, force=False)

    with pytest.raises(SystemExit):  # refuses to pay twice
        jr.cmd_run(snapshot, k=2, temperature=0.0, force=False)

    jr.cmd_score([snapshot])
    with open(os.path.join(snapshot, "gold", "judge_scores.json"), encoding="utf-8") as f:
        scores = json.load(f)[snapshot]["scores"]

    assert scores["v1_haiku"]["accuracy"] == 0.0     # both stored verdicts wrong
    assert scores["ast"]["accuracy"] == 1.0          # C1 faithful, C2 incorrect
    assert scores["hybrid"]["accuracy"] == 1.0       # AST decided both
    assert scores["llm_haiku"]["problems_caught"] == 0
    assert scores["llm_sonnet"]["false_alarms"] == 1
    assert scores["llm_sonnet"]["self_consistency"] == 1.0


def test_score_rejects_unlabeled_rows(snapshot):
    jr.cmd_export(snapshot)
    runs = {"meta": {"k": 1, "temperature": 0.0}, "items": []}
    with open(os.path.join(snapshot, "gold", "judge_runs.json"), "w") as f:
        json.dump(runs, f)
    with pytest.raises(SystemExit, match="Unlabeled"):
        jr.cmd_score([snapshot])
