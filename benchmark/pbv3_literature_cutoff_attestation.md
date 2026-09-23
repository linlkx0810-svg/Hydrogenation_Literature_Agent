# Literature screening cutoff for prospective-blind-v3

Role: independent benchmark custodian. Date: 2026-09-23.

## Attested value

`LAST_DEVELOPMENT_LITERATURE_SCREENING_CUTOFF = 2026-09-09`

A paper counts as prospective (Tier 1) only if it was published after this date. Everything earlier is at best Tier 2, `RETROSPECTIVE_BUT_UNSEEN`, and needs the full exposure scan before it can be locked.

## How the date was recovered

The value is the latest developer-side activity that enumerated or adjudicated literature identities. It was not estimated; each source is a dated local artifact.

| Date | Activity | Authoritative source |
|---|---|---|
| 2026-06-28 | Fe forward-citation screening decisions (1057 adjudicated records with abstracts) | `Fe_H2_Asymmetric_Hydrogenation/reports/stage4h_forward_citation_screening_decisions.csv` |
| 2026-06-30 | Ni harmonised literature table, stage 3h working corpus | `Ni benchmark/.../data/ni_h2_ah_harmonised_literature_table_stage3h0.csv` |
| 2026-08-09 | Co/Mn census literature search sweep (18 logged routes, all dated) | `reports/literature_discovery/Co_Mn_H2_Asymmetric_Hydrogenation_Census/01_search/Co_Mn_Search_Log.csv` |
| 2026-08-10 | Mn discovery recall audit | `reports/literature_discovery/Co_Mn_.../13_mn_recall_audit/` |
| 2026-08-12 | Pre-v4.2 reserve candidate screening; exposed-papers registry compiled | `reports/extraction_logs/agent_mvp_v4.1/pre_v4.2_3d_diagnostic_and_reserve/new_3d_reserve_screened_candidates.csv`, `.../external_3d_blind_reserve_discovery/governance/all_exposed_papers_registry.csv` |
| 2026-08-17 | Stage 7a Paper 2 literature landscape calibration; Blind-v1 post-hoc analysis | `reports/stage7a_paper2_literature_landscape_calibration/`, `.../external_3d_blind_reserve_one_shot_eval/post_blind_steps_1_6/` |
| 2026-09-08 | EXCL-1677 inclusion change (a previously excluded paper re-adjudicated into the corpus); literature reconciliation audit | `reports/EXCL-1677_inclusion_change.md`, `reports/literature_reconciliation_audit.json` |
| **2026-09-09** | **MN-H2-AH-0022 re-extraction; corpus normalization v2 curation closeout** | `reports/MN-H2-AH-0022_reextraction.md`, `reports/corpus-normalization-20260908-v2/` |

## Rationale

Where sources disagree, the rule is to take the latest date that could have influenced Agent development. The June Fe/Ni sweeps and the August Co/Mn census are the large enumerations, but literature identities were still being adjudicated on 2026-09-08 and 2026-09-09, so those later dates govern.

Two dates were considered and rejected as the cutoff:

- 2026-09-10/11, the prospective-blind-v2 recruitment. This was custodian-side, identity-only work. It does not expose papers to development and must not shrink the prospective window.
- 2026-09-22, the developer baseline commit `cb48b2d`. PR #20 added the ligand resolver and verifier but screened no literature. Rather than push the cutoff there, every candidate is additionally run through a Gate C exposure scan over the repository and the local project roots as they stand today, which covers anything read up to the present.

## Consequence for this recruitment round

The prospective window is 2026-09-09 to 2026-09-23, two weeks. A dedicated Crossref sweep over that window (`from-pub-date:2026-09-09`, sorted by publication date, 200 records across two queries) returned **zero** 3d-metal asymmetric hydrogenation primary papers. Tier 1 is therefore empty, and every candidate considered in this round is Tier 2.
