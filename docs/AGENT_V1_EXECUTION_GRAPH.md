# Agent v1.0 formal execution graph

Date: 2026-09-23. Status: the whole graph runs offline on this branch through `agent.py extract-raw`, `run-chain` and `score`. Artifact-level rules are in `docs/AGENT_V1_ARTIFACT_CONTRACTS.md`; remaining gaps are listed in `benchmark/agent_v1_system_freeze_candidate.json`.

## The single formal graph

```text
frozen source artifact (article/SI PDF, hash-verified)
  → deterministic text extraction (pypdf, page order, no OCR)
  → evidence candidate builder            [reaction_candidate_extraction.extract_reaction_candidates]
  → RAW LLM EXTRACTOR                     [raw_llm_extractor_v2.llm-extractor-v2, one chunk per call, strict JSON]
  → raw prediction                        ← FROZEN AND HASHED HERE, before anything may read it
  → entity normalization                  [ligand_resolver.resolve_ligand_mention]
  → evidence verifier                     [extraction_verifier.evidence-verifier-v1, deterministic]
  → verified prediction
  → scorer                                [field-atomic, FIELD_SCHEMA_V1 + SCORING_CONTRACT_V1]
```

One line: `source → evidence builder → Raw LLM → frozen raw prediction → normalization → evidence verifier → verified prediction → scorer`.

## Module status

| Module | Role in v1.0 | Status |
|---|---|---|
| `modules/reaction_candidate_extraction.py` | evidence candidate builder | `ACTIVE_IN_FORMAL_RUN` (field values demoted, see below) |
| `modules/raw_llm_extractor_v2.py` | Raw LLM extractor (`llm-extractor-v2`, 12 fields) | `ACTIVE_IN_FORMAL_RUN` |
| `tools/freeze_raw_predictions.py` | raw prediction freeze | `ACTIVE_IN_FORMAL_RUN` |
| `modules/openai_responses_provider.py` | provider transport | `ACTIVE_IN_FORMAL_RUN` |
| `modules/llm_extractor.py` (`llm-extractor-v1`, 8 fields) | historical implementation | `LEGACY_NOT_USED` |
| `modules/prediction_normalizer.py` | normalization stage (`ligand` ACTIVE, other fields `PASS_THROUGH_V1`) | `ACTIVE_IN_FORMAL_RUN` |
| `modules/ligand_resolver.py` | ligand resolution, called by the normalizer | `ACTIVE_IN_FORMAL_RUN` |
| `modules/artifact_chain.py` | fail-closed frozen-artifact loader | `ACTIVE_IN_FORMAL_RUN` |
| `tools/run_chain.py` | normalization + verification runner | `ACTIVE_IN_FORMAL_RUN` |
| `tools/score_agent_v1.py` | scorer implementing `SCORING_CONTRACT_V1` | `ACTIVE_IN_FORMAL_RUN` |
| `modules/extraction_verifier.py` | evidence verifier | `ACTIVE_IN_FORMAL_RUN` |
| `modules/verifier.py` (LLM verifier-v1) | second-opinion verifier | `DEFERRED_TO_V1_1` — not in the v1.0 graph |
| `modules/reaction_data_extraction.py` | paper-level Stage 5 extractor | `LEGACY_NOT_USED` |
| `modules/literature_search.py`, `pdf_download.py`, `title_abstract_screening.py`, `fulltext_screening.py` | corpus construction | `DEVELOPMENT_ONLY` |
| `tools/run_benchmark.py` | synthetic contract check | `DEVELOPMENT_ONLY` |
| `tools/run_trust_benchmark.py` | baseline-vs-verifier contract check | `DEVELOPMENT_ONLY` (must stop calling the rule baseline "raw") |
| `tools/score_blind_benchmark.py` | adjudication CSV scorer | `LEGACY_NOT_USED` until its field vocabulary is replaced by `FIELD_SCHEMA_V1` |

Only one verifier runs in the formal graph. `verifier.py` is deferred rather than deleted: it is a genuine second-opinion layer, but running two model stages in v1.0 doubles cost and gives two status vocabularies to reconcile, and only the deterministic verifier is wired into the CLI and CI today. Reinstating it creates Agent v1.1, not a variant of v1.0.

