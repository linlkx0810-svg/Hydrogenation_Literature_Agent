# Sealed external reserve policy

> **Status update 2026-09-22: EXPOSED_AFTER_BLIND_V1. Not a clean holdout.**
> Local records show that these four DOIs are the Blind-v1 cases `3DXR-001`…`3DXR-004`. Agent v4.1 evaluated them once on 2026-08-12 (Gold, predictions and scores exist). They were marked `EXPOSED_AFTER_BLIND_V1` on 2026-08-17, and a post-hoc ligand failure analysis exists. They are listed in `known_contamination_manifest.csv` and cannot certify Agent v1.0. See `development_manifest_recovery_status.md` and `NEW_BENCHMARK_EPOCH_PROPOSAL.md`. The content restrictions below still apply: do not open their Gold, predictions or failure analysis for development.

The four DOI identities in `sealed_external_reserve_manifest.csv` were historically reserved as a contamination-clean external holdout (Co 3, Mn 1).

## Allowed before the one-shot blind run

- verify DOI and bibliographic identity;
- verify that a paper file is the correct document;
- check development/contamination overlap using DOI only;
- hash and stage source files without extracting target answers.

## Forbidden before the one-shot blind run

- create Gold field values;
- inspect source text for the purpose of modifying extraction rules;
- tune prompts, entity mappings, resolver vocabulary, thresholds, or verifier logic based on these papers;
- use these papers in unit tests, demonstrations, error analysis, or development examples.

During recovery on 2026-09-22, DOI/title metadata were checked. Any abstract text surfaced incidentally during bibliographic lookup must not be used for system tuning. Scientific target fields remain sealed.

The reserve is only four papers, so it is an external prospective check rather than the complete 12–20-paper formal benchmark originally planned. Results from this reserve should be reported separately from any larger benchmark.
