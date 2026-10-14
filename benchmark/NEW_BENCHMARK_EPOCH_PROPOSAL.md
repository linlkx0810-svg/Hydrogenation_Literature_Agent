# Proposal: new prospective benchmark epoch

Status: PROPOSAL ONLY. No blind Gold is opened, no blind papers are recruited, and no Agent code is changed by this document.
Date: 2026-09-22

## Why

The 12-paper development set was fully recovered, so recovery is not the reason for a new epoch. The reason is that **no clean blind set is currently available to certify Agent baseline v1.0** (`agent-v1-ligand-verifier`):

- The four "sealed external reserve" papers are the consumed Blind-v1 cases `3DXR-001`…`3DXR-004`. They were evaluated on 2026-08-12, marked `EXPOSED_AFTER_BLIND_V1` on 2026-08-17, and have a post-hoc ligand failure analysis.
- The Test P blind, the Test E/G/K/L/M/N/O blinds, and the Gold v0.1 held-out pilots (PILOT02/05/07) have all been consumed by earlier Agent versions.

## Principles

1. **No inheritance claim.** The new epoch does not claim to continue the old 12-paper split or any old blind. Old results stay historical and are not comparable.
2. **Contamination blacklist.** Every DOI in `benchmark/known_contamination_manifest.csv` (187 at creation) is ineligible for the new blind. This covers the production corpus, the Fe/Ni 64-paper corpus, Pilot01–08, Stage 5C, Gold v0.1/v1.0, the Test E–P blinds, Blind-v1/3DXR, and the real_development_set_v1 originals and replacements.
3. **The old reserve cannot be a holdout.** The four 3DXR papers are removed from any holdout role. Keeping them would violate gate conditions 4 and 5.
4. **Development set.** `benchmark/development_manifest.csv` (12 papers, Gold v1 frozen) remains the development set for this epoch.
5. **New blind.** The blind should have 12–20 new papers that never entered development history. They should be recruited by an independent custodian using metadata only, with DOI and paper_id overlap against the blacklist = 0 before freezing.
6. **Freeze order.** Freeze the Agent baseline v1.0 commit SHA first. Then freeze the blind identity manifest (hash only in public). Create blind Gold after the raw predictions are frozen, and score once.
7. **No post-freeze tuning.** After the blind freezes, Agent v1.0 must not be changed based on blind results. Post-hoc analysis permanently marks those papers `EXPOSED` and adds them to the blacklist.

## Existing candidate to evaluate first

`prospective-blind-v2` already exists as an identity-only, custodian-held recruitment. It has 12 papers, `paper_overlap_gate = PASS` against development, and no Gold or predictions generated (`benchmarks/prospective_blind_v2/gate_attestation_v1.json` on `origin/codex/p0-prospective-blind-v2-eval-freeze`). Before adopting it, the **custodian**, not the developer side, should run:

```bash
python tools/check_benchmark_overlap.py --dev benchmark/development_manifest.csv --blind <custodian_pbv2_identity_manifest.csv> --exclude benchmark/known_contamination_manifest.csv
```

and confirm that no PBV2 paper was opened during development of `agent-v1-ligand-verifier`. This run did not open that manifest.
