# Formal blind benchmark scaffold

This directory defines the evaluation contract for the first formal scientific blind benchmark. It intentionally contains templates rather than copyrighted article text.

1. Fill the development manifest with the 12 papers used for prompt/rule/code development.
2. Fill the blind manifest with held-out papers. Hold out at paper/DOI level, not row level.
3. Run `python tools/check_benchmark_overlap.py --dev ... --blind ... --exclude benchmark/known_contamination_manifest.csv`. Proceed only on PASS. The exclusion manifest is intentionally broader than the recovered formal development manifest and blocks papers known to have been used in historical development/pilot work.
4. Freeze model, prompts, rules, code revision and manifest hashes before opening Gold answers.
5. Evaluate at reaction × field level for eight fields: reaction, catalyst, ligand, substrate, product, conditions, yield, selectivity.
6. Compare Raw LLM and Verifier using the same cases.
7. Record `correct`, `incorrect`, `abstain_reasonable`, or `abstain_unnecessary`, plus evidence support.
8. Run `python tools/score_blind_benchmark.py --adjudication ...`.

Ligand aliases are judged by canonical chemical identity rather than literal string equality. An alias such as L9* is only resolved automatically when the source explicitly binds it to a ligand identity; otherwise unresolved/ambiguous is preserved.


## Recovered historical development/pilot records

`recovered_historical_pilot_manifest.csv` records six papers that are directly documented as the Stage 5C pilot set (3 Fe + 3 Ni). They are treated as known contamination for future blind selection.

This file is **not** asserted to be the complete later 12-paper development set. The historical project record confirms that a 12-paper development set was planned/used, but the complete paper-by-paper mapping has not been recovered from authoritative records. Missing identities must remain missing rather than be inferred.
