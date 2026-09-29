# Agent v1.0 artifact contracts

Date: 2026-09-23. Graph: `docs/AGENT_V1_EXECUTION_GRAPH.md`. Schema: `benchmark/FIELD_SCHEMA_V1.json`. Metrics: `benchmark/SCORING_CONTRACT_V1.md`.

The chain is a sequence of **append-only artifacts**. A stage never edits the artifact it read; it writes a new one. Artifacts are joined on `candidate_id`, never on list position.

```text
source.txt / source.pdf
  → raw_predictions.jsonl        + raw_predictions.freeze.json   (immutable from here on)
  → normalized_predictions.jsonl
  → verified_predictions.jsonl   + chain_manifest.json
  → score_report.json
```

## The invariant

Once `tools/freeze_raw_predictions.py` has run, `raw_predictions.jsonl` is immutable. It is forbidden to edit a raw value, write a verifier status or `verified=true` back into it, replace a raw ligand mention with its canonical form, attach a scorer result, or add any downstream key. `modules/artifact_chain.load_frozen_raw` enforces this: it rejects a record whose `verification_status` is anything but `unverified`, and rejects records carrying `canonical_values`, `verification`, `score`, `gold` or `correct`.

Every later stage re-verifies the raw hash before reading, so an edited raw file voids the run instead of silently producing a score.

## Stage contracts

### 1. Evidence candidate builder

| | |
|---|---|
| Input | source text (from a hash-verified source artifact) |
| Output | candidate windows: `candidate_id`, `evidence_text`, `evidence_start`, `evidence_end` |
| Allowed | deterministic anchoring on the ee/yield regex, `context_sentences = 2`, duplicate removal on `(start, end)` |
| Forbidden | ranking, top-k, model-based or manual selection; exporting its regex field values as Agent predictions |

Its regex values and `confidence` remain `rule-baseline-v1` selection signals. They are never shown to the LLM and never scored as Agent output.

### 2. Raw LLM extractor — `llm-extractor-v2`

| | |
|---|---|
| Input | one evidence chunk plus its provenance |
| Output | `raw_predictions.jsonl` |
| Allowed | strict JSON against `raw-extraction-schema-v2`; every field nullable; one abstention reason per null |
| Forbidden | canonical values, verifier status, scorer status, gold, correctness labels, confidence scores, free text, extra keys, repairing a schema violation |

Each record carries exactly: `candidate_id`, `source_artifact_id`, `evidence_start`, `evidence_end`, `evidence_sha256`, `values` (the 12 fields of `FIELD_SCHEMA_V1`), `abstention_reasons`, `model_name`, `extraction_version`, `prompt_version`, `schema_version`, `field_schema_version`, `verification_status = "unverified"`. `tools/freeze_raw_predictions.py` rejects any other key.

### 3. Raw freeze — `raw_predictions.freeze.json`

Separate artifact, never merged into the records. It pins `artifact`, `raw_predictions_sha256`, `record_count`, `candidate_ids_sha256`, `extraction_version`, `prompt_version`, `schema_version`, `field_schema_version`, `frozen: true`, and the counts of answered and null field values.

Downstream stages must, before reading a single record: verify the file hash, verify the candidate-id digest, verify the field-schema version, and verify the extractor, prompt and response-schema versions. Any mismatch **fails closed** — `FrozenArtifactError`, no partial run, no score.

### 4. Normalization — `prediction-normalizer-v1`

| | |
|---|---|
| Input | frozen raw records + source text |
| Output | `normalized_predictions.jsonl` |
| Allowed | resolve `ligand` through `modules/ligand_resolver.py` against the source; carry every other field through unchanged |
| Forbidden | editing the raw artifact; dropping `raw_value`; inventing substrate, product, catalyst or reaction ontologies |

Field policy: `ligand: ACTIVE`, every other field `PASS_THROUGH_V1`. Each field record keeps `raw_value` **and** `canonical_value`, plus `normalization_status` ∈ {`resolved`, `unresolved`, `ambiguous`, `not_applicable`, `not_reported`, `pass_through`}, `normalization_method`, `normalization_confidence`, `normalization_evidence`.

### 5. Evidence verifier — `evidence-verifier-v1.1`

| | |
|---|---|
| Input | frozen raw reference, the normalization record, the bound evidence window |
| Output | `verified_predictions.jsonl` + `chain_manifest.json` |
| Allowed | per field `supported`, `partial`, `unsupported`, `unresolved`, `ambiguous`, `not_checked_v1`, `not_verifiable_v1`; per candidate `accept`, `review`, `reject` |
| Forbidden | resolving entities itself, producing a value the extractor did not produce, correcting chemistry, writing into the raw or normalized artifacts |

The verifier no longer imports the resolver; a test asserts that. Called without a normalization record, the ligand comes back `unresolved` with reason `normalization_missing` rather than being quietly resolved.

Coverage is governed by `benchmark/VERIFIER_COVERAGE_V1.json`, which gives every field exactly one mode: `FULL_EVIDENCE_CHECK`, `NORMALIZATION_AWARE_CHECK`, `LITERAL_EVIDENCE_CHECK`, `EXPLICIT_STEREO_CHECK` or `NOT_CHECKED_V1`. `reaction` is `NOT_CHECKED_V1`: there is no reaction canonicalizer in v1 and a substring test would not be verification. `catalyst` and `product` accept only a literal mention and can never block. `stereochemical_outcome` reads explicit descriptors only and blocks only on an explicitly contradictory configuration.

Each verified row carries `raw_value`, `raw_state`, `canonical_value`, `verification_status`, `checked_by_verifier` and `final_action` ∈ {`retain`, `suppress`, `flag_review`, `pass_through_unchecked`}.

The four layers are distinct and must not be conflated:

```text
Raw LLM prediction  ≠  normalization output  ≠  verifier verdict  ≠  final stream
```

and, in particular, **unchecked pass-through is not a verified answer**. A value with `final_action = pass_through_unchecked` reaches the consumer labelled `UNVERIFIED_PASS_THROUGH`.

### 6. Scorer — `agent-v1-scorer-v2`

| | |
|---|---|
| Input | frozen raw records, verified records, gold records |
| Output | `score_report.json` |
| Allowed | four separate accounts per `SCORING_CONTRACT_V1`: raw extractor, verifier-checked subset, unchecked and unverifiable accounting, final stream |
| Forbidden | writing into any upstream artifact; joining by position; counting `unresolved` or `ambiguous` as incorrect; reporting verifier benefit as an accuracy delta |

A field is withheld only when its `final_action` is `suppress`. `not_checked_v1` and `not_verifiable_v1` are not withholdings, and both are excluded from every verifier denominator. The scorer reports four separate accounts — raw extractor, verifier-checked subset, unchecked and unverifiable accounting, and final stream — with the denominators defined in `benchmark/SCORING_CONTRACT_V1.md`.

## Join rule

`candidate_id` is the only join key across `raw`, `normalized`, `verified`, `gold` and `score`. The scorer reports `n_chunks_without_gold` rather than aligning what it cannot match, and a duplicate `candidate_id` fails the freeze.
