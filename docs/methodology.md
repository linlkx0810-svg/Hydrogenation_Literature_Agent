# Methodology — Hydrogenation Literature Agent

## Overview

The Hydrogenation Literature Agent implements a five-stage, reproducible pipeline
for systematic literature mapping of base-metal-catalyzed asymmetric molecular-H₂
hydrogenation. Each stage is independently resumable, reproducible from its JSON
output, and configurable via YAML.

---

## Stage 1 — Literature Search

**Module:** `modules/literature_search.py`  
**Trigger:** `run_search.bat [config]`

### Data sources

| Source | Access mode | Rate limit |
|--------|-------------|------------|
| OpenAlex | Public API (polite pool with email) | ~100 req/s |
| Crossref | Public API | ~50 req/s |
| Semantic Scholar | Public API (key optional) | 1 req/s (no key), ~10 req/s (with key) |

### Search strategy

Queries are grouped by semantic intent (see `config/*.yaml`, `query_groups`):

- **Group A** — Direct metal + asymmetric hydrogenation phrases
- **Group B** — Enantioselective/chiral wording variants
- **Group C** — Molecular H₂ restriction (excludes transfer hydrogenation)
- **Group D** — Review papers (used as seeds for citation chasing)

### Citation chasing

After initial keyword retrieval, the pipeline:
1. Selects the top-N review papers by citation count (configurable `max_reviews`)
2. Selects the top-N primary papers by citation count (`max_primary`)
3. Retrieves all backward (reference) and forward (citing) links for each
4. Merges and deduplicates using fuzzy title matching (Levenshtein ratio ≥ `title_threshold`)

### Output

- `data/<prefix>/master_records.json` — machine-readable, one record per paper
- `outputs/<prefix>_Master_Literature.xlsx` — human-reviewable Excel

---

## Stage 2 — Title/Abstract Screening

**Module:** `modules/title_abstract_screening.py`  
**Trigger:** `run_screening.bat [config]`

### Scoring

Each record receives a confidence score (0–100) based on keyword presence in
title + abstract:

| Signal | Weight |
|--------|--------|
| Metal match (configurable regex) | High |
| Asymmetric / enantioselective | High |
| Hydrogenation / hydrogenase | Medium |
| Molecular H₂ / H2 / dihydrogen | High |
| Experimental evidence keywords | Medium |
| Exclusion terms (transfer hydrogenation, DFT, silane...) | Negative |

### Output tiers

- **Tier 1** — High confidence (score ≥ threshold), molecular H₂ confirmed
- **Tier 2** — Plausible, needs full-text verification
- **H₂-strict filter** — Tier 1 records with explicit H₂ evidence → fed to Stage 3

---

## Stage 3 — PDF Download

**Module:** `modules/pdf_download.py`  
**Trigger:** `run_download.bat [config] [browser]`

### Mode A — API/OA (automated)

Attempts to retrieve PDFs from:
1. OpenAlex open-access location field
2. Unpaywall API (requires `UNPAYWALL_EMAIL`)
3. Crossref licence/link fields

PDFs are validated (minimum byte size from `base_config.yaml`) and saved to
`papers/api_oa/`.

### Mode B — Browser (institutional)

Uses Playwright (headful Chromium) to navigate to each paper's DOI URL.
The script pauses on:
- Cloudflare / Anubis / CAPTCHA challenges
- Login walls

The user completes authentication manually, then presses ENTER to continue.
Browser session (cookies) is persisted across runs. PDFs are saved to
`papers/manual_access/`.

---

## Stage 4 — Full-Text Screening

**Module:** `modules/fulltext_screening.py`  
**Trigger:** `run_extraction.bat [config]` (first step)

PDF text is extracted via `pypdf`. For each page, the module applies:

- Metal presence patterns (from config regex)
- H₂ evidence patterns
- ee% presence
- Universal and metal-specific exclusion patterns

Each paper is classified as:
- **A. Confirmed** — strong evidence of target reaction
- **B. Excluded** — exclusion pattern matched
- **C. Uncertain** — insufficient evidence; recommend manual review

Only Confirmed (A) papers proceed to Stage 5.

---

## Stage 5 — Reaction Data Extraction

**Module:** `modules/reaction_data_extraction.py`  
**Trigger:** `run_extraction.bat [config]` (second step)

Structured data is extracted from confirmed PDFs using regex-based pattern
matching on page text. Fields extracted:

| Field | Example |
|-------|---------|
| Metal_catalyst | FeCl₂ |
| Ligand | (S)-BINAP |
| Substrate_class | aryl ketone |
| ee_percent | 92.5 |
| yield_percent | 88.0 |
| H2_pressure_bar | 50 |
| Temperature_C | 25 |
| Solvent | DCM |
| Reaction_time_h | 24 |
| TON / TOF | 200 / 11.1 |

> **Important:** Automated extraction is imprecise. All values **must** be
> manually verified against the source PDF before scientific use.

---

## Reproducibility

| Factor | Approach |
|--------|----------|
| Dependencies | Pinned in `requirements.txt` (major+minor version bounds) |
| Search state | Saved to `data/<prefix>/master_records.json` after Stage 1 |
| Screening state | Saved to `data/<prefix>/strict_h2_records.json` after Stage 2 |
| Run progress | `PROJECT_STATE.json` (gitignored — local only) |
| Random seed | Not applicable — no ML components |

Interrupted runs can be resumed by re-running the failed stage's BAT file.
The pipeline reads from the last successful stage's JSON output.
