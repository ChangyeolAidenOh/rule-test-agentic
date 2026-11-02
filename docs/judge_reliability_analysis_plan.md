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
- Labels are supported by boundary-test evidence (`gold/boundary_test_evidence.csv`),
  produced by `gold/check_boundaries.py` (see §4.1).
- v1 label distribution at freeze: 15 faithful, 2 incorrect, 0 missing; source: 10 rule, 7 derived.

### 4.1 Boundary-test evidence (v1)

`gold/check_boundaries.py` strips the line numbers from `gold/code/S*.txt`, loads each
snapshot module, probes every condition at its threshold and adjacent values, and writes
`gold/boundary_test_evidence.csv` (17 conditions, 50 cases). Re-running it from `gold/`
must reproduce the committed CSV byte for byte.

What the evidence is and is not:

- **A test harness, not a formal verifier.** It checks 50 chosen cases (threshold and
  neighbours), not all inputs. A match means "no disagreement at the probed points".
- **Executes snapshot code with `exec()`.** Run it only on these trusted, committed
  snapshot files.
- **Snapshot-specific.** It calls the v1 code's internal helpers by name
  (e.g. `_is_age_surcharge_applicable`), so it does not run on other snapshots.
  v2 needs its own harness, written by the annotator under the same rules.
- **Two readings of a condition are used, chosen per row:**
  - *decision* — the condition's truth value is compared with the code's branch decision
    or with whether the input is accepted (S1, S2, S3-C1/C2, S4-C1–C4, S5);
  - *invariant* — the condition is treated as a property that must always hold, with
    `spec_expected` fixed to True (S3-C3, S4-C5).
  The protocol did not specify which reading to use. The S4-C5 mismatch arises under the
  invariant reading; under the decision reading the code's `max(value, 0)` is consistent
  with the condition. This is recorded as a limit on the evidence (§8), not a reason to
  change the frozen label.
- **Mixed probe paths within a condition:** S2-C2 uses the helper
  `_is_annual_limit_available` for 179/180 and the `apply_rule` validation path for 181.

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
- **Boundary evidence is case-based** (50 probed cases, §4.1) and mixes decision and
  invariant readings across rows; the protocol did not fix which reading applies.
- **Spec-validity cases are incidental**: the issues above were noticed during fidelity
  labeling, not found by a systematic spec review. They are reported as the number of cases
  identified (2 of 17 v1 rows), not as an error rate or detection rate.

## 9. Out of scope / follow-up

- Specification Validity evaluation: a separate, pre-specified labeling pass per spec row
  (consistent with its description? with the raw rule?).
- Improving Node 1 so that actions (e.g. "floor at zero") are not encoded as conditions on
  intermediate variables.

## 10. Amendments

The original plan was committed in `eb978b1` together with the frozen v1 gold labels.
Amendments are recorded here; none changes the analyses (§6) or the interpretation
rules (§7), and each was committed before the corresponding judge output existed.

| # | Change | Before any judge output? |
|---|---|---|
| 1 | Added §4.1 (boundary-test evidence: case-based harness, `exec()` caveat, snapshot-specific helpers, decision vs invariant readings, mixed probe paths in S2-C2), the reference to `gold/check_boundaries.py` in §4, and one limitation in §8. Committed `gold/check_boundaries.py`, which produced the already-committed `boundary_test_evidence.csv`. | Yes — no `judge_runs.json` existed |
