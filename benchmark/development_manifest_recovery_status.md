# Development manifest recovery status

Date: 2026-09-22
Builder: `tools/build_development_recovery_ledger.py` (identity-only; no Gold, predictions, evidence text or reaction answers read)

## Result

| Item | Value |
|---|---|
| Historical target | 12 |
| Confirmed recovered (`CONFIRMED_MEMBER`) | **12** |
| Probable (`PROBABLE_MEMBER`) | 0 |
| Unresolved | 0 |
| Enough to certify the old blind (sealed external reserve) | **No**: the reserve itself is contaminated (see below) |
| Missing identities | None for the development set |

`FORMAL_LEAKAGE_GATE = FAIL_OVERLAP_DETECTED`

## Authoritative source of the 12 development identities

The 12-paper set is `real_development_set_v1` (NON-BLIND DEVELOPMENT). It is committed on GitHub, not reconstructed by inference:

- Branch `origin/codex/p0-real-development-set-v1` (also contained in `origin/codex/p0-prospective-blind-v2-eval-freeze`)
- `benchmarks/real_development/manifest_v1.csv` at commit `be2952d` (sha256 of file `cf342ca2c1c927132d7181cfa62d4ef5144673fbae7c6b5e14ec22d014aeb05d`). The same content is on both branches.
- Supporting records: `source_review_progress_v1.csv` (12/12 `SOURCE_REVIEWED_TARGET_ANCHORED`), `selection_change_log_v1.md`, and `gold_freeze_attestation_v1.json`. The attestation records private Gold v1 frozen on 2026-09-10 with 12 cases and 96 slots, sha256 `9907994…c25cc5`.
- `docs/real_development_set_v1.md` records the design: six Stage 5C pilot papers plus six scenario anchors, 6 Fe and 6 Ni.

| DEV | paper_id | DOI | metal | cohort |
|---|---|---|---|---|
| DEV-001 | FE-H2-AH-0005 | 10.1002/anie.201301972 | Fe | stage5c_pilot |
| DEV-002 | FE-H2-AH-0016 | 10.1021/jacs.1c04773 | Fe | stage5c_pilot |
| DEV-003 | FE-H2-AH-0022 | 10.1021/jacs.5b00085 | Fe | stage5c_pilot |
| DEV-004 | NI-H2-AH-0031 | 10.1002/anie.201902576 | Ni | stage5c_pilot |
| DEV-005 | NI-H2-AH-0032 | 10.1002/ejoc.202100642 | Ni | stage5c_pilot |
| DEV-006 | NI-H2-AH-0027 | 10.1002/anie.202115983 | Ni | source_complete_replacement |
| DEV-007 | FE-H2-AH-0006 | 10.1021/ic801518h | Fe | scenario_anchor |
| DEV-008 | FE-H2-AH-0011 | 10.1021/ja5003636 | Fe | scenario_anchor (also PILOT01) |
| DEV-009 | FE-H2-AH-0017 | 10.1021/acs.joc.9b01964 | Fe | scenario_anchor (also PILOT07) |
| DEV-010 | NI-H2-AH-0007 | 10.1021/jacs.6b00519 | Ni | scenario_anchor |
| DEV-011 | NI-H2-AH-0025 | 10.1038/s41467-024-49801-0 | Ni | scenario_anchor |
| DEV-012 | NI-H2-AH-0029 | 10.1021/acs.orglett.7b02417 | Ni | source_complete_replacement |

Two slots were replaced on 2026-09-10, before the Gold freeze. The originals are recorded as contaminated. They are not final members.

- DEV-006: original `NI-H2-AH-0033` (10.1021/acs.orglett.2c00608, a Stage 5C pilot).
- DEV-012: original `NI-H2-AH-0026` (10.1016/j.xcrp.2024.102261).

Five of the six Stage 5C pilot papers are final members. `NI-H2-AH-0033` stays in `recovered_historical_pilot_manifest.csv` and `known_contamination_manifest.csv`.

## Pilot01–Pilot08

The pilot-to-paper mapping comes from local pilot workbook and report names such as `PILOT01__FE-H2-AH-0011`. The split comes from `Gold_Benchmark_Split_Manifest_v0.1.csv`.

