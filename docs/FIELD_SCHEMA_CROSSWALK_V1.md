# Field schema crosswalk v1

Date: 2026-09-23. Authoritative schema: `benchmark/FIELD_SCHEMA_V1.json` (12 atomic fields).

Three field lists were in circulation. This document replaces all of them with one, and states exactly how the old lists map onto it. Nothing is silently renamed.

## Decisions

1. **`conditions` is not a field.** It is scored as four atomic fields: `h2_pressure`, `temperature`, `reaction_time`, `solvent`. A compound conditions bit hides partial correctness and makes error diagnosis impossible.
2. **Selectivity uses option B.** `ee_or_er` carries the numeric enantioselectivity as reported; `stereochemical_outcome` carries the configuration. A single compound `selectivity` field is not scored.
3. **The count is 12, not 8.** The historical "8 fields" figure came from a presentation and from the old freeze; neither is a reason to merge atomic quantities back together.
4. **`substrate_class` becomes `substrate`.** Class-level answers stay legal, and are scored against class-level gold; the field name no longer forces a class answer when the source names a compound.
5. **`catalyst`, `reaction`, `product` and `stereochemical_outcome` are new to the scored set.** They exist in the PR #20 documentation but were never in the old scored schema, so they have no historical metrics to compare against.

## Crosswalk

| FIELD_SCHEMA_V1 | Old freeze (8 scientific fields) | PR #20 docs (8 high-level fields) | Raw extracted source | Normalization | Scoring unit | Evidence requirement | Abstention handling |
|---|---|---|---|---|---|---|---|
| `reaction` | — | `reaction` | LLM JSON | controlled vocabulary | one chunk × field | reaction type stated in the window | null vs null gold = correct abstention |
| `catalyst` | — | `catalyst` | LLM JSON | string normalization | one chunk × field | named in the window | as above |
| `ligand` | `ligand` | `ligand` | LLM JSON | `ligand_resolver` canonical id | one chunk × field | mention + explicit alias definition in source | `unresolved` / `ambiguous` excluded from coverage, never incorrect |
| `substrate` | `substrate_class` | `substrate` | LLM JSON | string normalization; class answers scored against class gold | one chunk × field | named in the window | as above |
| `product` | — | `product` | LLM JSON | string normalization | one chunk × field | named in the window | as above |
| `h2_pressure` | `h2_pressure_bar` | part of `conditions` | LLM JSON | unit conversion to bar when the unit is explicit | one chunk × field | value and unit in the window | null vs null gold = correct abstention |
| `temperature` | `temperature_c` | part of `conditions` | LLM JSON | numeric, °C | one chunk × field | value in the window | non-numeric report is `not_reported_numerically`, not coerced |
| `reaction_time` | `reaction_time_h` | part of `conditions` | LLM JSON | numeric, hours | one chunk × field | value in the window | as above |
| `solvent` | `solvent` | part of `conditions` | LLM JSON | controlled vocabulary | one chunk × field | named in the window | as above |
| `yield` | `yield_percent` | `yield` | LLM JSON | numeric percent | one chunk × field | value in the window | conversion ≠ yield → `not_applicable` |
| `ee_or_er` | `ee_percent` | part of `selectivity` | LLM JSON | reported kind preserved; er→ee only when explicit | one chunk × field | value in the window | null vs null gold = correct abstention |
| `stereochemical_outcome` | — | part of `selectivity` | LLM JSON | controlled tokens, verbatim descriptors | one chunk × field | stated in the window | never inferred from the ee value |

## Comparability with historical numbers

Old prospective-blind-v2 metrics, Test B–P results and any "8 field" figure are **not comparable** to metrics computed under this schema. The unit changed (chunk × atomic field), the field set changed, and the abstention semantics changed. Historical numbers may be cited as history, never as a baseline for a v1.0 claim.

## Value states

`answered`, `not_reported`, `not_applicable`, `unresolved`, `ambiguous` are five distinct states, defined in `FIELD_SCHEMA_V1.json`. The two rules that matter most:

- `unresolved ≠ incorrect`, and `unresolved` does not count toward answer coverage.
- `not_applicable` leaves every denominator.
