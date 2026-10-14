# Agent v1.0 pipeline audit

Date: 2026-09-23
Audited commit: `cb48b2d439b272b8c1740b0d1de197a01e3bc98f` (branch `agent-v1-ligand-verifier`)
Comparison point: `origin/codex/p0-prospective-blind-v2-eval-freeze` (old freeze base `0d56d8905dcae74c2022bb77aa999fac88a66473`)

No code was changed while writing this audit. No prospective-blind-v3 identity, manifest or source was opened.

## 1. The repository holds two disjoint code lines

The central finding is not that the two pipelines disagree. It is that **they do not exist on the same branch**.

| Component | On `agent-v1-ligand-verifier` | On the old freeze branch |
|---|---|---|
| `modules/reaction_candidate_extraction.py` | yes (modified) | yes (blob `c8e36d7…`, frozen as the evidence builder) |
| `modules/ligand_resolver.py` | yes | **no** |
| `modules/extraction_verifier.py` | yes | **no** |
| `modules/llm_extractor.py` | **no** | yes (blob `b4aeff6…`, `llm-extractor-v1`) |
| `modules/verifier.py` | **no** | yes (blob `7733e1f…`, `verifier-v1`) |
| `modules/openai_responses_provider.py` | **no** | yes (blob `56519bf…`, `openai-responses-json-v1`) |
| `modules/blind_integrity.py`, `modules/development_benchmark.py` | no | yes |
| `agent.py` unified CLI | yes | no |
| `tools/run_trust_benchmark.py`, `tools/score_blind_benchmark.py` | yes | no |
| `tools/run_development_benchmark.py`, `tools/check_development_blind_overlap.py` | no | yes |

So the current developer baseline **contains no LLM layer at all**, and the old freeze contains no ligand resolver, no evidence verifier and no CLI. Neither branch alone can run the pipeline the project describes.

## 2. What is actually runnable today on the baseline

`agent.py` exposes four commands, all deterministic and API-key-free:

- `extract-text` → `extract_reaction_candidates`
- `verify-text` → `extract_reaction_candidates` + `verify_candidates`
- `benchmark` → `tools/run_benchmark.py` on a synthetic JSONL
- `trust-benchmark` → `tools/run_trust_benchmark.py` on the same synthetic JSONL

CI runs all four on `examples/benchmark_synthetic.jsonl`. Nothing in CI touches a model provider, and there is no code path on this branch that could.

## 3. Component-by-component verdict

### `modules/reaction_candidate_extraction.py` — evidence builder **and** answer extractor

Two jobs in one function. `extract_reaction_candidates` builds the deterministic evidence window (ee/yield anchor sentence ± `context_sentences`, duplicate windows dropped by `(start, end)`), which is the role the old freeze pinned. But the same function also fills all eight scientific fields by regular expression (`EE_RE`, `YIELD_RE`, `PRESSURE_RE`, `TEMP_RE`, `TIME_RE`, `SOLVENT_RE`, `LIGAND_RE`, `SUBSTRATE_RE`) and attaches a hand-weighted `confidence`.

Consequence: those regex values are simultaneously (a) a selection signal, (b) the `rule-baseline-v1` prediction, and (c) in `run_trust_benchmark.py`, the thing labelled *raw*. Verdict: **retain as the evidence builder, demote its field values**. The field values must be marked as baseline-only and must not be handed to the LLM or counted as LLM output.

### `tools/run_trust_benchmark.py` — mislabels the baseline as Raw LLM

`evaluate()` calls `extract_reaction_candidates`, reports it under the key `raw`, then runs `verify_candidate` and reports the result under `verifier`. There is no model in the loop. Reporting this as "Raw vs Verifier" would state that an LLM was evaluated when none ran. Verdict: **rename the comparison to `rule-baseline-v1` vs `evidence-verifier-v1`, and reserve the word Raw for real model output.**

It also pairs prediction to gold by list index (`predicted[index]`), which silently mis-associates every later candidate once one window is missed. Acceptable for a synthetic contract test, not acceptable as a scientific scorer.

### `modules/extraction_verifier.py` — deterministic, but it also normalizes

