# Release Notes

## v1.0.0 — Initial Public Release (2026)

### Summary

First public release of the Hydrogenation Literature Agent. The pipeline was
developed to support a systematic literature survey of base-metal-catalyzed
asymmetric molecular-H₂ hydrogenation across iron (Fe), cobalt (Co), manganese
(Mn), and nickel (Ni) catalyst systems.

### What's included

- **5-stage pipeline**: search → screening → PDF download → full-text
  classification → reaction data extraction
- **4 metal configurations** out of the box: Fe, Co, Mn, Ni
- **Dual PDF download modes**: automated API/OA link resolution and interactive
  browser mode for institutional access
- **Config-driven design**: all search queries, screening parameters, and
  output naming are YAML-configurable without code changes
- **Rerunnable stages**: each stage writes its output to JSON; failed stages can
  be rerun from the previous stage's saved JSON output

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

### Validation status

This release was checked for repository structure, documentation consistency,
privacy safeguards, and Git-tracking safety. It does not include a real
literature search, PDF download, or manually verified reaction-data extraction.

---

## Planned for v1.1.0

- Shell scripts for Mac/Linux users
- Optional LLM-assisted extraction (GPT-4o / Claude) as an alternative to
  regex in Stage 5
- Structured output in JSON-LD and CSV in addition to Excel
- Docker container for environment reproducibility
- Unit test suite for screening and extraction modules
