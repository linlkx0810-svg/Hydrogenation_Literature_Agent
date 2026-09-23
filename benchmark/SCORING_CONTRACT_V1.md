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
