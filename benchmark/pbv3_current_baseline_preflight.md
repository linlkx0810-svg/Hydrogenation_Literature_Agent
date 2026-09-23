# prospective-blind-v3 identity gate preflight

Role: independent benchmark custodian
Date: 2026-09-23 (supersedes the 2026-09-23 first pass on this branch)
Agent candidate: `cb48b2d439b272b8c1740b0d1de197a01e3bc98f` (branch `agent-v1-ligand-verifier`, PR #20)

## Result

`PBV3_IDENTITY_GATE = BLOCKED_INSUFFICIENT_CLEAN_CANDIDATES`
Reason code: `PBV3_COHORT_UNDERFILLED`
`EXECUTION_READY = NO`

8 of 12 slots hold a clean candidate, one more than before this round. Every gate that could be run on those 8 returned zero overlap. No identity freeze, no `gate_attestation_v1.json`, no Agent execution.

## Literature cutoff

`LAST_DEVELOPMENT_LITERATURE_SCREENING_CUTOFF = 2026-09-09`, recovered from dated local governance artifacts and attested in `benchmark/pbv3_literature_cutoff_attestation.md`. A dedicated sweep of the post-cutoff window returned no 3d-metal asymmetric hydrogenation primary paper, so Tier 1 is empty and all 8 clean candidates are Tier 2 `RETROSPECTIVE_BUT_UNSEEN`.

## Scope adjudication of the residual pool (round 3)

101 papers reviewed at abstract level: `IN_SCOPE` 0, `OUT_OF_SCOPE` 81, `SCOPE_UNCERTAIN` 20. Dominant reason codes are `OUT_NON_3D_METAL` (64) and `OUT_HETEROGENEOUS_OUTSIDE_SCOPE` (11). No candidate reached the eligibility gates, so the cohort is unchanged. Details are in `benchmark/pbv3_recruitment_funnel_report.md`.

## Cohort

| | Count |
|---|---|
| Clean locked | 8 |
| Backup clean | 0 |
| Remaining deficit | 4 |
| Duplicates | 0 |
| Tier 1 prospective | 0 |
| Tier 2 retrospective but unseen | 8 |

Aggregate metal distribution: Ni 3, Mn 3, Co 2. Fe 0.

## Gates

| Gate | Result |
|---|---|
| A — development manifest overlap (DOI, alias, paper_id, title) | 0 |
| B — unified eligibility registry overlap (DOI, alias, title) | 0 |
| C — repository and developer exposure (branches, tags, full history, `git log -S`, local project roots, title scan) | 0 |
| Duplicate gate | 0 |
| Source readiness | 5 `SOURCE_PACKAGE_READY`, 3 `SOURCE_NOT_READY` |
| Final | `BLOCKED_INSUFFICIENT_CLEAN_CANDIDATES` |

The recruitment funnel and the reason the pool is exhausted are in `benchmark/pbv3_recruitment_funnel_report.md`.

## Integrity

- Blind Gold opened: no
- Predictions generated: no
- Agent executed on any candidate: no
- Resolver or verifier run: no
- Scoring performed: no
- Chemistry fields inspected (reaction, catalyst, ligand, substrate, product, conditions, yield, ee/er): no
- Abstracts read: yes, for scope classification only (round 3); no abstract text stored, no target field recorded
- Developer scientific logic changed: no
- Blind identities in the repository: none. Public references use `PBV3-001` … `PBV3-012`; the case-to-metal mapping is not published, only the aggregate.

## Custodian-private artifacts

Held outside the repository under `reports/normalization_prospective_blind_v2/custodian_private/`:
`pbv3_identity_manifest_v1.csv`, `pbv3_source_manifest_v1.csv`, `pbv3_recruitment_audit_v1.csv`, `pbv3_pending_scope_candidates_v1.csv`, `pbv3_backup_candidates_v1.csv`, `pbv3_cohort_work_v1.csv`, `blind_identity_targets_v1.json`. Their hashes are recorded in `benchmark/pbv3_current_baseline_preflight.json`.

## What unblocks the gate

Four more clean papers, from either of two channels.

1. **Prospective accrual.** Run a monthly Crossref sweep from 2026-09-09 forward under the recruitment policy. This is the only channel that yields genuine Tier 1 cases.
2. ~~Scope pass on the residual pool.~~ Done on 2026-09-23. All 101 were adjudicated at abstract level: 0 in scope, 81 out of scope, 20 still uncertain and therefore excluded. The residual pool is exhausted and cannot contribute to the cohort.

The execution freeze stays out of scope. The old freeze pins `modules/llm_extractor.py`, `modules/verifier.py` and model `gpt-5.6-sol`, while PR #20 adds `modules/ligand_resolver.py` and `modules/extraction_verifier.py`; that graph conflict and the field-schema crosswalk are the next phase, after the cohort is complete.
