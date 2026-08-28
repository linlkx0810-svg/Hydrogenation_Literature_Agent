# Hydrogenation Literature Agent

> A reproducible scientific-literature mining pipeline for base-metal H₂ asymmetric hydrogenation, with multi-source retrieval, staged screening, provenance-aware reaction extraction, benchmarking, and human verification.

This repository is a research-software prototype built to turn fragmented catalysis literature into structured, reviewable reaction data. It currently supports Fe, Co, Mn, and Ni molecular-H₂ asymmetric hydrogenation through config-driven workflows.

## Why this project exists

Catalysis papers report reaction conditions and performance in inconsistent formats, often across text, tables, and supporting information. A useful scientific agent therefore needs more than keyword search: it must retrieve papers, screen relevance, associate values with local reaction context, preserve evidence, expose uncertainty, and remain auditable by a chemist.

This project implements that pipeline as a deterministic baseline that can later be compared with LLM-assisted extraction using the same evaluation framework.

## Architecture

```text
OpenAlex / Crossref / Semantic Scholar
                |
                v
      Stage 1: retrieval + dedup
                |
                v
      Stage 2: title/abstract screening
                |
                v
      Stage 3: OA / user-authorised PDF access
                |
                v
      Stage 4: full-text evidence screening
                |
                v
      Stage 5A: paper-level extraction
                |
                +------------------------------+
                v                              v
      Stage 5B: reaction candidates     provenance + confidence
                |                              |
                +--------------+---------------+
                               v
                    human verification
                               |
                               v
                    structured dataset
```

The new reaction-candidate baseline avoids treating the highest ee/yield in an entire paper as a single reaction record. Instead, it anchors on local result statements, associates nearby conditions, normalises pressure units, and preserves the exact evidence window and character offsets used for extraction.

## What is implemented

- **Multi-source retrieval** — OpenAlex, Crossref, Semantic Scholar, citation chasing
- **Config-driven screening** — YAML-defined metal/reaction rules, exclusions, and output settings
- **PDF acquisition workflow** — open-access resolution plus user-authorised institutional browser mode
- **Full-text evidence classification** — Confirmed / Excluded / Uncertain
- **Paper-level extraction** — ee, yield, pressure, temperature, solvent, time, TON/TOF
- **Reaction-level candidate extraction** — local field association instead of global maxima
- **Provenance** — evidence text plus source character offsets for each candidate
- **Confidence scoring** — deterministic confidence based on co-located supporting fields
- **Unit normalisation** — pressure converted to bar from bar/atm/psi/MPa/kPa
- **Benchmark harness** — field-level and candidate-count evaluation
- **Regression tests + CI** — pytest across Python 3.10–3.12 via GitHub Actions
- **Human-in-the-loop safeguards** — extracted values are not treated as scientifically verified until checked against source material

## Reaction-level output schema

A candidate record looks like:

```json
{
  "candidate_id": "rxn-0001",
  "ee_percent": 97.5,
  "yield_percent": 93.0,
  "h2_pressure_bar": 20.0,
  "temperature_c": 25.0,
  "reaction_time_h": 12.0,
  "solvent": "THF",
  "ligand": "BINAP",
  "substrate_class": "aryl ketone",
  "confidence": 0.95,
  "evidence_text": "...",
  "evidence_start": 1342,
  "evidence_end": 1516,
  "extraction_method": "rule-baseline-v1"
}
```

The evidence fields are deliberately part of the data model: a reviewer can trace every extracted value back to the local source text used by the extractor.

## Quick start

### Windows

```bat
git clone https://github.com/linlkx0810-svg/Hydrogenation_Literature_Agent.git
cd Hydrogenation_Literature_Agent
setup.bat

run_search.bat
run_screening.bat
run_download.bat
run_extraction.bat
```

### macOS / Linux

The Python modules are cross-platform. See `docs/setup_instructions.md` for module-level commands.

### Development / tests

```bash
python -m pip install -r requirements-dev.txt
pytest -q
python tools/run_benchmark.py --dataset examples/benchmark_synthetic.jsonl
```

The bundled benchmark is synthetic and exists to make CI deterministic and copyright-safe. Scientific benchmark results should be reported separately from manually curated, source-verified examples.

## Repository structure

```text
Hydrogenation_Literature_Agent/
├── config/                     # Fe / Co / Mn / Ni YAML configurations
├── modules/
│   ├── literature_search.py
│   ├── title_abstract_screening.py
│   ├── pdf_download.py
│   ├── fulltext_screening.py
│   ├── reaction_data_extraction.py
│   └── reaction_candidate_extraction.py
├── tools/
│   └── run_benchmark.py
├── tests/
│   ├── test_reaction_data_extraction.py
│   └── test_reaction_candidate_extraction.py
├── examples/
│   ├── example_extraction_output.csv
│   └── benchmark_synthetic.jsonl
├── docs/
│   ├── methodology.md
│   ├── validation_protocol.md
│   ├── limitations.md
│   └── setup_instructions.md
├── .github/workflows/tests.yml
├── requirements.txt
└── requirements-dev.txt
```

## Validation philosophy

The project separates three different claims:

1. **Software correctness** — regression tests verify deterministic parsing behaviour.
2. **Benchmark performance** — a benchmark runner measures candidate-count and field-level extraction accuracy.
3. **Scientific validity** — real extracted records require source verification by a human reviewer.

This distinction is intentional. Passing unit tests does not imply that an extraction system is scientifically accurate on unseen literature.

See `docs/validation_protocol.md` for the planned blind-test methodology, including precision/recall/F1 and field-level error analysis.

## Current limitations

- Reaction extraction remains rule-based and is a baseline, not a learned model.
- PDF text extraction does not solve scanned-document OCR or complex table reconstruction.
- Local-window association reduces paper-level mixing but does not guarantee that all fields belong to the same experimental row.
- SciFinder and Reaxys are not queried through the public-API pipeline.
- Real scientific benchmark data are intentionally not bundled unless redistribution is permitted.

## LLM roadmap

The next model-facing layer is designed as an **alternative extractor**, not as a replacement for evaluation:

```text
same evidence chunk
      |----------------------|
      v                      v
rule-baseline-v1       llm-extractor-v1
      |                      |
      +----------+-----------+
                 v
          common schema
                 |
                 v
           blind benchmark
```

This makes it possible to ask a useful engineering question: does an LLM materially improve reaction-field association and recall relative to a deterministic baseline, and at what cost/error profile?

## Responsible use

This repository contains no journal PDFs or copyrighted article text. PDF access is limited to open-access sources or documents the end user is authorised to access. Users are responsible for publisher terms, institutional licences, and copyright compliance.

All automatically extracted scientific values must be checked against the source before publication or downstream scientific use.

## License

MIT. See `LICENSE`.
