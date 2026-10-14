# Historical Normalization Challenge v1

Date: 2026-09-23. Former name: `normalization_blind_candidate_v1`.

## Why it is renamed

The package was built as a prospective blind for entity normalization. It cannot serve that role any longer: its 21 source papers are historical project material and every one of them sits inside `benchmark/blind_eligibility_exclusion_registry.csv` lineage as exposed development or corpus material. Calling it a blind would claim generalization evidence it cannot support.

From now on it is the **Historical Normalization Challenge v1**: a module-level regression and diagnostic set for entity resolution.

`eligible_as_blind = NO`. This is permanent, not pending.

The original archive `normalization_blind_candidate_v1_REVIEWER_ONLY.zip` and its freeze manifest are not modified, renamed or repacked. Only the interpretation changes, and it changes here.

## Contents

| Item | Count |
|---|---|
| Single-entity resolution cases | 100 |
| Pairwise identity (merge/split) cases | 157 |
| Source papers | 21 |
| Source documents (article + SI) | 29 |

Entity roles cover ligand, precatalyst and catalyst mentions, each carrying `raw_mention`, an optional `paper_local_label`, and source provenance (document, page, section, table or scheme, excerpt).

## Gold status

The reviewer Gold columns (`gold_status`, `gold_canonical_name`, `gold_canonical_entity_id`, `gold_family`, `gold_stereochemistry`) are **empty for all 100 single-entity cases**, and `review_decision` is empty for all 157 pairwise cases. Verified 2026-09-23 by counting filled cells; no cell contents were read for scientific purposes.

Gold must be created by an independent reviewer. It must never be generated from Agent output, and this repository does not contain a path that could do so. Until a reviewer adjudicates, only the evaluation interface exists.

## Permitted use

- regression testing of `modules/ligand_resolver.py`: does an explicit name resolve, does an undefined alias stay `unresolved`, does a contradictory definition return `ambiguous`
- module-level diagnosis of resolver coverage and abstention behaviour
- schema and format validation of the review packs

## Prohibited use

- any claim of generalization or prospective performance
- any blind or held-out role in Agent v1.0 or later
- tuning the resolver registry on these cases and then reporting scores on the same cases without saying so
- generating Gold from model output

## Evaluation interface

Input: `case_id`, `raw_mention`, `paper_local_label`, `entity_role`, source document and offsets.
System output per case: `canonical_id`, `canonical_name`, `status ∈ {resolved, unresolved, ambiguous}`, `resolution_method`, `evidence`.
Pairwise output per pair: `same_entity ∈ {yes, no, unresolved}` plus evidence.
Scoring, once reviewer Gold exists: resolution accuracy on resolvable cases, abstention correctness on unresolvable cases, and merge/split precision and recall on the pairwise set. Abstention is never scored as an error on a case the source cannot settle.
