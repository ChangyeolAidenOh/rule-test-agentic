# Judge Reliability Study — Analysis Plan

> Committed together with the v1 gold labels and **before** any v2-prompt judge output
> (`judge_runs.json`) or score (`judge_scores.*`) exists. Anything not specified here
> is exploratory and will be labeled as such.

## 1. Question

How often does each Business Rule Fidelity judge agree with a human gold label,
and does a hybrid design (deterministic AST check + LLM fallback) reduce judge error
compared with the v1 LLM-only judge?

## 2. Two evaluation targets — kept separate

| Target | Question | Status in this study |
|---|---|---|
| **Implementation Fidelity** | Does the generated code implement the spec row (`parameter / operator / value`)? | Measured (gold labels) |
| **Specification Validity** | Does the spec row itself faithfully and consistently encode the raw rule? | **Not measured.** Issues found incidentally are recorded as cases, not rates (§8) |

Fidelity is only as meaningful as the spec it is measured against. This study scores
judges on fidelity; spec validity is a separate follow-up task.

## 3. Data

| Snapshot | Conditions | Code | Role for the AST judge |
|---|---|---|---|
| `results_snapshot_v1` | 17 | frozen v1 pipeline output | **in-sample**: the AST checker was designed after inspecting v1 S2-C2 and S4-C1 |
| `results_snapshot_v2` | 26 | frozen output generated after the AST checker existed | **out-of-sample** |

Judges see exactly the code stored in each snapshot (`gold/code/S*.txt`).

## 4. Gold labels

- Single annotator (repository owner), following `gold/LABELING_PROTOCOL.md`.
- Verdict is judged against the spec row's `parameter / operator / value`, as fixed in the protocol before labeling.
- **v1 gold labels are frozen** at the commit that adds this file. No post-hoc changes to verdicts or tags,
  including when a label turns out to be interpretation-dependent (handled by §6 instead).
- v2 gold labels follow the same rules and are frozen at their own commit, made before
  `run` is executed on `results_snapshot_v2`.
- Labels are supported by boundary-test evidence (`gold/boundary_test_evidence.csv`).
- v1 label distribution at freeze: 15 faithful, 2 incorrect, 0 missing; source: 10 rule, 7 derived.

## 5. Judges

| Judge | Description |
|---|---|
| `v1_haiku` | verdicts stored by the v1 pipeline (verdict-first prompt, Haiku) — no new calls |
| `ast` | deterministic boundary check; may return `undetermined` |
| `llm_haiku` | v2 prompt (evidence-first, line-numbered code), Haiku, k samples, majority vote |
| `llm_sonnet` | v2 prompt, Sonnet, k samples, majority vote |
| `hybrid` | `ast`, falling back to `llm_sonnet` when `ast` is undetermined (the deployed design) |

Temperature 0 (the deployed configuration). k is recorded in `judge_runs.json`.
`undetermined` counts as *flagged for human review* (conservative), so it counts as a
catch on a gold problem and as a false alarm on a gold `faithful` row.

## 6. Analyses (pre-specified — exactly these, per snapshot and pooled)

| Analysis | Rows | Purpose |
|---|---|---|
| **Primary** | all rows | main result, pre-registered rule |
| **Sensitivity** | excluding rows tagged `ambiguous` | does the result depend on interpretation-dependent labels? |
| **Exposure split** | `seen` vs `unseen` rows, reported separately | were labels on rows whose judge output had been seen different? |

v1 counts at freeze: primary 17, excl_ambiguous 15, seen 8, unseen 9.

Metrics per judge: accuracy with Wilson 95% CI; problems caught / gold problems;
false alarms; coverage and accuracy-on-decided (AST); self-consistency across k (LLM).

## 7. Interpretation rules (fixed before seeing results)

1. **No significance tests.** With n ≤ 26 per snapshot, differences are reported
   descriptively with Wilson 95% CIs. Overlapping CIs are described as
   "not distinguishable at this sample size".
2. A comparison (e.g. hybrid vs v1_haiku) is called **robust** only if its direction is
   the same in Primary and Sensitivity. Otherwise it is reported as
   **sensitive to the ambiguous rows**, with both numbers shown.
3. A v1 judge verdict is called a **judge error** only after scoring against gold.
   Before scoring, v1_haiku on S2-C2 is a *candidate* judge error, not a finding.
4. Subsets with 0 gold problems cannot support claims about problem detection;
   such cells are reported but not interpreted.
5. No conclusion is assumed in advance; this section fixes how results will be read,
   not what they will be.

## 8. Known limitations (disclosed up front)

- **Single annotator**; no inter-annotator agreement in the primary analysis.
- **Same model family**: LLM judges are Claude models. An optional second annotation by
  Claude, if done, is reported as a label-quality check only, never as gold.
- **Exposure not captured by tags**: before labeling S1-C1 and S1-C2, the annotator saw
  a worked example of the labeling procedure on **a different run's** S1 code
  (simple thresholds, both faithful). The v1 file was frozen without a tag for this.
- **AST in-sample on v1** (see §3).
- **Interpretation-dependent labels** (tagged `ambiguous`):
  - v1 S2-C2: the spec's parameter (`annual_hospitalization_days_used lt 180`, days already used)
    and its description ("total days must not exceed 180", including the current claim)
    refer to different quantities. Labeled `faithful` against the parameter/operator/value.
  - v1 S4-C5: the spec targets `surrender_value_before_floor ge 0` while its description says
    "floor at zero"; the code floors the *final* value and allows a negative pre-floor value.
    Labeled `incorrect` per the protocol. This likely reflects a mismatch between the spec's
    formal encoding and its intent rather than a code defect; it documents a limit on how the
    label can be interpreted and is **not** grounds to change the label.
- **Spec-validity cases are incidental**: the issues above were noticed during fidelity
  labeling, not found by a systematic spec review. They are reported as the number of cases
  identified (2 of 17 v1 rows), not as an error rate or detection rate.

## 9. Out of scope / follow-up

- Specification Validity evaluation: a separate, pre-specified labeling pass per spec row
  (consistent with its description? with the raw rule?).
- Improving Node 1 so that actions (e.g. "floor at zero") are not encoded as conditions on
  intermediate variables.
