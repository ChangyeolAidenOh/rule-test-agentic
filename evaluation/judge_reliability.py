"""Judge reliability study for Business Rule Fidelity.

Question: how often does each fidelity judge agree with a human gold label?

Judges compared (all on the SAME frozen code snapshot):
  v1_haiku    stored verdicts from the v1 pipeline (verdict-first prompt, Haiku)
  ast         deterministic AST boundary check (may return `undetermined`)
  llm_haiku   v2 judge prompt (evidence-first, line-numbered code), Haiku, k samples
  llm_sonnet  v2 judge prompt, Sonnet, k samples
  hybrid      ast, falling back to llm_sonnet majority when ast is undetermined
              (this is what the pipeline runs)

Workflow (per snapshot directory, e.g. results_snapshot_v1):
  1. export   writes <snapshot>/gold/gold_labels.csv (blank labels), line-numbered
              code files, and the labeling protocol. Judge outputs are NOT included,
              so labeling is blind.
  2. (human)  fill gold_source and gold_verdict in gold_labels.csv
  3. run      calls the LLM judges and stores raw verdicts in judge_runs.json
              (refuses to overwrite unless --force, to avoid paying twice)
  4. score    compares every judge to gold; no API calls; can be re-run freely

Usage:
  python -m evaluation.judge_reliability export results_snapshot_v1
  python -m evaluation.judge_reliability run    results_snapshot_v1 --k 3
  python -m evaluation.judge_reliability score  results_snapshot_v1 [results_snapshot_v2 ...]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ast_fidelity import check_conditions_ast  # noqa: E402

GOLD_DIR = "gold"
GOLD_FILE = "gold_labels.csv"
RUNS_FILE = "judge_runs.json"
SCORE_JSON = "judge_scores.json"
SCORE_MD = "judge_scores.md"

VERDICTS = {"faithful", "incorrect", "missing"}
SOURCES = {"rule", "derived"}
PROBLEM = {"incorrect", "missing"}
JUDGES = ["v1_haiku", "ast", "llm_haiku", "llm_sonnet", "hybrid"]

# Note tags written by the annotator (see LABELING_PROTOCOL.md)
KNOWN_TAGS = {"seen", "ambiguous", "mixed", "direction"}
# Pre-specified analysis subsets (docs/judge_reliability_analysis_plan.md).
# Each entry: (name, row filter on the annotator's tags). Do not add subsets after
# seeing results — extra cuts invite selective reporting.
SUBSETS = [
    ("primary", lambda tags: True),                      # all rows, pre-registered rule
    ("excl_ambiguous", lambda tags: "ambiguous" not in tags),  # sensitivity
    ("seen", lambda tags: "seen" in tags),               # exposure split
    ("unseen", lambda tags: "seen" not in tags),         # exposure split
]

LABELING_PROTOCOL = """# Gold labeling protocol

Label each condition in `gold_labels.csv` against the generated code in `code/<scenario>.txt`.

## gold_verdict — judge against the SPEC row (parameter / operator / value), not against your own reading of the business rule
- `faithful`: the code enforces the same boundary as the spec.
  Equivalent forms count: `x > 90` for `gt 90`; `if x < 0: raise` enforces `x >= 0`;
  `if x > 180: raise` enforces `x <= 180`; for whole-number units `x >= 91` equals `x > 90`.
- `incorrect`: implemented, but the threshold sits on the other side of the boundary
  or uses a different value (e.g. spec `gt 0`, code only rejects `x < 0`, so 0 is allowed).
- `missing`: no code enforces the condition.

## gold_source — compare with the ORIGINAL rule text (column `raw_rule`)
- `rule`: stated in, or directly implied by, the original rule text.
- `derived`: an input-validation or sanity constraint the original text does not state.

## note — start with tags (separate with `;`), then free text
- `seen`: you saw a judge verdict or an analysis of this row before labeling
- `ambiguous`: the label depends on how the spec row is read (explain after `:`)
- `mixed`: the condition is implemented differently in different places
- `direction`: boundary is right but applied in the opposite direction

