# Raw LLM extractor lineage: v1 → v2

Date: 2026-09-23. Branch `agent-v1-ligand-verifier`, base commit `353bfbc`.

The Raw LLM layer arrives on this branch in two separate steps, committed separately. Step A restores history unchanged. Step B builds the current extractor on top of it. Neither step deletes the other.

## Phase A — exact legacy port

Source branch: `codex/p0-prospective-blind-v2-eval-freeze`
Source commit of the old freeze base: `0d56d8905dcae74c2022bb77aa999fac88a66473`

| File | Historical blob SHA | Blob SHA after the port | Byte-identical |
|---|---|---|---|
| `modules/llm_extractor.py` | `b4aeff654824bd2d23f23b77920a9f8487917f27` | `b4aeff654824bd2d23f23b77920a9f8487917f27` | yes |
| `modules/openai_responses_provider.py` | `56519bf43d7b267d83023ca6491a7686bd48a9d9` | `56519bf43d7b267d83023ca6491a7686bd48a9d9` | yes |
| `tests/test_llm_extractor.py` | `07d6f8a831f342911fbaa3bd7fb7c1637c55ffad` | `07d6f8a831f342911fbaa3bd7fb7c1637c55ffad` | yes |
| `tests/test_openai_responses_provider.py` | `92ad93f5d729be7a7a42d6142336b57c9b4faa6f` | `80d6e7f3222d6337534b5c68cbace5c2c700d512` | **no, one test removed** |

The two module files were restored with `git cat-file blob` against the historical SHA and re-hashed after writing: both match, so the port is byte-identical and nothing was "fixed on the way in".

The one deviation is in the provider test. The legacy file imported `modules.verifier` and contained `test_adapter_is_compatible_with_verifier_request_without_prompt_changes`. `verifier-v1` is `DEFERRED_TO_V1_1` and is deliberately not on this branch, so that single test and its import were removed; the other four tests are unchanged. The removal is recorded here rather than hidden, and the original blob SHA above is the way back to it.

Destination commit for Phase A: see the commit titled "Port llm-extractor-v1 and the Responses adapter unchanged" on this branch.

## What Phase A does and does not establish

`llm-extractor-v1` is the **historical implementation**. Porting it proves the code runs here and its 16 legacy contract tests pass. It does not make it the current Raw LLM extractor:

- its `RESPONSE_SCHEMA` and `SYSTEM_PROMPT` cover the historical 8 fields (`ee_percent`, `yield_percent`, `h2_pressure_bar`, `temperature_c`, `reaction_time_h`, `solvent`, `ligand`, `substrate_class`);
- `benchmark/FIELD_SCHEMA_V1.json` defines 12 atomic fields, splits `conditions`, splits selectivity into `ee_or_er` and `stereochemical_outcome`, and adds `reaction`, `catalyst`, `substrate`, `product`;
- it therefore cannot satisfy `benchmark/SCORING_CONTRACT_V1.md`.

Phase A status: `LEGACY_PORT_VALIDATED`. `AGENT_V1_SYSTEM_FREEZE_READY` stays `NO`.

## Phase B — llm-extractor-v2

The current Raw LLM extractor is a new module, not an edit of the historical one:

| Concept | v1 (historical) | v2 (current) |
|---|---|---|
| Module | `modules/llm_extractor.py` | `modules/raw_llm_extractor_v2.py` |
| Extractor version | `llm-extractor-v1` | `llm-extractor-v2` |
| Prompt version | `llm-extractor-prompt-v1` | `llm-extractor-prompt-v2` |
| Response schema | inline `RESPONSE_SCHEMA`, 8 keys | `raw-extraction-schema-v2`, 12 keys, generated from `FIELD_SCHEMA_V1.json` |
| Output record | `ReactionCandidate` (8 fields) | `RawPredictionRecord` (12 fields + provenance + abstention reasons) |
| Field source of truth | hard-coded in the module | `benchmark/FIELD_SCHEMA_V1.json` |

v1 stays on the branch, importable and tested, as the lineage anchor and as the only way to reproduce a historical run. It is marked `LEGACY_NOT_USED` in the Agent v1.0 execution graph.

## Rule

A change to v2's prompt, schema or validation after the system freeze creates `llm-extractor-v3`. Versions are never edited in place, and a result is always reported against the extractor version that produced it.
