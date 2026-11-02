# Gold labeling protocol

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

Use `note` for anything ambiguous. Do not look at judge outputs before labeling.
