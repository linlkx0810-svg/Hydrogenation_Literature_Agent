# Blind Benchmark Integrity

## Purpose

The project uses blind scientific evaluation to estimate extraction performance on unseen literature. Blind integrity is therefore a data-governance requirement, not merely a documentation convention.

This document defines the separation between development data, blind manifests, reviewer-only gold, model predictions and adjudication outputs.

## Data zones

### Development / test zone

May be read by normal extraction, prompt-development and regression commands.

Examples:

- synthetic CI fixtures
- development examples
- non-blind manually curated cases explicitly designated for tuning

### Blind manifest zone

May be visible during development, but must contain identifiers and hashes only. It must not contain scientific answers.

Allowed fields are intentionally narrow:

- `item_id`
- `paper_id`
- `doi`
- `source_id`
- `source_sha256`

See `examples/blind_manifest.example.json`.

### Reviewer-only / blind-gold zone

Must not be read by ordinary extraction or prompt-development commands. Typical path markers include:

- `reviewer_only/`
- `reviewer-only/`
- `blind_gold/`
- `blind-gold/`
- `sealed_predictions/`
- `adjudicated`

The path guard in `modules/blind_integrity.py` blocks these inputs unless explicit evaluation mode is used.

### Prediction zone

Model outputs and production outputs must stay outside reviewer/adjudication paths. A model writer must not write directly into a reviewer-only folder.

### Adjudication zone

Human adjudication outputs must be stored in a clearly separated reviewer/blind path. They must not overwrite model predictions or production records.

## Evaluation-mode rule

Normal benchmark command:

```bash
python tools/run_benchmark.py --dataset examples/benchmark_synthetic.jsonl
```

Reviewer-only or blind-gold evaluation requires an explicit flag:

```bash
python tools/run_benchmark.py \
  --dataset reviewer_only/blind_gold_v1.jsonl \
  --evaluation-mode
```

The same rule is enforced by the unified CLI:

```bash
python agent.py benchmark \
  --dataset reviewer_only/blind_gold_v1.jsonl \
  --evaluation-mode
```

`--evaluation-mode` is for frozen evaluation only. It must not be used while changing extraction rules, prompts, entity registries or verifier logic.

## Blind manifest rule

A development-safe blind manifest is allowed to reveal which source artefacts belong to a blind split without revealing their answers. The strict validator rejects unknown fields rather than silently accepting them.

Do not include fields such as:

- `gold`
- `expected`
- `label`
- `answer`
- adjudication decisions
- model predictions
- extracted scientific values

This enables source identity and file-integrity checks without contaminating model development.

## Guard limitations

The repository guard is a first-line software safeguard. It does not replace:

- filesystem permissions
- independent reviewer accounts or workspaces
- sealed archives
- frozen hashes and timestamps
- procedural separation between developer and reviewer

A path can always be deliberately renamed by a person with sufficient access. Therefore blind integrity still depends on independent review practice.

## Release checklist

Before reporting blind benchmark performance or declaring a dataset release-ready, confirm all of the following:

- [ ] Development and blind partitions were frozen before the evaluated extractor/prompt version was tuned.
- [ ] The development environment used only the blind manifest, not reviewer-only gold.
- [ ] Blind source identifiers/hashes match the frozen manifest.
- [ ] The evaluated extractor, prompt, registry and verifier versions are recorded.
- [ ] Blind evaluation was run only after development was frozen.
- [ ] Reviewer-only gold was opened only in explicit evaluation/adjudication mode.
- [ ] Model predictions are stored separately from adjudication outputs.
- [ ] No blind values were copied into examples, tests, logs, prompts or documentation.
- [ ] Software regression tests pass independently of scientific benchmark results.
- [ ] Benchmark metrics are reported separately from human scientific verification.
- [ ] Ambiguous chemistry remains unresolved until independent adjudication.
- [ ] Any post-blind fixes are treated as a new model/version and are not reported as the original blind result.

## Relationship to scientific validity

Passing CI proves software behavior, not chemical correctness. A high blind benchmark score estimates extraction performance, but final scientific records still require source-level review and, where necessary, independent chemical adjudication.
