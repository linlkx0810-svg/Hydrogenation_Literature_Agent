# Hydrogenation Literature Agent

> **Automated systematic-review pipeline for base-metal H₂ asymmetric hydrogenation — multi-source API search, rule-based screening, and structured catalytic data extraction. Architected for LLM integration.**

A modular, config-driven pipeline for systematic literature mapping of
**base-metal-catalyzed asymmetric molecular-H₂ hydrogenation**.
Covers iron (Fe), cobalt (Co), manganese (Mn), and nickel (Ni) catalyst systems
out of the box — switch metals with one command.

---

## Motivation

Asymmetric hydrogenation is a cornerstone of pharmaceutical and fine-chemical
synthesis. While precious-metal catalysts (Rh, Ir, Ru) dominate the established
literature, earth-abundant base metals (Fe, Co, Mn, Ni) have emerged as
sustainable alternatives — but their literature is fragmented across databases
and often conflated with related reactions (transfer hydrogenation, hydrosilylation).

This tool was built to solve a real data-collection bottleneck: **manually
surveying hundreds of papers across five stages of relevance filtering to
extract structured catalytic performance data** (ee%, yield, conditions) that
can inform ligand design and reaction optimisation.

---

## AI / Scientific Workflow Relevance

This project demonstrates several competencies relevant to AI-assisted scientific workflows:

| Capability | How it appears here |
|------------|---------------------|
| **Structured data extraction** | Rule-based extraction of ee%, yield, H₂ pressure, ligand identity from unstructured PDF text |
| **Multi-source API integration** | OpenAlex, Crossref, Semantic Scholar, Unpaywall — unified under a single interface |
| **Automated screening pipeline** | 5-stage funnel from raw search results to curated dataset |
| **Config-driven generalisability** | YAML configuration makes the pipeline reusable for any metal/reaction system |
| **Reproducibility engineering** | Pinned deps, JSON state persistence, resumable stages |
| **Browser automation** | Playwright-based institutional PDF access with manual override for CAPTCHA/login |
| **Human-in-the-loop design** | Automated extraction + explicit manual verification requirement |

This architecture is directly extensible to **LLM-assisted extraction** in a
future version (Stage 5 as a structured Claude/GPT-4o call rather than regex).

---

## Workflow Diagram

```
  config/<Metal>_H2_asymmetric_hydrogenation.yaml
         |
         v
+-----------------------------------------------------+
|  STAGE 1 -- Literature Search       run_search.bat  |
|  OpenAlex + Crossref + Semantic Scholar             |
|  -> keyword search -> citation chasing -> dedup     |
|  -> data/<prefix>/master_records.json               |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|  STAGE 2 -- Title/Abstract Screening run_screening  |
|  Metal regex + H2 keyword + exclusion filter        |
|  -> confidence score -> Tier 1 / Tier 2 / H2-strict |
|  -> data/<prefix>/strict_h2_records.json            |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|  STAGE 3 -- PDF Download            run_download.bat|
|  Mode A: API/OA (automated)                         |
|  Mode B: Browser / institutional (interactive)      |
|  -> papers/api_oa/  or  papers/manual_access/       |
+-------------------------+---------------------------+
                          |
                          v
+-----------------------------------------------------+
|  STAGE 4 -- Full-Text Screening     run_extraction  |
|  pypdf text extraction + evidence classification    |
|  -> A. Confirmed / B. Excluded / C. Uncertain       |
+-------------------------+---------------------------+
                          |   A. Confirmed only
                          v
+-----------------------------------------------------+
|  STAGE 5 -- Reaction Data Extraction run_extraction |
|  Regex-based: ee%, yield, H2 pressure, ligand...   |
|  [!] VERIFY ALL EXTRACTED VALUES MANUALLY           |
|  -> outputs/<prefix>_Reaction_Data.xlsx             |
+-----------------------------------------------------+
```

See [`docs/workflow_diagram.md`](docs/workflow_diagram.md) for the full annotated diagram.  
See [`docs/methodology.md`](docs/methodology.md) for algorithm details.

---

## Features

