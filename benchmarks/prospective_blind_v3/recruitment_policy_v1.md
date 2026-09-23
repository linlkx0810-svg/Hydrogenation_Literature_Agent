# prospective-blind-v3 recruitment policy v1

Role: independent benchmark custodian. Date: 2026-09-23.
Status: policy frozen. Cohort **not** frozen — recruitment is incomplete (see `benchmark/pbv3_current_baseline_preflight.md`).

## Why v3 rather than repairing v2

prospective-blind-v2 failed its gate against the current Agent candidate, and 7 of its 12 cases had to be removed. A cohort that keeps the v2 name while replacing more than half of it would make provenance unreadable. The split is renamed `prospective-blind-v3`. The v2 attestation stays as a historical record and must not be cited as a clean blind.

## Eligibility

A paper may be locked only if all of these hold.

1. Its DOI, and every publisher alias of that DOI (`tools/doi_aliases.py`), is absent from `benchmark/blind_eligibility_exclusion_registry.csv`.
2. Its paper_id, where one exists, is absent from that registry.
3. It is not in `benchmark/development_manifest.csv`.
4. It is not a Pilot01–08 paper, a Stage 5C paper, an old Gold benchmark block, a Test E–P case, or a Blind-v1 / 3DXR case. All of these are inside the registry.
5. It was never used in production error analysis or in any PR #20 example, test or report.
6. No Gold, prediction, score or post-hoc failure analysis exists for it.
7. No part of its source text or abstract informed any Agent or corpus scientific decision.
8. An identity-only exposure scan over all repository branches, `git log -S` over all refs, and the local project roots returns no hit outside custodian-held blind tooling.

## Selection

Stratification may use only bibliographic and availability metadata: metal, year, journal, broad substrate class as stated in the title or publisher metadata, source availability, and main/SI availability.

Selection must never use expected difficulty, ligand complexity, field complexity, anticipated extraction error, or any known target value. Recruitment is performance-blind by construction: the custodian does not open the paper's reaction content at any point before the run.

Target size is 12. Metal coverage across Mn, Fe, Co and Ni is preferred but never traded against the exclusion standard. The achieved distribution is reported; it is not forced.

## Source availability

A locked case needs lawful access to the primary article and, where it exists, the SI. Open-access license metadata alone is provisional evidence. A candidate stays `OA_LICENSE_METADATA_ONLY_NOT_ACQUIRED` until the custodian has the file and its sha256. Acquisition is identity-level work: the custodian records hashes and page counts, not chemistry.

## Custody

The identity manifest lives only in the custodian-private location. The repository may carry counts, metal distribution, hashes, gate status and this policy. Blind DOIs and titles must never appear in a markdown report, test, commit message, PR, log, CI output or public JSON. Public references use `PBV3-001` … `PBV3-012`.

Helper scripts that touch blind sources read identities from a custodian-private JSON passed with `--targets` or `BLIND_IDENTITY_TARGETS`. Hard-coding a blind DOI in a developer-visible script is a governance defect, and a test guards against it.

## Order of operations

1. Complete recruitment to 12 under this policy.
2. Freeze the identity manifest and publish `gate_attestation_v1.json` with counts and hashes only.
3. Resolve the Agent execution graph and the field schema crosswalk, then freeze the execution environment.
4. Only then run the Agent once, freeze raw predictions, create Gold, and score once.

A cohort is single-use. Once any case's output is opened, that case is permanently exposed and joins the exclusion registry.
