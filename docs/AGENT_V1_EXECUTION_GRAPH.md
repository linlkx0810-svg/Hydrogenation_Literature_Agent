# Agent v1.0 formal execution graph

Date: 2026-09-23. Status: specified, not yet satisfied by the code on this branch (see `docs/AGENT_V1_PIPELINE_AUDIT.md`).

## The single formal graph

```text
frozen source artifact (article/SI PDF, hash-verified)
  → deterministic text extraction (pypdf, page order, no OCR)
  → evidence candidate builder            [reaction_candidate_extraction.extract_reaction_candidates]
  → RAW LLM EXTRACTOR                     [llm_extractor.llm-extractor-v1, one chunk per call, strict JSON]
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
| `modules/llm_extractor.py` | Raw LLM extractor | `ACTIVE_IN_FORMAL_RUN` — **not present on this branch**, port required |
| `modules/openai_responses_provider.py` | provider transport | `ACTIVE_IN_FORMAL_RUN` — **not present on this branch**, port required |
| `modules/ligand_resolver.py` | entity normalization | `ACTIVE_IN_FORMAL_RUN` |
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
Prompt: `llm-extractor-prompt-v1`, frozen.
Output: strict JSON against the frozen response schema, every field nullable, no extra keys, no free text. A schema violation raises; it is never repaired into a prediction.

The raw prediction file is written and hashed before normalization or verification runs. Nothing downstream may edit it. Raw metrics are computed from that file alone.

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

Allowed per-field outcomes: `supported`, `partial`, `unsupported`, `unresolved`, `ambiguous`.
Allowed per-candidate routing: `accept`, `review`, `reject`.

The verifier may not produce a value that the extractor did not produce. It has no authority to correct chemistry, only to withhold it.

### 5. Scorer

Field-atomic per `benchmark/FIELD_SCHEMA_V1.json`, metrics per `benchmark/SCORING_CONTRACT_V1.md`, reported as a paired Raw vs Verified table on identical units.

## Evaluation unit

One reaction-candidate evidence chunk × one scientific field. A paper may yield zero, one or many chunks. Papers are the unit of source diversity, never the unit of scoring.

## Prohibitions inside the formal run

- no chunk-to-gold matching by list position; association is by `candidate_id` and a recorded target anchor
- no second model call to repair a schema failure
- no verifier-supplied replacement values
- no re-running a chunk after seeing its score
- no change to prompts, schema, thresholds, resolver vocabulary or evidence policy after the freeze; a change creates a new version
