# Scoring contract v1

Date: 2026-09-23. Schema: `benchmark/FIELD_SCHEMA_V1.json`. Graph: `docs/AGENT_V1_EXECUTION_GRAPH.md`.

## Evaluation unit

One **reaction-candidate evidence chunk × one scientific field**. Association between a prediction and its gold is by `candidate_id` and the recorded target anchor. Index-position pairing is forbidden.

## Denominators

For each field, starting from all chunk × field pairs with gold:

- remove `not_applicable` pairs entirely
- `gold_present` = pairs whose gold value is non-null
- `gold_absent` = pairs whose gold is null because the source does not report the field (`not_reported`)

## Outcome per pair

| Outcome | Condition |
|---|---|
| `correct` | prediction non-null, gold non-null, canonical match under the field's rule |
| `incorrect` | prediction non-null, gold non-null, no match |
| `hallucinated` | prediction non-null, gold absent |
| `miss` | prediction null, gold present, and the system gave no abstention reason |
| `abstain_reasonable` | prediction null with reason `not_reported`, `unresolved` or `ambiguous`, and gold absent |
| `abstain_unnecessary` | prediction null with an abstention reason, but gold present |
| `unresolved` | identity mentioned, not resolvable from the source |
| `ambiguous` | source supports two mutually exclusive readings |

`unresolved` and `ambiguous` are never counted as `incorrect`, and never enter answer coverage.

## Metrics, computed identically for Raw and for Verified

Let `answered = correct + incorrect + hallucinated`.

- **coverage** = `answered / (gold_present + gold_absent)`
- **selective accuracy** = `correct / (correct + incorrect)` — accuracy among answers on questions that have an answer
- **end-to-end accuracy** = `correct / gold_present`
- **hallucination rate on absent fields** = `hallucinated / gold_absent`
- **miss rate** = `miss / gold_present`
- **unresolved rate** = `unresolved / (gold_present + gold_absent)`
- **abstention quality** = `abstain_reasonable / (abstain_reasonable + abstain_unnecessary)`

## Verifier-specific metrics

- **evidence support rate** = supported fields / verified fields
- **unsupported answer rate** = unsupported fields / answered fields
- **reasonable abstention rate** = abstentions where gold is absent or the value was wrong, over all abstentions
- **wrong-value block rate** = raw-incorrect pairs the verifier withheld / raw-incorrect pairs
- **correct-value retention** = raw-correct pairs the verifier kept / raw-correct pairs

## Paired Raw vs Verified reporting

Both systems are scored on the identical set of chunk × field pairs, and the report is always a paired table:

```text
field            raw_acc  raw_cov  raw_sel  raw_unsup   ver_acc  ver_cov  ver_sel  ver_unsup
```

**Verifier benefit** is reported as the pair `(wrong-value block rate, correct-value retention)`, never as a bare accuracy delta. A verifier that answers less will always show a higher selective accuracy; that is not an improvement in extraction. A verifier run may be called beneficial only when it raises the wrong-value block rate while keeping correct-value retention high, and end-to-end accuracy does not fall.

## Raw integrity rule

Raw predictions are written and hashed before normalization and verification run. Raw metrics are computed from that frozen file. If a raw value is edited for any reason, the run is void and must be repeated under a new evaluation version. The verifier's output is a separate record; it never overwrites the raw record.

## Reporting rules

- Report `n` for every denominator; no percentage without its count.
- Report the number of chunks and the number of source papers separately; a paper is not a scoring unit.
- Never report a single scalar "accuracy" for the system without its coverage.
- Metrics computed under any earlier schema are not comparable and must not be placed in the same table.

## Verifier eligibility and coverage denominators

`benchmark/VERIFIER_COVERAGE_V1.json` assigns every field exactly one coverage mode. Three counts follow from it, and every verifier metric names which one it divides by.

| Count | Definition |
|---|---|
| `verifier_eligible_units` | chunk x field pairs that survive the `not_applicable` filter |
| `verifier_checked_units` | those pairs where `checked_by_verifier` is true, i.e. the field has a verifier and the raw value is non-null |
| `verifier_coverage_rate` | `verifier_checked_units / verifier_eligible_units` |

Report coverage as a rate over units. "8 of 12 fields" is not a coverage statement, because fields differ in how often they carry a value.

## Two status vocabularies, never merged

Raw prediction state: `answered`, `unresolved`, `ambiguous`, `not_reported`, `not_applicable`.
Verifier verdict: `supported`, `partial`, `unsupported`, `unresolved`, `ambiguous`, `not_checked_v1`, `not_verifiable_v1`.

A raw answer of `answered` with a verdict of `not_verifiable_v1` is a normal, legal combination.

- `not_checked_v1`: the field has no verifier in the contract, for example `reaction`.
- `not_verifiable_v1`: the field has a verifier, but this case's evidence representation does not allow a reliable verdict, for example a product drawn only in a scheme.

Neither is an error, and neither enters the verifier's support-rate denominator. Not checked is not unsupported; not verifiable is not incorrect.

## Four separate accounts

The report from `tools/score_agent_v1.py` keeps these apart on purpose.

**A. `a_raw_extractor`** — all 12 fields against gold. Denominator: all evaluable pairs. This is extractor performance and the headline number is `raw_end_to_end_accuracy`.

**B. `b_verifier_checked_subset`** — only pairs with `checked_by_verifier = true`. Denominator: `verifier_checked_units`. Carries `evidence_support_rate`, `unsupported_answer_rate`, `wrong_value_block_rate`, `correct_value_retention` and `verifier_checked_subset_selective_accuracy`.

**C. `c_unchecked_and_unverifiable`** — counts of `not_checked_v1` and `not_verifiable_v1`, with a per-field breakdown. These never appear in a B denominator.

**D. `d_final_stream`** — what a consumer receives after the verifier's `final_action`. Denominator: all evaluable pairs. `unverified_pass_through_units` counts values that reach the consumer without a verifier verdict; they are labelled `UNVERIFIED_PASS_THROUGH` and must never be described as verified. The headline number is `final_stream_end_to_end_accuracy`.

There is deliberately no single `verified_accuracy` in the report. Use `raw_end_to_end_accuracy`, `verifier_checked_subset_selective_accuracy` or `final_stream_end_to_end_accuracy`, and say which one.

## Final actions

`retain`, `suppress`, `flag_review`, `pass_through_unchecked`. Only `suppress` removes a value from the final stream. `pass_through_unchecked` keeps a raw answer that no verifier examined.
