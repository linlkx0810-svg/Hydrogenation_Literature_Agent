# Formal blind benchmark scaffold

This directory defines the evaluation contract for the first formal scientific blind benchmark. It intentionally contains templates rather than copyrighted article text.

1. Fill the development manifest with the 12 papers used for prompt/rule/code development.
2. Fill the blind manifest with held-out papers. Hold out at paper/DOI level, not row level.
3. Run `python tools/check_benchmark_overlap.py --dev ... --blind ...`. Proceed only on PASS.
4. Freeze model, prompts, rules, code revision and manifest hashes before opening Gold answers.
5. Evaluate at reaction × field level for eight fields: reaction, catalyst, ligand, substrate, product, conditions, yield, selectivity.
6. Compare Raw LLM and Verifier using the same cases.
7. Record `correct`, `incorrect`, `abstain_reasonable`, or `abstain_unnecessary`, plus evidence support.
8. Run `python tools/score_blind_benchmark.py --adjudication ...`.

Ligand aliases are judged by canonical chemical identity rather than literal string equality. An alias such as L9* is only resolved automatically when the source explicitly binds it to a ligand identity; otherwise unresolved/ambiguous is preserved.
