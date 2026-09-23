# prospective-blind-v2 preflight against the current Agent baseline

Role: independent benchmark custodian
Date: 2026-09-23
Agent candidate: `cb48b2d439b272b8c1740b0d1de197a01e3bc98f` (branch `agent-v1-ligand-verifier`, PR #20)
Old freeze `0d56d8905dcae74c2022bb77aa999fac88a66473` is **not** reused as the current baseline.

## Result

`PBV2_CURRENT_BASELINE_GATE = FAIL_CONTAMINATION`
Reason code: `PBV2_HISTORICAL_RULE_DEVELOPMENT_EXPOSURE`

No evaluation freeze v2 was created. No blind prediction, Gold or scoring was produced.

## Counts

| Item | Value |
|---|---|
| Blind identities | 12 |
| Identity manifest sha256 verified | yes (`21f9e918…14e0`) |
| Eligible locked-list sha256 verified | yes (`97f6b78f…029c7`) |
| Development manifest overlap (DOI / paper_id) | 0 / 0 |
| Known contamination overlap (DOI / paper_id) | 0 / 0 |
| Repository git-tree exposure (all remote branches) | 0 |
| Repository git-history exposure (`git log -S`, all refs) | 0 |
| PR #20 exposure (commits, code, tests, examples, benchmark files) | 0 |
| Historical development exposure | **3** |
| Uncertain provenance | **4** |
| Clean | 5 |

Blind DOIs, titles and per-case identities are deliberately absent from this report and from the repository. They stay in the custodian-held record outside the repository.

## Why the gate fails

The blacklist that PBV2 recruitment was screened against (`historical_doi_exclusions_v4.csv`, now `benchmark/known_contamination_manifest.csv`, 187 DOIs) was derived from artifacts that contain **predictions, Gold or scoring**. It does not cover identity exposure through corpus screening and rule development.

The project maintains a second, broader registry for exactly that purpose: `reports/extraction_logs/agent_mvp_v4.1/external_3d_blind_reserve_discovery/governance/all_exposed_papers_registry.csv` (9423 rows, 258 unique DOIs). Its categories are `OTHER_EXPOSED`, `BENCHMARK`, `AGENT_DEVELOPMENT`, `RULE_DEVELOPMENT`, `PRODUCTION`, `PRIOR_RESERVE_SCREEN`, `PILOT`, `TEST_B`, `TEST_C`, `TEST_P`.

**Three of the twelve PBV2 cases appear in that registry** with `exposure_category = RULE_DEVELOPMENT` *and* `PRIOR_RESERVE_SCREEN`, and with `exclude_from_new_reserve = YES`. The project's own governance therefore already ruled these papers ineligible for a new reserve. Reusing them now would contradict that rule, so they are `CONTAMINATED`.

Four further cases are `UNCERTAIN`. Their identities occur in corpus screening exclusion records, forward-citation screening decision tables (which carry abstracts), a project source catalog, or project manuscript text. Those artifact families are the same kind of material the registry labels `RULE_DEVELOPMENT`, but the registry was not built from them, so their status cannot be settled by an identity check alone. Uncertainty is not converted into PASS.

The remaining five cases show no identity occurrence anywhere outside custodian-held prospective-blind-v2 tooling.

## Secondary finding: custodian hygiene

Two developer-visible helper scripts in the local project (`scripts/prospective_blind_v2_local_pdf_identity_scan.py`, `scripts/prospective_blind_v2_verify_recovered_pdfs.py`) contain blind DOIs inline. This is not development exposure of the papers to the Agent, but blind identities should live only in custodian-held files.

## Checks performed

1. Blacklist validation on `cb48b2d`: 187 rows, 187 unique normalized DOIs, 0 duplicates, 0 blank DOIs, 114 rows carry a paper_id with no duplicates. sha256 `ffb1698a…dae745`.
2. Identity manifest located and hash-verified **before** any comparison. The eligible locked list was hash-verified too.
3. DOI and paper_id overlap of all 12 identities against `benchmark/development_manifest.csv` (12 rows, sha256 `a73a81d5…0ed454`) and against the 187-row blacklist.
4. Identity-only exposure search: every blind DOI across all remote branches' trees, `git log -S` over all refs, and a full text scan of the three local project roots (excluding the custodian PBV2 directory itself).
5. Per-case classification into CLEAN / CONTAMINATED / UNCERTAIN, recorded privately.

## Integrity

- Blind Gold opened: no
- Blind predictions generated: no
- Blind scoring performed: no
- Blind chemistry (reactions, catalysts, ligands, substrates, products, conditions, yield, ee/er, evidence chunks) inspected: no
- Extractor, resolver, verifier, prompts, thresholds and scoring code: unchanged
- `benchmarks/prospective_blind_v2/evidence_chunks_v1.jsonl` and any prediction artifacts: not opened

## Required before any blind can be certified

1. Adopt a single exposure standard. The blind eligibility rule should screen against the union of the prediction/Gold blacklist and the broader exposed-papers registry.
2. Either drop the 3 contaminated cases and adjudicate the 4 uncertain ones, or recruit a fresh blind under the unified standard. Recruitment must be done by the custodian, and the replacement identities must not reach the developer side.
3. Freeze the current execution graph and field schema before any run: `benchmark/AGENT_V1_EXECUTION_GRAPH.md` and `benchmark/FIELD_SCHEMA_CROSSWALK_V1.md` are still missing, and the old freeze pins modules (`modules/llm_extractor.py`, `modules/verifier.py`, model `gpt-5.6-sol`) that differ from what PR #20 adds (`modules/ligand_resolver.py`, `modules/extraction_verifier.py`). The 8 presentation fields and the 8 scored fields of the old freeze are not the same schema and must be reconciled first.
