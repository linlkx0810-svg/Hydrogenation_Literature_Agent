# Validation Protocol

## Purpose

The pipeline is intended to accelerate literature mapping while keeping scientific claims traceable to source documents. Automated screening and extraction are therefore treated as candidate-generation steps, not as substitutes for expert verification.

## Validation layers

### 1. Synthetic regression tests

`tests/` contains deterministic examples that check the behaviour of core extraction rules (ee, yield, pressure, temperature, time, TON/TOF, solvent, ligand and substrate-class detection). These tests contain no copyrighted article text and run automatically in GitHub Actions.

### 2. Manually curated blind benchmark

A separate benchmark should be frozen before rule or prompt tuning. Each benchmark item should contain:

- stable paper identifier (preferably DOI)
- inclusion/exclusion gold label
- manually verified reaction-level fields
- provenance for each gold value (page/table/scheme or evidence note)
- adjudication status for ambiguous cases

Do not tune extraction rules on the blind-test partition.

### 3. Recommended metrics

For screening, report precision, recall and F1 for the inclusion decision. For structured extraction, report exact-match accuracy per field and coverage (fraction of gold fields for which the system returned a value). Chemical entities may additionally require a normalised-match metric.

### 4. Error taxonomy

Record at least the following failure classes:

- PDF/text extraction failure
- search/retrieval miss
- false inclusion or exclusion
- value associated with the wrong reaction/table entry
- unit parsing or conversion error
- ligand/catalyst entity-resolution error
- substrate/product association error
- ambiguity requiring human adjudication

## Scientific-use rule

Outputs from the current rule-based Stage 5 extractor must be manually checked against source PDFs before they are used as scientific evidence, training labels, or quantitative review data.

## Benchmark publication policy

Only publish benchmark examples when redistribution is permitted. For copyrighted papers, store identifiers, gold labels/values and compact provenance metadata rather than article PDFs or substantial source text.
