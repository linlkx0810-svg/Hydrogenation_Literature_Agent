# Prospective blind v2 evidence-chunk policy v1

This policy is frozen before the first live blind prediction. It defines how text evidence is converted into model-visible candidate chunks without consulting blind gold or reviewer decisions.

## Evaluation unit

The scientific evaluation unit is a **reaction-candidate evidence chunk**, not an entire paper.

The 12-paper prospective blind cohort defines source diversity. A paper may produce zero, one, or multiple candidate chunks.

## Source-text boundary

1. Use only source artifacts belonging to the frozen prospective-blind-v2 source manifest.
2. Verify every source artifact hash before text processing.
3. Extract PDF text page-by-page with the frozen `pypdf` environment; concatenate pages in source order.
4. Do not use OCR, image interpretation, external web retrieval, or manual transcription in this text-only v2 benchmark.
5. Article and SI files, when both are present in the frozen source manifest, are processed as distinct source artifacts.

The exact `pypdf` package version must be recorded in the final run manifest before inference.

## Candidate-window construction

Use the existing deterministic function:

`modules.reaction_candidate_extraction.extract_reaction_candidates`

Frozen code blob:

`c8e36d7383df0ddb7acd128eeefc59a85b461bb8`

Parameters:

- extraction method: `rule-baseline-v1`
- `context_sentences = 2`
- anchor: sentence containing the existing ee or yield regular-expression match
- duplicate windows: removed by the existing deterministic `(start, end)` rule

No ranking, top-k filtering, model-based selection, manual target selection, or post-hoc rescue is permitted.

## Model-visible information

For each candidate, the LLM receives only the frozen `evidence_text` plus the already-frozen extractor prompt/schema.

Do **not** expose the deterministic baseline's parsed scientific values, confidence score, reviewer decisions, blind gold, registry results, or historical normalization answers to the live model.

## Chunk manifest

Before the first live model call, create an evidence manifest containing only non-gold provenance fields such as:

- source identifier
- source SHA256
- candidate ID
- evidence start/end offsets
- evidence-text SHA256
- evidence-builder version

The manifest may contain the local chunk file path but must not contain expected answers.

Hash and freeze the complete evidence manifest before inference.

## Zero-candidate sources

A frozen source artifact that generates zero candidate windows must remain zero-candidate for the reported run. Do not manually create a replacement chunk after seeing this result.

Report `zero_candidate_source_count` separately. This is retrieval/chunk-generation coverage and must not be hidden inside conditional extraction accuracy.

## Blind adjudication

After raw and verifier predictions are sealed, the independent reviewer/custodian may adjudicate the generated chunks without seeing model predictions. Gold construction must use the exact frozen chunk IDs/hashes so scoring cannot silently switch evidence windows.

## Versioning rule

Any change to page-text extraction, sentence splitting, anchor patterns, context size, deduplication, source-artifact set, or candidate selection policy creates a new evidence-builder/evaluation version and cannot be reported as the original prospective-blind-v2 run.
