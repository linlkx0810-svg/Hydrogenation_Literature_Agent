# Literature-derived implementation plan

## Purpose

This note translates design patterns from recent scientific-literature extraction systems into a staged implementation plan for the Hydrogenation Literature Agent.

The objective is **not** to reproduce another system. The objective is to borrow validated architectural ideas while preserving this project's core scientific constraints: provenance, abstention, non-destructive normalization, independent blind review, and human verification before scientific use.

## Current project position

The repository already has a strong deterministic baseline:

- multi-source literature retrieval and screening;
- reaction-level local evidence windows instead of paper-level global maxima;
- source offsets and evidence text;
- rule-based extraction with a common reaction-candidate schema;
- synthetic regression tests and a separate blind-validation philosophy;
- explicit separation of software correctness, benchmark performance, and scientific validity.

The next step should therefore be **controlled reliability improvements**, not a wholesale rewrite.

---

## Reference systems and what to borrow

### 1. ChatExtract

**Paper:** Polak & Morgan, *Nature Communications* 2024, DOI: 10.1038/s41467-024-45914-8

**Useful pattern:**
- first identify a short relevant text window;
- extract structured fields from that local context;
- explicitly allow missing information;
- use redundant follow-up verification questions;
- let the verifier reject an initially plausible answer;
- use strict structured outputs for automation.

**What to adopt here:**
- `llm-extractor-v1` should operate on already selected evidence chunks rather than whole papers;
- every field must support `null` / unresolved;
- verification should be a separate second pass;
- multiple-value passages require stricter checking than simple single-value passages.

**What not to copy blindly:**
- do not assume conversational redundancy alone is sufficient for chemical identity resolution;
- do not discard all partially useful records merely because one field is missing; preserve field-level status.

Reference: https://www.nature.com/articles/s41467-024-45914-8

---

### 2. Eunomia

**Paper:** Ansari & Moosavi, *Digital Discovery* 2024, DOI: 10.1039/D4DD00252K

**Useful pattern:**
- LLM agent uses tools rather than relying on one prompt;
- document search retrieves the most relevant context;
- chain-of-verification re-checks whether evidence actually supports the extracted claim;
- domain-specific tools and external datasets can be invoked when needed.

**What to adopt here:**
- keep extraction, evidence retrieval, verification, and normalization as separate tools/modules;
- verification must check logical support, not just formatting;
- agent orchestration should sit above deterministic scientific tools, not replace them.

**What not to copy blindly:**
- do not give the agent unrestricted access to blind gold, reviewer-only files, or historical adjudications;
- do not let free-form reasoning become the stored scientific evidence.

Reference: https://pubs.rsc.org/en/content/articlehtml/2024/dd/d4dd00252k

---

### 3. OpenChemIE

**Paper:** Fan et al., *Journal of Chemical Information and Modeling* 2024, DOI: 10.1021/acs.jcim.4c00572

**Useful pattern:**
- treat chemistry papers as multi-modal documents;
- extract from text, tables, and figures with modality-specific components;
- integrate those outputs only at the document level using chemistry-informed logic;
- explicitly evaluate the full pipeline, not only individual components.

**What to adopt here:**
- introduce a common intermediate representation for mentions from text/table/figure sources;
- represent compound labels such as `1a`, `2b`, `L1` separately from resolved chemical identity;
- keep cross-modal links explicit and allow unresolved links;
- evaluate document-level reaction assembly separately from field extraction.

**What not to do yet:**
- do not make heavyweight OCSR dependencies mandatory in the default environment;
- do not integrate multimodal components into production until a synthetic benchmark is passing.

Reference: https://arxiv.org/abs/2404.01462

---

### 4. ReactionSeek

**Paper:** Li et al., *Nature Communications* 2026, DOI: 10.1038/s41467-026-70180-1

**Useful pattern:**
- hybrid LLM + cheminformatics architecture;
- separate image mining, text mining, and chemical-data standardization;
- use chemistry-aware tools for canonicalization rather than asking the LLM to normalize everything;
- retain a downstream machine-readable reaction dataset and query layer.