| Pilot | paper_id | DOI | Gold v0.1 split | In the 12-paper development set? |
|---|---|---|---|---|
| PILOT01 | FE-H2-AH-0011 | 10.1021/ja5003636 | DEVELOPMENT_DEBUG | Yes (DEV-008) |
| PILOT02 | FE-H2-AH-0019 | 10.1038/s41467-025-67933-9 | STRICT_HELD_OUT_TEST | No |
| PILOT03 | FE-H2-AH-0025 | 10.1002/ejoc.201500146 | DEVELOPMENT_DEBUG | No |
| PILOT04 | FE-H2-AH-0013 | 10.1021/acs.organomet.6b00711 | DEVELOPMENT_DEBUG | No |
| PILOT05 | FE-H2-AH-0012 | 10.1021/ja4082233 | STRICT_HELD_OUT_TEST | No |
| PILOT06 | FE-H2-AH-0021 | 10.1002/chem.201204236 | DEVELOPMENT_DEBUG | No |
| PILOT07 | FE-H2-AH-0017 | 10.1021/acs.joc.9b01964 | STRICT_HELD_OUT_TEST | Yes (DEV-009) |
| PILOT08 | FE-H2-AH-0020 | 10.1002/anie.200705115 | (freeze-contract regression fixture) | No |

All eight pilot papers have human Gold and were used in earlier Agent development or evaluation (Frozen Gold Benchmark v1.0, 2026-08-07). They are all `CONTAMINATED`. Pilot01–07 are not the same set as the 12-paper development set; only two of them overlap with it.

## The sealed external reserve is already exposed

Local records show that the four "sealed external reserve" papers are the consumed **Blind-v1** cases `3DXR-001`…`3DXR-004`. The DOI-to-case mapping comes from `reports/extraction_logs/agent_mvp_v4.1/external_3d_blind_reserve_one_shot_eval/sources/reserve_source_snapshot_manifest.csv`.

- On 2026-08-12, Agent v4.1 ran on them once, and Gold labels, raw predictions and field-level scores were frozen (`governance/BLIND_EVAL_GOVERNANCE_CHECK.md`).
- On 2026-08-17, `post_blind_steps_1_6/governance/BLIND_V1_EXPOSED_CASES.json` marked all four `EXPOSED_AFTER_BLIND_V1`, with `exclude_from_blind_v2_construction` and `exclude_from_v4_2_development` set.
- `post_blind_steps_1_6/analysis/LIGAND_FAILURE_ANALYSIS.{md,csv}` is a post-hoc ligand failure analysis on these papers. This run did not open it.
- `reports/normalization_prospective_blind_v2/historical_doi_exclusions_v4.csv` already lists all four as historical exclusions.

Under the contamination rule for papers with existing Gold or error analysis, all four are `CONTAMINATED`. They cannot certify Agent baseline v1.0. The ligand resolver in this PR was written on 2026-09-22, after the post-hoc ligand failure analysis. Whether that analysis influenced it cannot be ruled out without reading blind answers, which this run did not do.

## Leakage checks run

The reports are in `benchmark/leakage_reports/`.

| Check | Result |
|---|---|
| Development (12) vs reserve (4): DOI overlap | 0 |
| Development (12) vs reserve (4): paper_id overlap | 0 (the reserve manifest has no paper_id column, so this check is vacuous) |
| Known contamination (187) vs reserve (4): DOI overlap | **4** |
| Status with `--exclude known_contamination_manifest.csv` | **FAIL** |
| Status of the development-only check | PASS (`KNOWN_RECOVERED_OVERLAP_CHECK = PASS`; this is not a formal blind PASS) |

## Gate conditions

1. 12/12 development identities recovered from an authoritative source: **met**
2. Development DOI vs blind DOI overlap = 0: **met**
3. Development paper_id vs blind paper_id overlap = 0: **met** (vacuous)
4. Known contamination vs blind overlap = 0: **not met** (4/4)
5. Blind papers never used for prompt, rule, code or error-analysis development: **not met** (post-hoc ligand failure analysis exists)

## Ledger scope and limitations

`development_recovery_ledger.csv` has 187 rows. Its union covers the 12 development papers, the 2 replaced originals, Pilot01–08, the 4 Blind-v1 papers, the 3 Test P blind papers, and every DOI in `historical_doi_exclusions_v4.csv` (sha256 `b06b34e9…7bf577`). That list already covers the production corpus v1.1 and the Fe/Ni 64-paper corpus.

- `confidence` is the confidence in the recorded historical role. Every row is backed by a file path.
- For 69 rows, only the DOI is available locally; metal is `UNKNOWN` and title is blank. Their contamination status does not depend on the missing metadata.
- DOI normalization is lowercase exact match. Alternate DOIs for the same paper, such as Angewandte `ange.` vs `anie.`, are listed separately when both occur.
