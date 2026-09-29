# External Reserve Preflight Status

Date: 2026-09-22 (updated after development-set recovery)

## Current result

`FORMAL_LEAKAGE_GATE = FAIL_OVERLAP_DETECTED`

- The complete 12-paper development set is recovered (12/12 `CONFIRMED_MEMBER`) from `origin/codex/p0-real-development-set-v1@be2952d:benchmarks/real_development/manifest_v1.csv`.
- Development (12) vs reserve (4): DOI overlap **0**, paper_id overlap **0** (the reserve has no paper_id column).
- Known contamination (187) vs reserve (4): DOI overlap **4/4**.
- The reserve is the consumed Blind-v1 set (`3DXR-001`…`3DXR-004`). It was evaluated on 2026-08-12 and marked `EXPOSED_AFTER_BLIND_V1` on 2026-08-17, and a post-hoc ligand failure analysis exists.

Reports:
- `benchmark/leakage_reports/dev_vs_sealed_reserve_with_known_contamination.json` (FAIL)
- `benchmark/leakage_reports/dev_vs_sealed_reserve_dev_only.json` (PASS; development-only, not a formal blind PASS)

## Superseded

The earlier partial status on this date reported 6/12 development identities recovered with PARTIAL_PASS. It is superseded by `development_manifest_recovery_status.md`.

## Governance

Do not open the reserve papers' Gold, predictions, scoring or failure-analysis files. Do not tune the extractor, ligand resolver, verifier, prompts, mappings or thresholds using these papers. A new blind is required (`NEW_BENCHMARK_EPOCH_PROPOSAL.md`).