- **Multi-source search** — OpenAlex, Crossref, Semantic Scholar, citation chasing
- **Configurable screening** — YAML-defined keyword groups, regex patterns, exclusion terms
- **Dual PDF download** — open-access API mode + headful browser mode for institutional access
- **Full-text classification** — Confirmed / Excluded / Uncertain with evidence sentences
- **Structured data extraction** — ee%, yield, pressure, temperature, solvent, TON/TOF
- **Resumable pipeline** — each stage saves JSON state; interrupted runs continue from last success
- **Four metals ready** — Fe, Co, Mn, Ni configurations included; templates for new systems

---

## Quick Start

### 1. Clone and set up

```bat
git clone https://github.com/YOUR_USERNAME/Hydrogenation_Literature_Agent.git
cd Hydrogenation_Literature_Agent
setup.bat
```

`setup.bat` creates a `.venv`, installs dependencies, installs Playwright Chromium,
and creates the required output directories.

### 2. Configure API credentials (optional but recommended)

```bat
copy .env.example .env
rem Edit .env with your email and API keys — improves rate limits and OA coverage
```

### 3. Run the full pipeline (Fe, default)

```bat
run_search.bat
run_screening.bat
run_download.bat
run_extraction.bat
```

### 4. Switch to a different metal

```bat
run_search.bat      config\Co_H2_asymmetric_hydrogenation.yaml
run_screening.bat   config\Co_H2_asymmetric_hydrogenation.yaml
run_download.bat    config\Co_H2_asymmetric_hydrogenation.yaml
run_extraction.bat  config\Co_H2_asymmetric_hydrogenation.yaml
```

### 5. Institutional PDF access (browser mode)

```bat
run_download.bat config\Fe_H2_asymmetric_hydrogenation.yaml browser
```

A visible Chrome window opens. Complete any login / CAPTCHA / Cloudflare
challenges manually, then press **ENTER** in the terminal to continue.
The session is saved; subsequent runs reuse cookies.

> **Security note:** The session directory (`~/.cache/hla_browser_session/`)
> stores your institutional login cookies. Never commit or share this directory.
> The `.gitignore` excludes it automatically. Delete the directory to revoke
> saved sessions (e.g. when leaving an institution or sharing a machine).

### Mac / Linux

The `.bat` scripts are Windows-only. See [`docs/setup_instructions.md`](docs/setup_instructions.md)
for the equivalent `python -m modules.*` commands.

---

## Repository Structure

```
Hydrogenation_Literature_Agent/
├── README.md
├── requirements.txt
├── setup.bat                          ← first-time setup
├── run_search.bat                     ← Stage 1
├── run_screening.bat                  ← Stage 2
├── run_download.bat                   ← Stage 3 (API + browser modes)
├── run_extraction.bat                 ← Stages 4 + 5
│
├── config/
│   ├── base_config.yaml               ← shared defaults
│   ├── Fe_H2_asymmetric_hydrogenation.yaml
│   ├── Co_H2_asymmetric_hydrogenation.yaml
│   ├── Mn_H2_asymmetric_hydrogenation.yaml
│   └── Ni_H2_asymmetric_hydrogenation.yaml
│
├── modules/                           ← pipeline stage implementations
│   ├── literature_search.py           ← Stage 1
│   ├── title_abstract_screening.py    ← Stage 2
│   ├── pdf_download.py                ← Stage 3
│   ├── fulltext_screening.py          ← Stage 4
│   └── reaction_data_extraction.py    ← Stage 5
│
├── utils/                             ← shared helpers
│   ├── config_loader.py
│   ├── text_utils.py
│   ├── logger.py
│   ├── state_manager.py
│   └── excel_io.py
│
├── templates/
│   ├── config_template.yaml           ← template for new metals
│   └── extraction_schema_template.json
│
├── examples/
│   ├── example_input_config.yaml      ← annotated Fe config example
│   └── example_extraction_output.csv  ← sample Stage 5 output
│
├── docs/
│   ├── workflow_diagram.md            ← detailed ASCII pipeline diagram
│   ├── methodology.md                 ← algorithm documentation
│   ├── limitations.md                 ← known limitations
│   ├── setup_instructions.md          ← full setup guide incl. Mac/Linux
│   └── github_release_notes.md        ← release history
│
├── assets/                            ← screenshots (add your own)
│
├── outputs/                           ← Excel results (gitignored)
├── papers/                            ← downloaded PDFs (gitignored)
└── data/                              ← JSON pipeline state (gitignored)
```

