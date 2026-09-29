# Reaction taxonomy v1

Date: 2026-09-24. Artifact: `benchmark/REACTION_TAXONOMY_V1.json`. Bound field: `reaction` in `benchmark/FIELD_SCHEMA_V1.json`.

## Where it comes from

Nothing here is new vocabulary. The taxonomy is the cross product of two **frozen Stage 5b controlled vocabularies** already used by the Fe/Ni corpus:

- `vocab_reaction_type.csv`: `asymmetric_hydrogenation`, `transfer_or_relay_hydrogenation`, `reductive_hydroamination`, `other_source_reported`
- `vocab_substrate_class.csv`: `ketone`, `imine`, `alkene`, `heteroarene`, `alkyne_tandem`, `other` (plus `mixed_or_multiple`, excluded below)

Label form: `<reaction_type>.<substrate_class>`, giving 24 closed labels. Both source files are pinned by sha256 in the JSON.

## Rules

- a label names the transformation class only;
- a label never contains a catalyst, a ligand, a yield, an ee or a substrate name;
- the same transformation always takes the same label, across papers;
- `mixed_or_multiple` is not a legal Gold label, because a Gold target is exactly one reaction;
- a label is assigned from the frozen corpus classification of the paper (`scope_tier`, `substrate_type` in `fe_ni_h2_ah_combined_64_scope_summary.csv`) together with the substrate of the frozen target anchor.

`EXTENDED_H2_RELAY` in the corpus maps to `transfer_or_relay_hydrogenation`; `CORE_DIRECT_H2` maps to `asymmetric_hydrogenation`. That mapping is the corpus's own distinction between direct molecular-H2 hydrogenation and an H2-driven relay or shuttle process, not a new judgement.

## Schema amendment

`FIELD_SCHEMA_V1.json` now cites this taxonomy in the `reaction` field's `canonicalization` and `vocabulary`, and records the change in `schema_amendments`. The field set is unchanged, so the schema version stays `agent-v1-field-schema-v1`. This closes `SCHEMA_DEFINITION_GAP(reaction)`.

## Provenance of the 12 assigned labels

All 12 development cases now carry a `reaction` label with provenance `LEGACY_CORPUS_TAXONOMY` and review status `PROVISIONAL_SOURCE_ADJUDICATION`. That status is deliberate: the mapping was made by Claude from the corpus record, and it is **not** human-confirmed. A human reviewer upgrading it should change the review status, not the label format.

## Not connected to any blind set

The taxonomy is derived only from the exposed Fe/Ni development corpus. No prospective-blind-v3 identity, source or manifest was consulted.
