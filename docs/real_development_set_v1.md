# Real non-blind development set v1

## Purpose

This dataset is an explicitly **NON-BLIND DEVELOPMENT** set for debugging and evaluating the eight-field reaction extraction and verification pipeline on real asymmetric H2 hydrogenation literature.

It is not a held-out test set and must not be presented as an independent blind benchmark.

## Source population

The candidate papers are drawn from the historical 64-paper Fe/Ni source-verified subset. These papers were previously used in data repair, source verification, pilot extraction, or reaction-scenario analysis. They are therefore appropriate for development use and inappropriate for future blind claims.

The initial set contains 12 papers:

- six papers reused from the Stage 5C pilot, which already has source-linked reaction rows and evidence logs;
- six additional papers previously used as source-linked reaction-scenario anchors, chosen to broaden reaction and ligand coverage.

The public repository stores only bibliographic metadata and development labels. Copyrighted article/SI text and verbatim evidence chunks must remain local/private unless redistribution is permitted.

## Selection design

The set is deliberately stratified rather than random:

- 6 Fe + 6 Ni;
- direct-H2 cases plus several relay/cooperative cases;
- carbonyl, imine/hydrazone, alkene, ketoacid/acid, and relay heterocycle contexts;
- multiple ligand/catalyst contexts, including tetradentate/pincer Fe systems, cyclopentadienone/relay systems, Ni bisphosphines, and phosphinooxazoline-type systems;
- previously easy/source-explicit examples mixed with cases likely to stress reaction association, entity association, missing fields, conflicts, and multi-entry extraction.

This composition is designed to diagnose failure modes, not estimate population-level accuracy.

## Blind-integrity gate

Before any real-model execution or score publication:

1. Resolve the paper-ID manifest for every active held-out set, especially `normalization_blind_candidate_v1`.
2. Compare every selected `combined_record_id` and DOI in `benchmarks/real_development/manifest_v1.csv` against those manifests.
3. If any overlap is found, remove the overlapping development paper and replace it with another already-seen/source-verified Fe/Ni paper before model execution.
4. Record the check date, source manifest version/hash, and result.
5. Never open reviewer-only gold, sealed predictions, or adjudicated blind answers merely to perform this overlap check; use metadata-only manifests.

Until this gate is completed, all rows in the development manifest carry `PENDING_MANIFEST_CROSSCHECK`.

## Gold-standard protocol

Gold labels should be created from the actual main article and, where available and relevant, Supporting Information. The common scored fields are:

- `ee_percent`
- `yield_percent`
- `h2_pressure_bar`
- `temperature_c`
- `reaction_time_h`
- `solvent`
- `ligand`
- `substrate_class`

For every scored reaction example:

- identify one target reaction/entry before assigning field values;
- bind each non-null gold field to a source locator;
- preserve missing values as null rather than infer plausible chemistry;
- preserve unresolved/ambiguous values rather than force a single answer;
- distinguish main-text-only evidence from main+SI evidence;
- normalize units only when the source value and conversion are unambiguous;
- do not use existing model predictions as evidence while creating gold.

For Stage 5C reuse cases, historical rows may be used as navigation aids, but each selected eight-field gold example should be re-checked against its cited source location before benchmark freeze.

## Evaluation protocol

Freeze the development gold before running a hosted model. Then evaluate, using the same scoring code:

1. `rule-baseline-v1`
2. real `llm-extractor-v1`
3. retained output after `verifier-v1`

Report precision, recall, F1, answer rate, attempted-gold coverage, hallucinations on absent fields, abstentions on present fields, and per-field metrics. For the verifier also report wrong-value block rate and correct-value retention.

A null prediction against a null gold field is not counted as a correct extracted value.

## Interpretation limits

The 12-paper set is a development diagnostic, not an external validation set. Scores may guide prompt/schema/verifier changes but cannot support claims of generalization. Scientific performance claims require a separately frozen held-out evaluation set with independent adjudication.

## Next execution step

After the blind-overlap gate passes, prepare a local/private JSONL pack containing the chosen reaction-level examples and field-level evidence locators. Freeze that pack, connect the real model provider, and run the three-way comparison without changing prompts between systems.
