# Verifier v1

## Purpose

`verifier-v1` separates **extraction** from **evidence acceptance**. An extractor may return a plausible value; the verifier asks a narrower question: does the exact supplied evidence support that exact value for the same reaction/entity?

The verifier never changes the extracted scientific value. It appends a field-level judgement beside it.

## Field-level contract

Each of the eight reaction fields is verified independently:

- `ee_percent`
- `yield_percent`
- `h2_pressure_bar`
- `temperature_c`
- `reaction_time_h`
- `solvent`
- `ligand`
- `substrate_class`

For every field, the verifier receives only:

1. field name;
2. extracted value;
3. the exact evidence chunk;
4. caller-controlled evidence locator metadata.

It must return exactly:

```json
{
  "status": "accepted",
  "reason_code": "supported"
}
```

No explanation or corrected value is accepted by the schema.

## Status meanings

### accepted

Use only when the evidence explicitly supports the exact extracted value for the same reaction/entity.

Allowed reason:

- `supported`

### rejected

Use when a non-null extracted value is demonstrably wrong with respect to the evidence.

Allowed reasons:

- `wrong_entity`
- `wrong_reaction`
- `format_error`

Examples include taking the ligand from the wrong entry, assigning another row's yield to the target reaction, or representing a supported value in an invalid unit/format.

### unresolved

Use when the evidence cannot establish a reliable decision.

Allowed reasons:

- `missing`
- `ambiguous`
- `conflict`

A main-text/SI conflict is therefore not silently resolved. It remains `unresolved/conflict` until adjudication.

## Why plausible values are not enough

A verifier must not accept a value simply because it is chemically reasonable. For example:

```text
Extracted ligand: BINAP
Evidence: "a chiral phosphine ligand was used"
```

The correct verification outcome is not `accepted`. The exact identity is unsupported by the supplied evidence.

Likewise, if a scope paragraph contains values for several entries and the target association is unclear, the result must remain unresolved.

## Extraction and verification remain separate

The data model intentionally keeps the original extraction untouched. A verification object stores:

```json
{
  "field_name": "ligand",
  "extracted_value": "BINAP",
  "status": "rejected",
  "reason_code": "wrong_entity",
  "verifier_version": "verifier-v1",
  "prompt_version": "verifier-prompt-v1",
  "model_name": "...",
  "evidence_locator": {
    "paper_id": "paper-001",
    "page": 5
  }
}
```

This makes later auditing possible: reviewers can distinguish what the extractor originally said from what the verifier concluded.

## Verification metrics

Verification statistics are reported separately from extraction coverage.

For a candidate, `summarize_verification()` reports:

- extraction coverage: fraction of the eight fields that were non-null before verification;
- accepted-extracted fraction: fraction of returned non-null fields accepted by the verifier;
- counts for `accepted`, `rejected`, and `unresolved`;
- counts for each reason code.

A system should not improve its apparent verification precision simply by abstaining on most fields; coverage must be shown beside acceptance.

## Deterministic replay

The repository includes copyright-safe synthetic fixtures:

```text
examples/verifier_candidate_synthetic.json
examples/verifier_responses_synthetic.json
```

Run:

```bash
python agent.py verify-replay \
  --candidate examples/verifier_candidate_synthetic.json \
  --responses examples/verifier_responses_synthetic.json \
  --model-name example-verifier
```

This command does not call a network model. It validates the verifier contract and provenance plumbing reproducibly.

## Provider separation

`modules/verifier.py` defines a provider-neutral `VerifierProvider` protocol. A future hosted or local model adapter must implement the same strict interface.

This is deliberate: scientific evaluation should not depend on one provider SDK.

## Blind-integrity rule

Normal verifier development must not read reviewer-only/blind-gold material. Replay inputs and outputs pass through the existing blind-integrity path guards.

Do not tune verifier prompts against frozen blind gold. After a blind run, any substantive verifier or prompt change must be versioned and evaluated as a new system.

## What verifier-v1 does not do

`verifier-v1` does not:

- repair an incorrect extracted value;
- choose between conflicting source values;
- resolve cross-paper chemical identities;
- inspect molecular structure images;
- perform independent expert adjudication;
- promote a record to `final-verified` or `ML-ready`.

Those actions remain separate so their contribution and failure modes can be measured independently.
