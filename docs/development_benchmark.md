# Development Benchmark v1

## Purpose

`development-benchmark-v1` is a **development-only engineering benchmark** for comparing three views of the same eight reaction fields:

1. `rule-baseline-v1`
2. `llm-extractor-v1` replay
3. the subset of LLM fields retained after `verifier-v1`

The bundled dataset is synthetic. It exists to prove that the scoring, abstention, verification, scenario analysis, and blind-integrity contracts behave correctly before a real provider is connected.

**Do not report the bundled scores as real literature performance, real LLM performance, or publication benchmark results.**

## Why ordinary accuracy is not the headline metric

Scientific extraction contains many legitimately missing fields. If an evaluator counts `gold=null` and `prediction=null` as a correct answer, a model can appear accurate simply by abstaining on everything.

The development benchmark therefore gives no correctness credit for null-null agreement. It reports:

- **precision**: correct non-null predictions / all non-null predictions
- **recall**: correct non-null predictions / all non-null gold values
- **F1**: harmonic mean of precision and recall
- **attempted gold coverage**: gold-present fields on which the extractor returned a value / all gold-present fields
- **answer rate**: all non-null predictions / all scored field slots
- **hallucinations on absent**: non-null predictions where gold is absent
- **abstentions on present**: null predictions where a gold value exists

Per-field versions of these metrics are also emitted.

## Verifier effect

For the replayed LLM path, the benchmark additionally constructs a post-verification view in which only fields marked `accepted` are retained.

This allows the benchmark to measure the reliability/coverage tradeoff directly:

- precision before verification
- precision after verification
- recall before verification
- recall after verification
- precision delta
- recall delta
- **wrong-value block rate**: fraction of wrong non-null LLM values not accepted by the verifier
- **correct-value retention**: fraction of correct non-null LLM values retained by the verifier
- verifier status and reason-code counts

A verifier is therefore not judged only by whether precision rises. A verifier that rejects nearly everything may raise precision while destroying recall; the benchmark makes that visible.

## Synthetic scenarios

`examples/development_benchmark_v1.jsonl` contains clean and adversarial cases including:

- clean complete extraction
- missing fields
- multiple-value ambiguity
- source conflict
- wrong-reaction association
- wrong-entity association
- unsupported plausible values
- unit/format error
- an intentionally conservative verifier case to demonstrate recall loss

The replay responses are authored fixtures. They are not outputs from a hosted model.

## Run

Human-readable summary:

```bash
python tools/run_development_benchmark.py
```

Full machine-readable report:

```bash
python tools/run_development_benchmark.py --json
```

A custom development dataset can be supplied with:

```bash
python tools/run_development_benchmark.py --dataset path/to/nonblind_development.jsonl --json
```

Reviewer-only, blind-gold, sealed-prediction, and adjudication paths remain blocked by the blind-integrity guard.

## Dataset row contract

Each JSONL row represents one already-selected local evidence chunk and must be explicitly labelled:

```json
"split": "development"
```

It contains:

- `case_id`
- `scenario`
- `text`
- optional `context_sentences` for the rule baseline
- `gold`: exactly the eight scientific fields
- `llm_response`: exactly the same eight fields
- optional `verifier_overrides` for synthetic replay behavior

The eight fields are:

- `ee_percent`
- `yield_percent`
- `h2_pressure_bar`
- `temperature_c`
- `reaction_time_h`
- `solvent`
- `ligand`
- `substrate_class`

## What must happen before publication-level benchmarking

The next benchmark layer must replace replay fixtures with real model outputs and independently curated, non-blind development examples drawn from source documents that are legally accessible to the researcher.

For a meaningful scientific comparison:

1. freeze the prompt/extractor/verifier versions before evaluation;
2. curate gold values independently from the model outputs;
3. preserve source locators and evidence boundaries;
4. prevent DOI/source overlap between development and later held-out blind blocks;
5. report extractor performance and verifier effect separately;
6. keep identity normalization errors separate from extraction errors where possible;
7. do not tune on the final blind partition.

Historical Test B/C/D results are not automatically comparable to this benchmark because their schemas and evaluation conditions differ. They should be converted only under an explicit non-blind mapping protocol if reused later.