Use `note` for anything ambiguous. Do not look at judge outputs before labeling.
Scoring reports results with and without `seen` / `ambiguous` rows.
"""


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------

def load_snapshot(snapshot_dir: str) -> list[dict]:
    """Load frozen scenario artifacts: rule spec, generated code, stored v1 verdicts."""
    scenarios = []
    for path in sorted(glob.glob(os.path.join(snapshot_dir, "S*_result.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        state = data.get("state", {})
        stored = data.get("metrics", {}).get("fidelity_results") or state.get("fidelity_results", [])
        scenarios.append({
            "scenario_id": state.get("scenario_id") or os.path.basename(path).split("_")[0],
            "raw_rule": state.get("raw_rule", ""),
            "conditions": state.get("rule_spec", {}).get("conditions", []),
            "code": state.get("generated_code", ""),
            "stored": {r.get("condition_id"): r for r in stored},
        })
    if not scenarios:
        raise SystemExit(f"No S*_result.json files found in {snapshot_dir}")
    return scenarios


def stored_verdict(r: dict | None) -> str:
    """Map a stored v1/v2 fidelity result to a verdict."""
    if not r:
        return "undetermined"
    if "verdict" in r:
        return r["verdict"]
    if r.get("implemented") and r.get("correct"):
        return "faithful"
    if r.get("implemented"):
        return "incorrect"
    return "missing"


# ---------------------------------------------------------------------------
# Statistics (pure functions — unit tested)
# ---------------------------------------------------------------------------

def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def majority(votes: list[str]) -> str:
    """Majority verdict; ties or empty -> undetermined."""
    if not votes:
        return "undetermined"
    counts = Counter(votes).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return "undetermined"
    return counts[0][0]


def parse_tags(note: str) -> set[str]:
    """Extract known tags from a note such as 'seen; ambiguous: 이후 포함 여부; ...'."""
    tags = set()
    for part in (note or "").split(";"):
        head = part.split(":", 1)[0].strip().lower()
        if head in KNOWN_TAGS:
            tags.add(head)
    return tags


def is_flagged(verdict: str) -> bool:
    """A verdict sends the condition to human review if it is not `faithful`.

    `undetermined` counts as flagged: in the pipeline an undecided condition
    must be reviewed by the developer, so it is a (conservative) flag.
    """
    return verdict != "faithful"


def score_judge(pairs: list[tuple[str, str]]) -> dict:
    """Score one judge. pairs = [(gold_verdict, judge_verdict), ...]."""
    n = len(pairs)
    correct = sum(1 for g, j in pairs if g == j)
    decided = [(g, j) for g, j in pairs if j != "undetermined"]
    decided_correct = sum(1 for g, j in decided if g == j)

    positives = [(g, j) for g, j in pairs if g in PROBLEM]
    negatives = [(g, j) for g, j in pairs if g not in PROBLEM]
    caught = sum(1 for _, j in positives if is_flagged(j))
    false_alarms = sum(1 for _, j in negatives if is_flagged(j))
    flagged = caught + false_alarms

    lo, hi = wilson_interval(correct, n)
    return {
        "n": n,
        "accuracy": correct / n if n else None,
        "accuracy_ci95": [lo, hi],
        "coverage": len(decided) / n if n else None,
        "accuracy_on_decided": decided_correct / len(decided) if decided else None,
        "gold_problems": len(positives),
        "problems_caught": caught,
        "recall": caught / len(positives) if positives else None,
        "false_alarms": false_alarms,
        "precision": caught / flagged if flagged else None,
    }


def self_consistency(samples: list[list[str]]) -> float | None:
    """Share of conditions on which all k samples agree."""
    usable = [s for s in samples if len(s) > 1]
    if not usable:
        return None
    return sum(1 for s in usable if len(set(s)) == 1) / len(usable)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_export(snapshot_dir: str) -> None:
    scenarios = load_snapshot(snapshot_dir)
    gold_dir = os.path.join(snapshot_dir, GOLD_DIR)
    code_dir = os.path.join(gold_dir, "code")
    os.makedirs(code_dir, exist_ok=True)

    for sc in scenarios:
        numbered = "\n".join(f"{i:4d}: {line}" for i, line in enumerate(sc["code"].split("\n"), 1))
        with open(os.path.join(code_dir, f"{sc['scenario_id']}.txt"), "w", encoding="utf-8") as f:
            f.write(numbered + "\n")

    with open(os.path.join(gold_dir, "LABELING_PROTOCOL.md"), "w", encoding="utf-8") as f:
        f.write(LABELING_PROTOCOL)

    gold_path = os.path.join(gold_dir, GOLD_FILE)
    if os.path.exists(gold_path):
        print(f"{gold_path} already exists — not overwritten (it may contain your labels).")
        return

    fields = ["scenario_id", "condition_id", "parameter", "operator", "value", "unit",
              "description", "raw_rule", "gold_source", "gold_verdict", "note"]
    n = 0
    with open(gold_path, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for sc in scenarios:
            for c in sc["conditions"]:
                w.writerow({
                    "scenario_id": sc["scenario_id"],
                    "condition_id": c.get("condition_id", ""),
                    "parameter": c.get("parameter", ""),
                    "operator": c.get("operator", ""),
                    "value": c.get("value", ""),
                    "unit": c.get("unit", ""),
                    "description": c.get("description", ""),
                    "raw_rule": sc["raw_rule"],
                    "gold_source": "",
                    "gold_verdict": "",
                    "note": "",
                })
                n += 1
    print(f"Exported {n} conditions from {len(scenarios)} scenarios -> {gold_path}")
    print(f"Code for labeling: {code_dir}/  |  Protocol: {gold_dir}/LABELING_PROTOCOL.md")


def cmd_run(snapshot_dir: str, k: int, temperature: float, force: bool) -> None:
    from config.settings import MODEL_HAIKU, MODEL_SONNET, NODE_MODELS
    from evaluation.fidelity import judge_conditions_llm

    runs_path = os.path.join(snapshot_dir, GOLD_DIR, RUNS_FILE)
    if os.path.exists(runs_path) and not force:
        raise SystemExit(f"{runs_path} exists. Use --force to re-run (this costs API calls).")

    # Register judge models without touching settings.py (same dict object get_llm reads).
    NODE_MODELS.setdefault("judge_haiku", MODEL_HAIKU)
    NODE_MODELS.setdefault("judge_sonnet", MODEL_SONNET)
    judges = {"llm_haiku": "judge_haiku", "llm_sonnet": "judge_sonnet"}

    scenarios = load_snapshot(snapshot_dir)
    items = []
    for sc in scenarios:
        conds = sc["conditions"]
        ast_by_id = {r["condition_id"]: r["verdict"] for r in check_conditions_ast(conds, sc["code"])}
        samples: dict[str, dict[str, list[str]]] = {cid: {j: [] for j in judges} for cid in ast_by_id}

        for judge, node in judges.items():
            for rep in range(k):
                print(f"  {sc['scenario_id']} {judge} sample {rep + 1}/{k}")
                out = judge_conditions_llm(conds, sc["code"], node_name=node, temperature=temperature)
                for cid in samples:
                    samples[cid][judge].append(out.get(cid, {}).get("verdict", "undetermined"))

        for c in conds:
            cid = c.get("condition_id")
            items.append({
                "scenario_id": sc["scenario_id"],
                "condition_id": cid,
                "v1_haiku": stored_verdict(sc["stored"].get(cid)),
                "ast": ast_by_id.get(cid, "undetermined"),
                **samples.get(cid, {}),
            })

    payload = {
        "meta": {
            "snapshot": snapshot_dir,
            "k": k,
            "temperature": temperature,
            "models": {"llm_haiku": MODEL_HAIKU, "llm_sonnet": MODEL_SONNET},
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "items": items,
    }
    with open(runs_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(items)} judged conditions -> {runs_path}")


def load_gold(snapshot_dir: str) -> dict[tuple[str, str], dict]:
    path = os.path.join(snapshot_dir, GOLD_DIR, GOLD_FILE)
    gold, problems = {}, []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["scenario_id"], row["condition_id"])
            v = row.get("gold_verdict", "").strip().lower()
            s = row.get("gold_source", "").strip().lower()
            if v not in VERDICTS:
                problems.append(f"{key}: gold_verdict '{v}'")
            if s not in SOURCES:
                problems.append(f"{key}: gold_source '{s}'")
            note = row.get("note", "")
            gold[key] = {"verdict": v, "source": s, "note": note, "tags": parse_tags(note)}
    if problems:
        raise SystemExit("Unlabeled or invalid rows in " + path + ":\n  " + "\n  ".join(problems))
    return gold


def resolve_items(runs: dict) -> list[dict]:
    """Collapse k samples to majority and build the hybrid verdict."""
    out = []
    for it in runs["items"]:
        r = dict(it)
        for j in ("llm_haiku", "llm_sonnet"):
            r[f"{j}_samples"] = it.get(j, [])
            r[j] = majority(it.get(j, []))
        r["hybrid"] = r["ast"] if r["ast"] != "undetermined" else r["llm_sonnet"]
        out.append(r)
    return out


def score_items(items: list[dict], gold: dict) -> dict:
    results = {}
    for judge in JUDGES:
        pairs = [(gold[(i["scenario_id"], i["condition_id"])]["verdict"], i[judge]) for i in items]
        results[judge] = score_judge(pairs)
    for j in ("llm_haiku", "llm_sonnet"):
        results[j]["self_consistency"] = self_consistency([i[f"{j}_samples"] for i in items])
    return results


def _fmt(x, pct=True):
    if x is None:
        return "n/a"
    return f"{x:.0%}" if pct else str(x)


def render_markdown(label: str, scores: dict, items: list[dict], gold: dict, meta: dict) -> str:
    lines = [f"## {label}", ""]
    lines.append(f"k = {meta.get('k')}, temperature = {meta.get('temperature')}, "
                 f"conditions = {len(items)}")
    n_prob = sum(1 for v in gold.values() if v["verdict"] in PROBLEM)
    n_derived_prob = sum(1 for v in gold.values() if v["verdict"] in PROBLEM and v["source"] == "derived")
    lines.append(f"gold problems = {n_prob} (of which derived = {n_derived_prob})")
    lines.append("")
    lines.append("| judge | accuracy (95% CI) | coverage | acc. on decided | problems caught | false alarms | self-consistency |")
    lines.append("|---|---|---|---|---|---|---|")
    for j in JUDGES:
        s = scores[j]
        lo, hi = s["accuracy_ci95"]
        caught = f"{s['problems_caught']}/{s['gold_problems']}"
        lines.append(
            f"| {j} | {_fmt(s['accuracy'])} ({lo:.0%}–{hi:.0%}) | {_fmt(s['coverage'])} | "
            f"{_fmt(s['accuracy_on_decided'])} | {caught} | {s['false_alarms']} | "
            f"{_fmt(s.get('self_consistency'))} |"
        )
    lines.append("")
    lines.append("Disagreements with gold:")
    lines.append("")
    lines.append("| scenario | cond | source | gold | " + " | ".join(JUDGES) + " |")
    lines.append("|---|---|---|---|" + "---|" * len(JUDGES))
    for i in items:
        g = gold[(i["scenario_id"], i["condition_id"])]
        if any(i[j] != g["verdict"] for j in JUDGES):
            lines.append(
                f"| {i['scenario_id']} | {i['condition_id']} | {g['source']} | {g['verdict']} | "
                + " | ".join(i[j] for j in JUDGES) + " |"
            )
    lines.append("")
    return "\n".join(lines)


def sensitivity(items: list[dict], gold: dict) -> dict:
    """Score every judge on each pre-specified subset in SUBSETS."""
    out = {}
    for name, include in SUBSETS:
        keep = [i for i in items
                if include(gold[(i["scenario_id"], i["condition_id"])].get("tags", set()))]
        if not keep:
            continue
        out[name] = {
            "n": len(keep),
            "gold_problems": sum(
                1 for i in keep if gold[(i["scenario_id"], i["condition_id"])]["verdict"] in PROBLEM
            ),
            "scores": score_items(keep, gold),
        }
    return out


def render_sensitivity(label: str, sens: dict) -> str:
    names = list(sens.keys())
    lines = [f"### Pre-specified subsets — {label}", ""]
    lines.append("Accuracy (problems caught / gold problems). primary = all rows; "
                 "excl_ambiguous = sensitivity analysis; seen / unseen = exposure split "
                 "(rows whose judge output was seen before labeling vs not). "
                 "Descriptive only: no significance tests at this sample size.")
    lines.append("")
    header = " | ".join(f"{n} (n={sens[n]['n']}, problems={sens[n]['gold_problems']})" for n in names)
    lines.append(f"| judge | {header} |")
    lines.append("|---|" + "---|" * len(names))
    for j in JUDGES:
        cells = []
        for n in names:
            sc = sens[n]["scores"][j]
            cells.append(f"{_fmt(sc['accuracy'])} ({sc['problems_caught']}/{sc['gold_problems']})")
        lines.append(f"| {j} | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def cmd_score(snapshot_dirs: list[str]) -> None:
    all_items, all_gold, sections, report = [], {}, [], {}
    for snap in snapshot_dirs:
        with open(os.path.join(snap, GOLD_DIR, RUNS_FILE), encoding="utf-8") as f:
            runs = json.load(f)
        gold = load_gold(snap)
        items = resolve_items(runs)
        missing = [(i["scenario_id"], i["condition_id"]) for i in items
                   if (i["scenario_id"], i["condition_id"]) not in gold]
        if missing:
            raise SystemExit(f"Conditions without gold rows in {snap}: {missing}")

        scores = score_items(items, gold)
        sens = sensitivity(items, gold)
        report[snap] = {"meta": runs["meta"], "scores": scores,
                        "sensitivity": {k: {**v, "scores": v["scores"]} for k, v in sens.items()}}
        sections.append(render_markdown(snap, scores, items, gold, runs["meta"]))
        sections.append(render_sensitivity(snap, sens))

        tag = os.path.basename(os.path.normpath(snap))
        for i in items:
            all_items.append({**i, "scenario_id": f"{tag}:{i['scenario_id']}"})
        for (sid, cid), v in gold.items():
            all_gold[(f"{tag}:{sid}", cid)] = v

    if len(snapshot_dirs) > 1:
        pooled = score_items(all_items, all_gold)
        pooled_sens = sensitivity(all_items, all_gold)
        report["pooled"] = {"scores": pooled, "sensitivity": pooled_sens}
        sections.append(render_markdown("pooled", pooled, all_items, all_gold, {"k": "mixed", "temperature": "mixed"}))
        sections.append(render_sensitivity("pooled", pooled_sens))

    md = "# Fidelity judge reliability\n\n" + "\n".join(sections)
    out_dir = os.path.join(snapshot_dirs[0], GOLD_DIR)
    with open(os.path.join(out_dir, SCORE_JSON), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, SCORE_MD), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"Saved -> {out_dir}/{SCORE_MD}, {SCORE_JSON}")


def main():
    p = argparse.ArgumentParser(description="Fidelity judge reliability study")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="write blank gold-label template for a snapshot")
    e.add_argument("snapshot")

    r = sub.add_parser("run", help="run LLM judges on a snapshot (API calls)")
    r.add_argument("snapshot")
    r.add_argument("--k", type=int, default=3, help="samples per LLM judge (default 3)")
    r.add_argument("--temperature", type=float, default=0.0)
    r.add_argument("--force", action="store_true")

    s = sub.add_parser("score", help="score judges against gold (no API calls)")
    s.add_argument("snapshots", nargs="+")

    args = p.parse_args()
    if args.cmd == "export":
        cmd_export(args.snapshot)
    elif args.cmd == "run":
        cmd_run(args.snapshot, args.k, args.temperature, args.force)
    else:
        cmd_score(args.snapshots)


if __name__ == "__main__":
    main()
