# Validation Protocol

## Purpose

The pipeline is intended to accelerate literature mapping while keeping scientific claims traceable to source documents. Automated screening and extraction are therefore treated as candidate-generation steps, not as substitutes for expert verification.

## Validation layers

### 1. Synthetic regression tests

`tests/` contains deterministic examples that check the behaviour of core extraction rules (ee, yield, pressure, temperature, time, TON/TOF, solvent, ligand and substrate-class detection). These tests contain no copyrighted article text and run automatically in GitHub Actions.

Agent v1.0 additionally tests two independent trust-layer components:

- `modules/ligand_resolver.py` — resolves explicit ligand names and source-defined aliases such as L1/L2; undefined aliases remain unresolved and conflicting definitions remain ambiguous.
- `modules/extraction_verifier.py` — checks that extracted values are supported by the candidate's bound evidence window and routes results to accept/review/reject.

### 2. Manually curated blind benchmark

A separate benchmark must be frozen before rule or prompt tuning. Each benchmark item should contain:

- stable paper identifier (preferably DOI)
- manually verified reaction-level fields
- provenance for each gold value (page/table/scheme or compact evidence note)
- adjudication status for ambiguous or source-unresolvable cases

The first formal baseline uses reaction × field evaluation for eight fields:

1. reaction
2. catalyst
3. ligand
4. substrate
5. product
6. conditions
7. yield
8. selectivity

The development and blind partitions must be separated at the paper/DOI level, not by random reaction rows from the same paper. Run `tools/check_benchmark_overlap.py` and proceed only when both DOI overlap and paper_id overlap are zero.

The current planning record refers to a 12-paper development set. Its exact paper identities must be recovered and frozen before the formal blind benchmark is executed; they must not be reconstructed by guessing.

Do not tune extraction rules, prompts, entity mappings, or verification thresholds on the blind-test partition after Gold answers are opened.

### 3. Raw extractor vs verifier

Raw extraction and verification must be evaluated on the same cases.

`tools/run_trust_benchmark.py` supports the synthetic regression layer. The formal scientific benchmark is scored after human adjudication with `tools/score_blind_benchmark.py`.

Report at least:

- end-to-end correct rate = correct / all evaluable fields
- selective accuracy = correct / answered fields
- coverage = answered fields / all evaluable fields
- evidence support rate
- unsupported answer rate
- reasonable-abstention precision
- reasonable-abstention recall
- per-field results and error-type counts

A verifier that improves selective accuracy by abstaining more often must not be described as globally better without also reporting coverage and end-to-end correctness.

### 4. Chemical identity adjudication

Chemical entities require canonical-identity matching rather than literal string matching.

For ligands, a label such as `L9*`, a full ligand name, and a structure-derived identifier may be judged equivalent only when they map to the same canonical ligand identity. The automated resolver may map a paper-local alias only when the source explicitly defines that alias. If the source does not establish the identity, the correct automated state is unresolved rather than guessed.

### 5. Error taxonomy

Record at least the following failure classes:

- PDF/text extraction failure
- search/retrieval miss
- false inclusion or exclusion
- value associated with the wrong reaction/table entry
- unit parsing or conversion error
- ligand/catalyst entity-resolution error
- substrate/product association error
- evidence-location or evidence-binding error
- unsupported inference
- avoidable abstention
- ambiguity requiring human adjudication

## Scientific-use rule

Outputs from the current extraction system remain candidate data until checked against source material. Verifier `accept` means that the candidate is supported by the evidence representation available to the software; it is not a substitute for scientific human review of the original source when publishing or creating Gold labels.

## Benchmark publication policy

Only publish benchmark examples when redistribution is permitted. For copyrighted papers, store identifiers, Gold labels/values and compact provenance metadata rather than article PDFs or substantial source text.
