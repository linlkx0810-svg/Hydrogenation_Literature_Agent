# Prospective blind v2 evaluation protocol

## Status

The prospective blind v2 paper cohort is identity-frozen at 12 papers.

- quota complete: yes
- duplicate papers: 0
- overlap with the frozen non-blind development set: 0
- paper overlap gate: `PASS`
- blind manifest SHA256: `21f9e9180428514d88868aeb3b7e6acd23f3aac29ada2dc0ce466abed22114e0`
- locked-list SHA256: `97f6b78f2947bb972c57db078456c3ec9ba11ccdb0a03ebb3cd0899b6de029c7`

No blind scientific answers, raw mentions, model predictions, Resolver outputs, normalization outputs, or scores existed at the time of this identity freeze.

## Frozen scientific components

The reported v2 blind run must use the already-frozen scientific contracts without prompt or logic edits:

- extractor: `llm-extractor-v1`
- extractor prompt: `llm-extractor-prompt-v1`
- verifier: `verifier-v1`
- verifier prompt: `verifier-prompt-v1`
- eight fields: `ee_percent`, `yield_percent`, `h2_pressure_bar`, `temperature_c`, `reaction_time_h`, `solvent`, `ligand`, `substrate_class`

Any later scientific prompt or logic change requires a new evaluation version.

## Live-provider boundary

`modules/openai_responses_provider.py` is a transport-only adapter. It must not alter the extractor/verifier prompts, field definitions, evidence chunks, scientific values, or abstention rules.

The adapter uses the Responses API Structured Outputs interface with strict JSON Schema. The exact provider/model ID and runtime settings are not yet frozen. The benchmark must remain disabled until they are pinned in the run manifest.

For OpenAI, use an environment variable for the API key. Never place API keys in source files, fixtures, logs, issue bodies, or benchmark manifests.

## Pre-run freeze requirements

Before the first live blind prediction, record all of the following:

1. provider name;
2. exact model ID returned/accepted by the provider;
3. provider-adapter version and git blob;
4. SDK version;
5. reasoning effort if used;
6. temperature/top-p only when explicitly supported and intentionally set;
7. extractor/verifier versions, prompt versions and git blobs;
8. blind identity manifest hash;
9. source-artifact hashes;
10. evidence-chunk construction version and immutable chunk hashes;
11. timestamp and repository commit.

Do not start blind inference if any required freeze field is unresolved.

## One-shot run order

1. Validate the frozen blind source identities and hashes without opening any reviewer-only gold.
2. Construct the frozen evidence chunks using the predeclared evidence-building procedure.
3. Run Raw LLM extraction exactly once per frozen case/chunk.
4. Seal raw outputs and compute their hashes.
5. Run `verifier-v1` on the exact same chunks and extracted values.
6. Seal verifier outputs and compute their hashes.
7. Only after predictions are sealed may the independent reviewer/custodian construct or open blind gold for adjudication.
8. Score Raw LLM and LLM+Verifier separately.

Transport retries are allowed only for failed API delivery and must resend an identical payload. A retry must not change model, prompt, schema, chunk, or sampling settings.

## Reported metrics

Report both aggregate and per-field metrics:

- precision, recall, F1;
- answer rate;
- attempted-gold coverage;
- hallucinations on absent fields;
- abstentions on present fields;
- wrong-reaction errors;
- wrong-entity errors;
- ambiguous/conflict abstentions;
- verifier wrong-value block rate;
- verifier correct-value retention.

The first 12-paper result is a prospective pilot benchmark. It should not be presented as a broad population estimate for all asymmetric-hydrogenation literature.

## Scientific validity boundary

Passing software tests validates the contract and transport layer only. Scientific performance is established only by the frozen prospective blind run followed by independent source-level adjudication.