Per field it answers `supported` / `unsupported`; per candidate it routes `accept` / `review` / `reject`, and it first checks evidence integrity by re-slicing `source_text[start:end]` against the stored evidence. It never rewrites a value — the "verifier verifies" rule holds.

Two caveats. First, the ligand branch calls `resolve_ligand_mention` and attaches `canonical_id` / `canonical_name`, so **normalization happens inside verification**; the resolver's `resolved` status is also renamed to `supported`, mixing two vocabularies. Second, `ligand` is excluded from the regular `checks` list and handled only through the resolver, so a ligand is never checked for presence in its own evidence window.

### `modules/ligand_resolver.py` — correct layer, correct discipline

Explicit names resolve through a 17-entry canonical registry; paper-local `L1`/`L2` aliases resolve only from an explicit in-source definition; contradictory definitions return `ambiguous`; undefined aliases return `unresolved`. No cross-paper inference, no external calls. Verdict: **retain as the normalization layer**, and move it out of the verifier's internals so the graph has one normalization step.

### `modules/llm_extractor.py` (old branch) — the only real Raw LLM

Provider-agnostic, one evidence chunk per call, strict JSON schema with every field nullable, numeric ranges enforced, extra keys rejected, schema failure raises instead of coercing. This is what "Raw LLM" must mean. Verdict: **port unchanged; it is the missing layer.**

### `modules/verifier.py` (old branch) — a second, LLM-based verifier

Field-by-field, statuses `accepted` / `rejected` / `unresolved` with reason codes `supported`, `missing`, `ambiguous`, `conflict`, `wrong_entity`, `wrong_reaction`, `format_error`. It never rewrites values either. It overlaps in purpose with `extraction_verifier.py` but not in mechanism: one asks a model, the other checks strings against an offset-bound window.

### `modules/openai_responses_provider.py` (old branch) — transport only

No scientific logic; lazy SDK import; injectable client; no key default. Verdict: **port unchanged.**

### Legacy, not part of Agent v1.0

`modules/reaction_data_extraction.py` (paper-level Stage 5 extractor, superseded by reaction-level work), `modules/literature_search.py`, `modules/pdf_download.py`, `modules/title_abstract_screening.py`, `modules/fulltext_screening.py` (corpus-building stages, not part of the extraction benchmark), `tools/score_blind_benchmark.py` (CSV adjudication scorer whose `field` column is free text and whose vocabulary matches neither schema).

## 4. Interface incompatibilities

1. **Three field vocabularies.** Old freeze: 8 atomic fields (`ee_percent` … `substrate_class`). PR #20 documentation: 8 high-level fields (`reaction`, `catalyst`, `ligand`, `substrate`, `product`, `conditions`, `yield`, `selectivity`). `score_blind_benchmark.py`: whatever the adjudication CSV contains. Nothing maps between them.
2. **Two verifier status vocabularies**: `accepted/rejected/unresolved` + reason codes, versus `supported/unsupported/ambiguous/unresolved` + `accept/review/reject`.
3. **Two notions of "the answer"**: `ReactionCandidate` dataclass fields versus `llm-extractor-v1` JSON payload. They share field names but not provenance rules.
4. **`conditions` as one compound field** in the PR #20 docs makes partial correctness unscoreable: pressure, temperature, time and solvent collapse into one right/wrong bit.
5. **Missing-value semantics are undefined.** `None` currently means "regex found nothing", which is not the same as *not reported in the source*, *not applicable to this reaction*, *unresolved identity*, or *ambiguous*.

## 5. What this implies for the freeze

Agent v1.0 cannot be frozen as a scientific system at this commit, because the formal graph's Raw LLM stage is not present on this branch and the field schema is not decided. It can be frozen once the port and the schema decision land. The specification documents written alongside this audit (`docs/AGENT_V1_EXECUTION_GRAPH.md`, `benchmark/FIELD_SCHEMA_V1.json`, `docs/FIELD_SCHEMA_CROSSWALK_V1.md`, `benchmark/SCORING_CONTRACT_V1.md`) define the target; `benchmark/agent_v1_execution_manifest.json` records which slots are still `UNRESOLVED_BEFORE_FREEZE`.
