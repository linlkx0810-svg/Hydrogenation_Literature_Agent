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
2. A residual pool of 101 papers has an asymmetric-hydrogenation title, is absent from the registry, but does not name a metal in its title. Most are probably precious-metal or organocatalytic work, which is exactly why the 3d screening never captured them. Deciding scope needs an abstract-level read. This custodian did not read any abstract, so those papers stay unscreened rather than being guessed into the cohort. The list is held privately for a human custodian scope pass.

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

Discovery used the Crossref REST API with bibliographic queries only. The custodian read titles, journal names, publication dates, type, license and link metadata. No abstract, no full text, no reaction table, no ligand, yield, ee or condition was read for any candidate. Candidate DOIs were alias-expanded through `tools/doi_aliases.py` before every comparison, and candidates were de-duplicated on normalized title as well as on DOI.