**What to adopt here:**
- keep extraction and normalization as distinct stages;
- add chemistry-tool adapters behind stable interfaces;
- standardization should be versioned and reproducible;
- future query/knowledge functionality should consume the verified dataset rather than raw extraction output.

**What not to copy blindly:**
- this project requires stronger provenance and independent adjudication because asymmetric catalysis depends critically on exact ligand/catalyst identity and stereochemistry.

Reference: https://www.nature.com/articles/s41467-026-70180-1

---

### 5. MARCUS

**Paper:** Rajan et al., *Digital Discovery* 2025, DOI: 10.1039/D5DD00313J

**Useful pattern:**
- text extraction and optical chemical structure recognition are complementary;
- multiple OCSR engines can be compared rather than trusted individually;
- stereochemical validation deserves a dedicated layer;
- human-in-the-loop refinement is a legitimate part of a scientific curation system.

**What to adopt here:**
- exact chemical identity should be separate from raw text labels;
- normalized entities should support canonical identifiers and stereochemical state;
- enantiomers/diastereomers must never be collapsed by loose alias matching;
- human adjudication should remain explicit and auditable.

**What not to do yet:**
- do not deploy a GPU-heavy OCSR stack before text/evidence verification and registry logic are stable.

Reference: https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00313j

---

## Recommended target architecture

```text
retrieval / screening
        |
        v
source acquisition + parsing
        |
        v
candidate evidence selection
        |
        +-------------------------+
        |                         |
        v                         v
rule-baseline-v1          llm-extractor-v1
        |                         |
        +------------+------------+
                     v
              common raw schema
                     |
                     v
                 verifier-v1
                     |
                     v
        field-level accepted / rejected /
              unresolved / conflict
                     |
                     v
      chemistry identity normalization
     raw label -> alias/family/exact/unresolved
                     |
                     v
            human adjudication
                     |
                     v
       source-verified reaction dataset
                     |
          +----------+----------+
          |                     |
          v                     v
   ML-ready subset       claim/mechanism layer
```

## Execution order

### P0 — reliability before capability expansion

1. Implement `llm-extractor-v1` beside the current deterministic baseline.
2. Implement `verifier-v1` with field-level acceptance/rejection/unresolved/conflict.
3. Harden blind-data separation and contamination guards.
4. Benchmark rule baseline vs LLM extractor on development/synthetic data only.

### P1 — chemical identity and document assembly

5. Add a non-destructive chemistry identity normalization layer.
6. Add synthetic stereochemistry-sensitive registry tests.
7. Prototype multi-modal/document-level reaction assembly behind an experimental flag.
8. Only after the above is stable, evaluate OCSR/table adapters.

### Later — scientific knowledge layer

9. Claim extraction.
10. Mechanistic/DFT descriptors.
11. Similarity/ML recommendation.
12. Natural-language query/API/UI.

---

## Guardrails for Codex / implementation agents

- Do not read or search frozen blind gold or reviewer-only outputs.
- Do not modify production data in place.
- Do not tune prompts against blind examples.
- Do not convert `unresolved` into a guessed value.
- Do not silently resolve main-text/SI conflicts.
- Preserve raw source labels and evidence before adding normalized fields.
- Keep the existing deterministic extractor as a frozen comparison baseline.
- Add synthetic tests before applying a new module to real scientific records.
- Passing CI is software evidence only; it is not proof of scientific validity.

## GitHub implementation issues

- #3 P0: Add `llm-extractor-v1` with explicit abstention and common schema
- #4 P0: Add `verifier-v1` and field-level evidence acceptance/rejection
- #5 P0: Harden blind benchmark protocol and contamination guards
- #6 P1: Add chemistry identity normalization layer with unresolved-first policy
- #7 P1 research spike: document-level multimodal reaction assembly

## Recommended first Codex task

Start with **issue #5**, then **#3**, then **#4**.

Reason: blind-data isolation should be enforceable before adding a more capable model-facing extractor. After that, build the LLM extractor and verifier while the deterministic baseline remains untouched.
