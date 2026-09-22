# Sealed external reserve policy

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
