# Hydrogenation Literature Agent — Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                  HYDROGENATION LITERATURE AGENT v1                  │
│          Reusable for Fe / Co / Mn / Ni asymmetric H2 hydrog.       │
└─────────────────────────────────────────────────────────────────────┘

  config/<Metal>_H2_asymmetric_hydrogenation.yaml
         │
         │  load_config()  [utils/config_loader.py]
         ▼
┌────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — Literature Search          run_search.bat               │
│  modules/literature_search.py                                      │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  OpenAlex    │  │   Crossref   │  │   Semantic Scholar       │ │
│  │  keyword     │  │   keyword    │  │   keyword search         │ │
│  │  search      │  │   search     │  │   (API key optional)     │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬─────────────┘ │
│         └─────────────────┴──────────────────────┘               │
│                            │                                       │
│                    deduplicate() ──── fuzzy title match            │
│                            │                                       │
│              ┌─────────────┴──────────────┐                       │
│              │   Citation Chasing          │                       │
│              │   (OpenAlex backward +      │                       │
│              │    forward, top reviews +   │                       │
│              │    top primaries)           │                       │
│              └──────────────┬─────────────┘                       │
│                             │ deduplicate again                    │
│                             ▼                                      │
│          outputs/<prefix>_Master_Literature.xlsx                   │
│          data/<prefix>/master_records.json                         │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — Title/Abstract Screening   run_screening.bat            │
│  modules/title_abstract_screening.py                               │
│                                                                    │
│  For each record:                                                  │
│    ├─ Metal regex match          (metal-specific, from config)     │
│    ├─ Asymmetric/enantioselective keyword                          │
│    ├─ Hydrogenation keyword                                        │
│    ├─ Molecular H2 keyword                                         │
│    ├─ Experimental detail keyword                                  │
│    └─ Exclusion filter (transfer hydrog., silane, borane, DFT...)  │
│                                                                    │
│  → Confidence score (0–100)                                        │
│  → Inclusion decision + Tier 1/2 assignment                        │
│  → Strict H2-only filter                                           │
│                                                                    │
│  outputs/<prefix>_Title_Abstract_Screened.xlsx                     │
│  outputs/<prefix>_Strict_H2_Only.xlsx          ◄── feeds Stage 3   │
│  data/<prefix>/strict_h2_records.json                              │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — PDF Download               run_download.bat             │
│  modules/pdf_download.py                                           │
│                                                                    │
│  ┌──────────────────────────────────┐                              │
│  │  Mode A: API/OA (automated)      │                              │
│  │  • OpenAlex OA locations         │                              │
│  │  • Unpaywall (requires email)    │  → papers/api_oa/            │
│  │  • Crossref PDF links            │                              │
│  └──────────────────────────────────┘                              │
│                                                                    │
│  ┌──────────────────────────────────┐                              │
│  │  Mode B: Browser (institutional) │                              │
│  │  • Headful system Chrome         │  → papers/manual_access/     │
│  │  • Persistent session cookies    │                              │
│  │  • Pauses for: Cloudflare,       │                              │
│  │    Anubis, CAPTCHA, login walls  │                              │
│  └──────────────────────────────────┘                              │
│                                                                    │
│  outputs/<prefix>_Download_Log.xlsx                                │
│  data/<prefix>/strict_h2_records.json  (updated with pdf_path)     │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STAGE 4 — Full-Text Screening        run_extraction.bat (Step 1)  │
│  modules/fulltext_screening.py                                     │
│                                                                    │
│  For each record with a PDF:                                       │
│    ├─ Extract all page texts (pypdf)                               │
│    ├─ Search for metal evidence, H2 evidence, ee%, scope           │
│    ├─ Apply universal + metal-specific exclusion patterns          │
│    └─ Classify: A. Confirmed / B. Excluded / C. Uncertain          │
│                                                                    │
│  outputs/<prefix>_Fulltext_Screening.xlsx                          │
│    sheets: fulltext_screening, A_confirmed, B_excluded, C_uncertain│
│  data/<prefix>/fulltext_screening.json                             │
└─────────────────────────┬──────────────────────────────────────────┘
                          │  A. Confirmed papers only
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STAGE 5 — Reaction Data Extraction   run_extraction.bat (Step 2)  │
│  modules/reaction_data_extraction.py                               │
│                                                                    │
│  From confirmed PDFs, extract:                                     │
│    Metal catalyst, Ligand, Substrate class,                        │
│    ee%, Yield%, H2 pressure, Temperature,                          │
│    Solvent, Reaction time, TON, TOF                                │
│                                                                    │
│  ⚠  Automated extraction — ALWAYS verify values manually.         │
│                                                                    │
│  outputs/<prefix>_Reaction_Data.xlsx                               │
│  data/<prefix>/reaction_data.json                                  │
└────────────────────────────────────────────────────────────────────┘

                    PROJECT_STATE.json
                    ┌─────────────────┐
                    │  run_id         │ ← tracks each run
                    │  per stage:     │
                    │    status       │ ← running/done/failed
                    │    started      │
                    │    finished     │
                    │    stats        │
                    └─────────────────┘
                    Interrupted runs can be resumed by re-running
                    from the failed stage.
```

## Metal Configuration Summary

| Metal | Config file | Symbol | Key query anchor |
|-------|------------|--------|-----------------|
| Iron | `Fe_H2_asymmetric_hydrogenation.yaml` | Fe | iron/Fe |
| Cobalt | `Co_H2_asymmetric_hydrogenation.yaml` | Co | cobalt/Co |
| Manganese | `Mn_H2_asymmetric_hydrogenation.yaml` | Mn | manganese/Mn |
| Nickel | `Ni_H2_asymmetric_hydrogenation.yaml` | Ni | nickel/Ni |

## Data Flow Summary

```
Stage 1 → data/<prefix>/master_records.json
Stage 2 → data/<prefix>/strict_h2_records.json
Stage 3 → papers/{api_oa,manual_access}/*.pdf
Stage 4 → data/<prefix>/fulltext_screening.json
Stage 5 → data/<prefix>/reaction_data.json
           outputs/<prefix>_Reaction_Data.xlsx  ← final dataset
```
