# Real non-blind development gold curation v1

## Purpose

This protocol converts previously seen, source-verified Fe/Ni asymmetric-H2 literature into a real NON-BLIND development benchmark for extraction + verification. It is development data, not held-out blind evidence and not a scientific performance claim by itself.

## Unit of evaluation

The benchmark unit is one **anchored reaction entry**, not one paper-level summary. Each `DEV-*` paper must first be assigned a stable `target_reaction_id` tied to a specific table/scheme/general-procedure/scope entry before its eight fields can be frozen as final gold.

The eight scored fields are:

1. `ee_percent`
2. `yield_percent`
3. `h2_pressure_bar`
4. `temperature_c`
5. `reaction_time_h`
6. `solvent`
7. `ligand`
8. `substrate_class`

## Non-negotiable association rule

Values from different reaction entries in the same paper must never be combined into one gold record merely because all values are individually source-supported. A paper may contain optimization, substrate scope, scale-up, mechanistic probes, deuterium experiments, controls, and low-loading demonstrations with different conditions. Only evidence demonstrably attached to the selected target reaction may populate its gold fields.

If the source does not establish the association, use `null` with an explicit unresolved status.

## Curation stages

### Stage A — historical seed reuse

Reuse source-verified Stage 5C/Stage 5D values only as **seeds**. This reduces duplicate manual work but does not automatically make the values final gold.

Allowed seed provenance includes:
- Stage 5C reaction rows and evidence logs;
- Stage 5D 64-paper representative rows and repair audit;
- previously source-linked reaction-scenario anchors.

### Stage B — target reaction anchoring

For every `DEV-*` paper, record:
- source DOI;
- target reaction identifier;
- target substrate/product identifier when available;
- source table/scheme/general-procedure locator;
- whether yield and ee are demonstrably from the same entry;
- whether conditions are demonstrably attached to that entry.

No final field scoring is allowed until the target anchor is at least `ANCHORED_SOURCE_LOCATOR`.

### Stage C — field-level source review

Each field receives one status:
- `SOURCE_VERIFIED_SAME_ENTRY`
- `SOURCE_VERIFIED_PAPER_LEVEL_ONLY`
- `DERIVED_UNIT_NORMALIZATION`
- `DERIVED_FROM_ER_SAME_ENTRY`
- `REPORTED_NONNUMERIC`
- `NOT_REPORTED`
- `UNRESOLVED_ASSOCIATION`
- `CONFLICT_NEEDS_REVIEW`

Only `SOURCE_VERIFIED_SAME_ENTRY` and explicitly documented deterministic derivations are final scoreable gold values.

## Deterministic normalization policy

### Pressure

Pressure conversion is allowed only when the original value and unit are source-linked to the target entry. Preserve the original pressure string in private curation metadata. Examples:
- atm -> bar using 1 atm = 1.01325 bar;
- psi -> bar using 1 psi = 0.0689475729 bar.

A bare number such as `50` without a verified pressure unit is not converted.

### Temperature

Do not silently map `room temperature` to 20, 23, or 25 °C. Keep `temperature_c = null` and record the original string as `REPORTED_NONNUMERIC` unless the paper itself defines the numerical temperature.

### Enantioselectivity

If a target entry reports only er, conversion to ee is permitted only after the exact same-entry association is verified. For a two-enantiomer ratio `a:b`, derived ee is `abs(a-b)/(a+b) * 100`. Preserve the original er and mark `DERIVED_FROM_ER_SAME_ENTRY`; do not overwrite the source representation.

### Yield

Do not silently equate conversion with yield. Thresholds such as `>99%` must preserve the comparator. If the benchmark scorer requires a scalar, the case remains unresolved until a threshold-scoring policy is explicitly frozen.

## Source hierarchy

Preferred evidence order:
1. target table/scheme/scope entry in SI or article;
2. general procedure explicitly governing that target entry;
3. article text explicitly describing the same target entry;
4. historical source-linked Stage 5C/Stage 5D extraction as a seed only.

Metadata, abstracts, review articles, and legacy summaries cannot establish final reaction-specific gold values by themselves.

## Leakage / blind integrity

Before any real-model benchmark run, every development DOI and corpus ID must pass the metadata-only overlap gate against all active held-out/reviewer-only manifests. The development manifest remains `PENDING_MANIFEST_CROSSCHECK` until that step is completed.

Historical blind/gold benchmark DOI blocks must also be treated according to their original leakage policy; use in this development set must be explicitly documented as non-blind and must not retroactively alter historical benchmark claims.

## Current status

The first seed pass covers 12 papers (6 Fe, 6 Ni). Historical source-verified data populate 62 of 96 field slots as candidate seeds; 34 field slots remain source-review targets. These counts describe curation progress only, not extraction-model performance.