## Stage contracts

### 1. Evidence candidate builder

Deterministic and model-free. Its only formal output is the candidate window: `candidate_id`, `evidence_text`, `evidence_start`, `evidence_end`, and the source artifact id.

- anchor: a sentence matching the ee or yield regular expression
- window: anchor ± `context_sentences = 2`
- duplicates: dropped on `(start, end)`
- no ranking, no top-k, no model-based or manual selection

Its regex field values (`ee_percent` … `substrate_class`) and its `confidence` are **selection signals and the `rule-baseline-v1` reference only**. They are not shown to the LLM, are not written into the raw prediction record, and are never scored as Agent v1.0 output. Any comparison against them must be labelled `rule-baseline-v1`, never `raw`.

### 2. Raw LLM extractor

Input: one evidence chunk plus its provenance, nothing else — no other chunk, no paper-level context, no baseline value, no gold, no retrieval.
Prompt: `llm-extractor-prompt-v2`, frozen candidate.
Output: strict JSON against the frozen response schema, every field nullable, no extra keys, no free text. A schema violation raises; it is never repaired into a prediction.

The raw prediction file is written and hashed by `tools/freeze_raw_predictions.py` before normalization or verification runs; that tool also refuses records already marked verified, duplicate candidate ids, version drift, and any abstention reason attached to a field that carries a value. Nothing downstream may edit the file. Raw metrics are computed from it alone.

Every null carries one of `not_reported`, `not_applicable`, `unresolved`, `ambiguous`, so the five value states of `FIELD_SCHEMA_V1` survive into scoring instead of collapsing into one null.

Offline operation: `agent.py extract-raw` runs as a dry run that emits only request envelopes, or replays saved provider responses. CI exercises both, plus the freeze and its verification, without a model call.

### 3. Entity normalization

`ligand_resolver` maps a raw mention to `{raw_mention, canonical_id, canonical_name, status, confidence, evidence, candidates, resolution_method}` with `status ∈ {resolved, unresolved, ambiguous}`.

- explicit registry name → resolve
- paper-local alias with an explicit in-source definition → resolve
- alias without a definition → `unresolved`
- contradictory definitions → `ambiguous`
- never guess across papers

Normalization is a separate record. It annotates the raw value; it does not replace it, and the raw value stays readable next to it.

### 4. Evidence verifier

Deterministic. Inputs: one normalized field value and the exact evidence window bound to its candidate. First it re-slices `source_text[start:end]` and compares it to the stored evidence: on mismatch or invalid offsets every field of that candidate is `unsupported` and the candidate is rejected.

Allowed per-field outcomes: `supported`, `partial`, `unsupported`, `unresolved`, `ambiguous`, `not_checked_v1`.

`evidence-verifier-v1` implements checks for 8 of the 12 fields. `reaction`, `catalyst`, `product` and `stereochemical_outcome` are emitted as `not_checked_v1` with `checked_by_verifier: false`; they are excluded from the verifier's support-rate denominator and are never treated as withheld.
Allowed per-candidate routing: `accept`, `review`, `reject`.

The verifier may not produce a value that the extractor did not produce. It has no authority to correct chemistry, only to withhold it.

### 5. Scorer

Field-atomic per `benchmark/FIELD_SCHEMA_V1.json`, metrics per `benchmark/SCORING_CONTRACT_V1.md`, implemented in `tools/score_agent_v1.py`, reported as a paired Raw vs Verified table on identical units and joined on `candidate_id`.

## Evaluation unit

One reaction-candidate evidence chunk × one scientific field. A paper may yield zero, one or many chunks. Papers are the unit of source diversity, never the unit of scoring.

## Prohibitions inside the formal run

- no chunk-to-gold matching by list position; association is by `candidate_id` and a recorded target anchor
- no second model call to repair a schema failure
- no verifier-supplied replacement values
- no re-running a chunk after seeing its score
- no change to prompts, schema, thresholds, resolver vocabulary or evidence policy after the freeze; a change creates a new version
