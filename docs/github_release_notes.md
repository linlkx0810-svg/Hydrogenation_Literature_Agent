# Release Notes

## v1.0.0 — Initial Public Release (2025)

### Summary

First public release of the Hydrogenation Literature Agent. The pipeline was
developed to support a systematic literature survey of base-metal-catalyzed
asymmetric molecular-H₂ hydrogenation across iron (Fe), cobalt (Co), manganese
(Mn), and nickel (Ni) catalyst systems.

### What's included

- **5-stage pipeline**: search → screening → PDF download → full-text
  classification → reaction data extraction
- **4 metal configurations** out of the box: Fe, Co, Mn, Ni
- **Dual PDF download modes**: automated open-access (API) and interactive
  browser mode for institutional access
- **Config-driven design**: all search queries, screening parameters, and
  output naming are YAML-configurable without code changes
- **Resumable runs**: each stage writes its output to JSON; interrupted runs
  resume from the last successful stage

### Known limitations in v1.0.0

- Reaction data extraction (Stage 5) is regex-based; all extracted values
  require manual verification
- Windows-only `.bat` launchers (Python modules are cross-platform)
- No OCR support for scanned PDFs
- No LLM/ML components

### Configuration files included

| Metal | Config file |
|-------|-------------|
| Iron | `config/Fe_H2_asymmetric_hydrogenation.yaml` |
| Cobalt | `config/Co_H2_asymmetric_hydrogenation.yaml` |
| Manganese | `config/Mn_H2_asymmetric_hydrogenation.yaml` |
| Nickel | `config/Ni_H2_asymmetric_hydrogenation.yaml` |

### Verified run: Fe H₂ asymmetric hydrogenation

A complete pipeline run was performed for Fe-catalyzed asymmetric H₂
hydrogenation. The run covered all five stages and produced:
- A curated master literature list
- Title/abstract and full-text screening results
- Manually verified reaction data extraction for confirmed papers

Results are not included in this repository (see copyright/PDF notice in
`LICENSE`). The pipeline code and configuration are fully reproducible given
access to the same PDFs.

---

## Planned for v1.1.0

- Shell scripts for Mac/Linux users
- Optional LLM-assisted extraction (GPT-4o / Claude) as an alternative to
  regex in Stage 5
- Structured output in JSON-LD and CSV in addition to Excel
- Docker container for environment reproducibility
- Unit test suite for screening and extraction modules
