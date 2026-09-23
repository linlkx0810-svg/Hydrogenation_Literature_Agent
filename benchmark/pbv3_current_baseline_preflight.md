# prospective-blind-v3 identity gate preflight

Role: independent benchmark custodian
Date: 2026-09-23
Agent candidate: `cb48b2d439b272b8c1740b0d1de197a01e3bc98f` (branch `agent-v1-ligand-verifier`, PR #20)

## Result

`PBV3_IDENTITY_GATE = BLOCKED_INSUFFICIENT_CLEAN_CANDIDATES`
Reason code: `PBV3_COHORT_UNDERFILLED`

7 of 12 slots hold a clean lock candidate. No identity manifest was frozen and no `gate_attestation_v1.json` was created. Every check that could be run on the 7 passed; the gate is blocked on cohort size, not on a detected overlap.

## Unified exclusion registry

`benchmark/blind_eligibility_exclusion_registry.csv`, sha256 `6ef807a3…afe61`: 1971 unique normalized DOIs, all `EXCLUDE`, of which 106 are publisher-alias rows. `IDENTITY_ONLY_SAFE` is empty for now. Construction and rules are in `benchmark/blind_eligibility_registry_report.md`.

## PBV2 reassessment under the unified standard

| Outcome | Cases |
|---|---|
| CLEAN, retained | 5 |
| CONTAMINATED | 6 |
| EXCLUDE_UNCERTAIN | 1 |
| Removed in total | 7 |

The three cases already known to be contaminated were joined by three of the four previously uncertain cases: their identities sit in adjudicated corpus screening records, which the exposed-papers registry treats as `RULE_DEVELOPMENT`. The last uncertain case occurs in project manuscript text and a source catalog; its role cannot be settled without reading chemistry, so it is `EXCLUDE_UNCERTAIN`. No case was carried forward as `UNCERTAIN`.

## Replacement funnel

| Step | Count |
|---|---|
| Bibliographic discovery pool (Crossref snapshot, identity metadata only) | 211 |
| After unified-exclusion, development and PBV2 removal | 175 |
| In-scope journal articles (asymmetric + hydrogenation in title) | 87 |
| Naming a single 3d metal, primary-research shaped | 11 |
| Rejected: DOI alias or registry hit | 2 |
| Rejected: non-experimental (theoretical, mechanistic-origin) | 3 |
| Rejected: abstracting/highlight service, not primary literature | 3 |
| Viable | 3 |
| Clean after the identity exposure scan | **2** |
| EXCLUDE_UNCERTAIN after that scan | 1 |

Two rejections matter beyond arithmetic: one candidate was the German-edition DOI of a paper the Agent has already been evaluated on as Blind-v1, and another the alias of a paper in a prior development inventory. An exact-match check against the old 187-DOI blacklist would have admitted both. Alias expansion now blocks them.

## Gates on the 7 clean lock candidates

| Gate | Requirement | Result |
|---|---|---|
| A — development | DOI and paper_id overlap with `benchmark/development_manifest.csv` = 0 | 0 / 0 |
| B — unified exclusion registry | `EXCLUDE` DOI and paper_id overlap = 0 | 0 / 0 |
| C — current baseline and PR #20 | scientific-development exposure = 0 | 0 |
| duplicates within the cohort | 0 | 0 |

Gate C covered every remote branch tree, `git log -S` over all refs, and a full text scan of the three local project roots. The only identity occurrences for retained cases are in custodian-held prospective-blind tooling, which is recorded, not counted as exposure.

Metal distribution of the 7: Ni 3, Mn 3, Co 1. Fe is currently unrepresented. Metal balance was not traded against the exclusion standard.

Source availability: the 2 new candidates carry `OA_LICENSE_METADATA_ONLY_NOT_ACQUIRED`. Files must be acquired and hashed before any run.

## Blind governance fix

Two developer-visible helper scripts had blind DOIs and titles hard-coded. Both now load identities from a custodian-private JSON via `--targets` or `BLIND_IDENTITY_TARGETS`, and they exit with an error when no file is supplied. The custodian-private identity target file lives outside the repository. A test guards the repository against any prospective-blind DOI reappearing in tracked files.

## Integrity

- Blind Gold opened: no
- Blind predictions generated: no
- Blind scoring performed: no
- Resolver, verifier or any Agent component run on blind papers: no
- Blind chemistry (reactions, catalysts, ligands, substrates, products, conditions, yield, ee/er, evidence chunks) inspected: no
- Extractor, resolver, verifier, prompts, thresholds, normalization and scoring code: unchanged
- Blind identities in the repository: none. Public references use `PBV3-001` … `PBV3-012`.

## What unblocks the gate

5 more clean papers. The exhausted pool is a stale Crossref snapshot taken during the v2 recruitment, not the literature. A fresh custodian discovery sweep, run against the 1971-DOI registry and restricted to work published after the last corpus screening sweep, is the way to fill the remaining slots. Recruitment must stay with the custodian.

The execution freeze stays out of scope until the cohort is complete. The old freeze pins `modules/llm_extractor.py`, `modules/verifier.py` and model `gpt-5.6-sol`, while PR #20 adds `modules/ligand_resolver.py` and `modules/extraction_verifier.py`. These are not the same evaluation graph, and no run may be planned until that is resolved and frozen.
