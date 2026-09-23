# Unified blind eligibility exclusion registry

Role: independent benchmark custodian
Date: 2026-09-23
File: `benchmark/blind_eligibility_exclusion_registry.csv`
sha256: `6ef807a35a3f095d8e08b1a0259ad466fa2eb96539d36c9eb57bcc4c9eaafe61`

This registry replaces the two disagreeing standards that let a contaminated cohort pass in September. It is the single authoritative answer to one question: **may this paper identity still be used in a prospective blind?**

## Contents

| | Rows |
|---|---|
| Total rows (unique normalized DOI) | 1971 |
| `EXCLUDE` | 1971 |
| `IDENTITY_ONLY_SAFE` | 0 |
| of which publisher-alias rows | 106 |

## Sources merged

| Source | DOIs contributed |
|---|---|
| `benchmark/known_contamination_manifest.csv` (predictions, Gold, development) | 187 |
| `all_exposed_papers_registry.csv` (every row carries `exclude_from_new_reserve = YES`) | 257 |
| `fe_h2_ah_excluded.csv` (adjudicated corpus screening decisions) | 1662 |
| `stage4h_forward_citation_screening_decisions.csv` (adjudicated screening with abstracts) | 1049 |
| `ni_h2_ah_harmonised_literature_table_stage3h0.csv` | 63 |
| `ni_h2_ah_excluded.csv` | 25 |
| `frozen_stage2b_blind_excluded.csv` | 20 |

Counts overlap; the registry is a union keyed on the normalized DOI.

The exposed-papers registry's own categories are `AGENT_DEVELOPMENT`, `RULE_DEVELOPMENT`, `BENCHMARK`, `PRODUCTION`, `PILOT`, `PRIOR_RESERVE_SCREEN`, `TEST_B`, `TEST_C`, `TEST_P` and `OTHER_EXPOSED`. Every one of its 9423 rows is flagged `exclude_from_new_reserve = YES`, so the whole set is carried over rather than re-adjudicated category by category.

## Exclusion rule

A DOI is `EXCLUDE` when any of these hold: used in development, prompt, rule, resolver, verifier or extractor work; used in testing with scientific content; Gold created; predictions generated; scored; error or failure analysis performed; manually adjudicated; a prior blind or reserve was opened on it; a prior reserve screen exposed its content; its source text or abstract informed an Agent or corpus scientific decision; or it is explicitly flagged `exclude_from_new_reserve = YES`.

Adjudicated corpus screening records (`EXCLUDED` / `INCLUDED` decisions made from title and abstract) count as rule development. This is not an extra standard: the exposed-papers registry already labels the Ni versions of exactly these artifacts `RULE_DEVELOPMENT`. The Fe-side equivalents were missing only because that registry was built from one project directory.

`IDENTITY_ONLY_SAFE` is reserved for identities that appear only in bibliographic discovery, DOI or title lists, metadata-only citation search, identity-only recruitment, download inventories or hash verification. Three raw discovery dumps were scanned for such rows; every DOI in them was already excluded through an adjudicated artifact, so the category is currently empty. It stays in the schema because future discovery sweeps will populate it.

## Publisher DOI aliases

`tools/doi_aliases.py` expands Wiley's Angewandte Chemie German-edition DOIs (`10.1002/ange.*`) to and from the International Edition (`10.1002/anie.*`). The registry stores both forms, so an exact-match gate catches either.

This is not hypothetical. During this run, the replacement candidate pool contained the German-edition DOI of a Blind-v1 paper that the Agent has already been evaluated on, and the International-edition DOI of a paper in a prior development inventory. Both would have passed an exact-match check against the old 187-DOI blacklist. Both are now excluded.

## How to use it

```bash
python tools/check_benchmark_overlap.py \
  --dev benchmark/development_manifest.csv \
  --blind <custodian-private blind identity manifest> \
  --exclude benchmark/blind_eligibility_exclusion_registry.csv
```

Run it as custodian. The blind manifest never enters the repository.