---

## Supported Configurations

| Metal | Config file | Symbol | Key distinguishing queries |
|-------|-------------|--------|---------------------------|
| Iron | `Fe_H2_asymmetric_hydrogenation.yaml` | Fe | iron/Fe + asymmetric + H₂ |
| Cobalt | `Co_H2_asymmetric_hydrogenation.yaml` | Co | cobalt/Co + asymmetric + H₂ |
| Manganese | `Mn_H2_asymmetric_hydrogenation.yaml` | Mn | manganese/Mn + asymmetric + H₂ |
| Nickel | `Ni_H2_asymmetric_hydrogenation.yaml` | Ni | nickel/Ni + asymmetric + H₂ |

To add a new metal or reaction system, copy `templates/config_template.yaml`
and fill in the metal name, symbol, regex, and query groups. No code changes needed.

---

## Example Output

Stage 5 produces a structured Excel file and JSON. A representative CSV sample
is provided at [`examples/example_extraction_output.csv`](examples/example_extraction_output.csv).

| DOI | Metal | Ligand | ee% | Yield% | H₂ (bar) | Temp (°C) | Solvent |
|-----|-------|--------|-----|--------|----------|-----------|---------|
| 10.1021/jacs.5b00085 | FeCl₂ | (S)-BINAP | 90.0 | 85.0 | 50 | 25 | DCM |
| 10.1002/anie.201912024 | Fe(OAc)₂ | Josiphos SL-J002-1 | 95.2 | 92.0 | 40 | 20 | THF |
| 10.1039/D1SC01234A | FeBr₂ | (R,R)-Me-BPE | 88.5 | 78.0 | 60 | 30 | MeOH |

> All values are illustrative examples. Extracted values must be verified
> manually against source PDFs before scientific use.

---

## Limitations

- Stage 5 extraction is regex-based — **all extracted values must be manually verified**
- Windows `.bat` scripts only (Python modules are cross-platform)
- No OCR support for scanned PDFs
- Search coverage excludes databases not accessible via free APIs (SciFinder, Reaxys)
- No LLM/ML components in v1.0 — rule-based throughout

See [`docs/limitations.md`](docs/limitations.md) for full discussion.

---

## Copyright and PDF Access Disclaimer

This repository contains **no PDF files** and **no copyrighted journal content**.

The PDF download module retrieves only:
1. Documents available under open-access licences via public APIs, or
2. Documents accessed by the end user through their own valid institutional
   subscription, via interactive browser mode.

Users are responsible for ensuring their access and use complies with applicable
publisher terms of service, copyright law, and their institution's licensing
agreements. See `LICENSE` for full notice.

---

## Future Development Roadmap

- [ ] LLM-assisted extraction (Claude / GPT-4o) as an alternative to regex in Stage 5
- [ ] Shell scripts for Mac / Linux
- [ ] Docker container for environment reproducibility
- [ ] Unit test suite for screening and extraction modules
- [ ] JSON-LD and RDF output for linked data compatibility
- [ ] Web interface for configuration and result browsing
- [ ] Integration with ChemDraw / RDKit for substrate SMILES validation

---

## Dependencies

See [`requirements.txt`](requirements.txt).

| Package | Purpose |
|---------|---------|
| `openpyxl` | Excel read/write |
| `pypdf` | PDF text extraction |
| `requests` | HTTP requests to search APIs |
| `pandas` | DataFrame I/O for log files |
| `PyYAML` | YAML config parsing |
| `playwright` | Browser PDF download (optional) |

---

## License

MIT — see [`LICENSE`](LICENSE).

For PDF access rights, see the copyright notice section above and in `LICENSE`.
