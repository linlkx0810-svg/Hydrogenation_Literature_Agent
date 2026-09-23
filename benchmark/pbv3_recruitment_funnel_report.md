# prospective-blind-v3 recruitment funnel

Role: independent benchmark custodian
Date: 2026-09-23
Cutoff: `2026-09-09` (see `benchmark/pbv3_literature_cutoff_attestation.md`)

## Outcome

`PBV3_IDENTITY_GATE = BLOCKED_INSUFFICIENT_CLEAN_CANDIDATES`
8 of 12 slots hold a clean candidate. The round added 1 new clean paper to the 7 carried in. No cohort was frozen and no attestation was written.

## Funnel

| Stage | Count |
|---|---|
| Crossref queries issued (4 metals × base and substrate terms, plus base-metal and scope sweeps) | 82 |
| Raw unique DOIs discovered | 2361 |
| Dedicated post-cutoff sweep (`from-pub-date:2026-09-09`, sorted by date) | 200 records returned |
| Tier 1 candidates in that window (3d-metal, primary, asymmetric H2 hydrogenation) | **0** |
| Passing the bibliographic screen (journal article; title carries asymmetric/enantioselective + hydrogenation; one 3d metal named; no review, highlight, correction, transfer hydrogenation or purely theoretical work) | 33 |
| After duplicate and alias de-duplication | 29 |
| Rejected `REJECT_DEVELOPMENT_OVERLAP` | 0 |
| Rejected `REJECT_KNOWN_EXPOSURE` (unified registry, alias-expanded) | 23 |
| Rejected as a removed PBV2 case | 1 |
| Already locked in the cohort | 4 |
| Surviving Gates A and B | 1 |
| Surviving Gate C exposure scan | **1** |
| Pending scope verification (see below) | 101 |

Every one of the 23 exposure rejections matched on DOI or a DOI alias. Title-identity matching found no additional case, so the registry is not over-rejecting on titles.

## The binding constraint

The developer's own literature screening has already enumerated essentially the whole 3d-metal asymmetric hydrogenation literature up to mid-2026. Of the 29 in-scope candidates discovered from a 2361-DOI sweep, 24 were already excluded or already in the cohort. A clean *retrospective* blind is close to impossible: the corpus work saw the field.

Two consequences follow.

1. The realistic source of clean blind papers is **future** literature. The prospective window is currently two weeks wide and empty. Monthly accrual after the cutoff is the reliable path to the remaining 4 slots.
2. A residual pool of 101 papers had an asymmetric-hydrogenation title, no registry hit, and no metal in its title. Round 2 left it unscreened because deciding scope needs an abstract. Round 3 below adjudicated it.

## Gate results for the 8 clean candidates

| Gate | Requirement | Result |
|---|---|---|
| A — development manifest (DOI, alias, paper_id, normalized title) | 0 | 0 |
| B — unified eligibility registry (DOI, alias, title) | 0 | 0 |
| C — repository branches, tags, full history, `git log -S`, local project roots, normalized-title scan | 0 | 0 |
| duplicates within the cohort | 0 | 0 |

Aggregate metal distribution: Ni 3, Mn 3, Co 2. Fe is still unrepresented; no Fe candidate survived the exposure gate, and metal balance was not traded against cleanliness.

Tier composition: Tier 1 prospective 0, Tier 2 `RETROSPECTIVE_BUT_UNSEEN` 8. None of these is presented as genuinely post-cutoff prospective.

## Source readiness

| Status | Count |
|---|---|
| `SOURCE_PACKAGE_READY` (main article and SI staged locally, byte counts, page counts and hashes on file) | 5 |
| `SOURCE_NOT_READY` (identified from publisher metadata; files not acquired) | 3 |

`EXECUTION_READY = NO` regardless of the identity gate.

## Method notes

Rounds 1 and 2 used the Crossref REST API with bibliographic queries only: titles, journal names, publication dates, type, license and link metadata, no abstracts. Round 3 additionally read abstract metadata, for scope classification only. No full text, reaction table, ligand, yield, ee or condition was read at any point. Candidate DOIs were alias-expanded through `tools/doi_aliases.py` before every comparison, and candidates were de-duplicated on normalized title as well as on DOI.

## Round 3: abstract-level scope adjudication of the residual pool

The 101 papers that carried an asymmetric-hydrogenation title, no registry hit and no metal in the title were adjudicated at abstract level. Abstract metadata came from Crossref (90 records, 53 of them via OpenAlex's inverted index). 11 papers had no abstract available anywhere.

| Outcome | Count |
|---|---|
| Reviewed | 101 |
| `IN_SCOPE` | **0** |
| `OUT_OF_SCOPE` | 81 |
| `SCOPE_UNCERTAIN` | 20 |

Reason codes: `OUT_NON_3D_METAL` 64, `OUT_HETEROGENEOUS_OUTSIDE_SCOPE` 11, `OUT_NOT_HYDROGENATION` 3, `OUT_TRANSFER_HYDROGENATION` 2, `OUT_THEORETICAL_ONLY` 1, `UNCERTAIN_METAL` 10, `UNCERTAIN_ARTICLE_TYPE` 9, `UNCERTAIN_H2_SOURCE` 1.

This confirms the round-2 inference rather than overturning it: the residual pool was dominated by precious-metal catalysis, and the rest is heterogeneous, metal-free or borane/FLP work, reviews, process and machine-learning papers, or abstracts too thin to settle the catalyst. Not a single homogeneous 3d-metal molecular-H2 asymmetric hydrogenation paper was hiding in it. No candidate reached Gate A, so Gates A, B and C had nothing to run on this round.

The 20 `SCOPE_UNCERTAIN` papers stay excluded. Unknown means exclude; they remain in the private pending list for a human pass if anyone wants to revisit them with full text.

Method: abstracts were used only to answer the five scope questions (primary experimental, asymmetric, molecular H2, 3d metal, benchmark reaction class). Classification was rule-based over keyword patterns. No abstract text was stored in the repository or in the private audit, and no ligand, catalyst structure, substrate, product, pressure, temperature, time, solvent, yield, ee, er or dr was recorded anywhere.
