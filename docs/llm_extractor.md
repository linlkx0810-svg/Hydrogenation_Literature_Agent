# LLM Extractor v1

## Purpose

`llm-extractor-v1` is an optional evidence-bounded extractor that sits beside the existing deterministic `rule-baseline-v1`. It does not replace the rule baseline and it does not change existing production records.

The design follows a simple scientific rule: **the model may extract only what is explicitly supported by the supplied evidence chunk, and it may abstain on every field.**

This layer implements extraction only. Independent field-level verification is a separate stage (`verifier-v1`, Issue #4).

## Why the provider is separated from the extractor

`modules/llm_extractor.py` defines a small `LLMProvider` protocol. The core extractor knows nothing about a specific API or SDK. A provider adapter receives:

- the versioned system prompt;
- one already-selected evidence chunk;
- the strict response schema;
- the prompt version.

It returns one JSON object. This separation allows hosted models, local models and deterministic replay fixtures to be evaluated under the same scientific schema.

## Evidence boundary

The LLM extractor must receive **one already-selected local evidence chunk**, not an entire corpus and not an unrestricted literature search result.

The caller owns and preserves:

- `evidence_text`;
- `evidence_start` / `evidence_end`;
- candidate ID;
- source locator metadata.

The provider cannot overwrite those provenance fields.

## Strict response contract

The provider must return exactly eight keys:

```json
{
  "ee_percent": 97.5,
  "yield_percent": 93.0,
  "h2_pressure_bar": 20.0,
  "temperature_c": 25.0,
  "reaction_time_h": 12.0,
  "solvent": "THF",
  "ligand": "BINAP",
  "substrate_class": "aryl ketone"
}
```

Every value may instead be `null`.

A field must be `null` when:

- the evidence does not state it;
- multiple candidate values are present and the target association is unclear;
- the evidence conflicts internally;
- the value appears to belong to another reaction;
- the model would need outside chemical knowledge to infer it.

The validator rejects:

- missing required keys;
- extra explanation/reasoning keys;
- malformed JSON;
- stringified numbers such as `"95"`;
- non-finite numbers;
- percentages outside 0–100;
- negative pressure or time;
- empty strings.

Validation failures raise `LLMResponseSchemaError`. They are not silently corrected.

## Confidence and scientific status

`llm-extractor-v1` deliberately records `confidence = 0.0` in the common reaction-candidate schema. This is **not** a claim that the result is wrong; it means the extractor does not pretend to have a calibrated scientific confidence score.

Every LLM result is also marked:

```text
verification_status = unverified
```

The later verifier stage must decide whether each field is accepted, rejected or unresolved.

## Compare the rule baseline and LLM extractor on the same synthetic chunk

The repository includes a copyright-safe synthetic example:

```text
examples/evidence_chunk_synthetic.txt
examples/llm_response_synthetic.json
```

Run the deterministic rule baseline with one neighboring sentence so its evidence window covers the same two-sentence synthetic chunk:

```bash
python agent.py extract-text \
  --input examples/evidence_chunk_synthetic.txt \
  --context 1
```

Replay a saved strict LLM response through the exact LLM schema and provenance layer:

```bash
python agent.py llm-extract-replay \
  --input examples/evidence_chunk_synthetic.txt \
  --response examples/llm_response_synthetic.json \
  --model-name example-model
```

`llm-extract-replay` does **not** call a network model. It exists so CI and reviewers can test the LLM extraction contract reproducibly. A real model adapter should implement the same `LLMProvider.complete_json()` interface.

## Minimal provider adapter example

```python
from modules.llm_extractor import LLMExtractionRequest, extract_reaction_chunk


class MyProvider:
    model_name = "my-model"

    def complete_json(self, request: LLMExtractionRequest):
        # Call a hosted or local model here using:
        # request.system_prompt
        # request.user_prompt
        # request.response_schema
        # Return one JSON string or mapping.
        raise NotImplementedError


provider = MyProvider()
result = extract_reaction_chunk(
    evidence_text="one pre-selected evidence chunk",
    provider=provider,
    candidate_id="paper-001-rxn-001",
    source_locator={"paper_id": "paper-001", "page": 4},
)
print(result.to_dict())
```

Provider-specific credentials and network clients should remain outside the extraction schema. This avoids coupling scientific evaluation to one vendor.

## Blind-integrity rule

Normal LLM development must not access reviewer-only or blind-gold material. The unified CLI applies the same `modules/blind_integrity.py` path guards to both the evidence input and saved provider response.

Do not tune prompts or provider parameters using frozen blind cases. A blind evaluation should occur only after extractor and prompt versions are frozen.

## Versioning

Current versions:

```text
extraction_version = llm-extractor-v1
prompt_version     = llm-extractor-prompt-v1
```

Any substantive prompt change should increment the prompt version. Any schema, parsing or scientific-behavior change should increment the extraction version before a new benchmark is reported.

## Non-goals of v1

This module does not yet:

- verify that extracted values are truly supported by evidence;
- resolve chemical identity across papers;
- perform OCSR or table/image reconstruction;
- promote records to `final-verified` or `ML-ready`;
- choose one value from an unresolved source conflict.

Those remain separate stages so their performance can be measured independently.
