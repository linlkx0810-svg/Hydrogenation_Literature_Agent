# Known Limitations

## 1. Search coverage is not exhaustive

The pipeline queries OpenAlex, Crossref, and Semantic Scholar. Papers indexed
only in other databases (Web of Science, SciFinder, Reaxys, CAS) will be missed.
Citation chasing mitigates this but does not eliminate the gap.

**Mitigation:** Use broad query groups (Group D, review papers) and manual
seed papers to extend coverage into less-indexed sources.

---

## 2. Title/abstract screening can produce false positives and false negatives

The rule-based confidence scorer is calibrated for molecular H₂ reactions but
will occasionally:
- Include transfer-hydrogenation papers if the abstract omits the H-donor
- Exclude valid papers with unusual or abbreviated terminology

**Mitigation:** Full-text screening (Stage 4) catches false positives from
Stage 2. For Tier 2 papers, manual review is recommended.

---

## 3. Open-access PDF coverage is incomplete

Stage 3 API mode can only retrieve papers with valid open-access links.
Institutional access (browser mode) extends coverage but requires manual
interaction and a valid subscription.

**Mitigation:** Browser mode supports 1-based single-row testing
(`run_download.bat [config] browser [row]`) to verify access before processing
all papers.

---

## 4. Reaction data extraction is regex-based and imprecise

Stage 5 uses pattern matching on raw PDF text. Known failure modes:
- Numerical values in figure captions extracted instead of table data
- Superscripts / subscripts corrupted by pypdf text extraction
- Multi-page tables split across extraction boundaries
- Non-standard ee% reporting (e.g., "94:6 er" instead of "88% ee")

**Mitigation:** Every extracted value **must** be manually verified against
the source PDF before use in any scientific publication or analysis.

---

## 5. Windows-only batch scripts

The provided `.bat` launch scripts require Windows. The Python modules are
platform-independent; Mac/Linux users can invoke the modules directly:

```bash
python -m modules.literature_search --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.title_abstract_screening --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.pdf_download --config config/Fe_H2_asymmetric_hydrogenation.yaml --mode api
python -m modules.fulltext_screening --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.reaction_data_extraction --config config/Fe_H2_asymmetric_hydrogenation.yaml
```

---

## 6. API rate limits

Without API keys/emails, Semantic Scholar and Unpaywall impose strict rate
limits that can significantly slow Stage 1 and Stage 3. See `.env.example`
for the relevant environment variables.

---

## 7. pypdf extraction quality varies by PDF type

- Native (born-digital) PDFs: high-quality text extraction
- Scanned PDFs without OCR layer: no text extracted — paper will be
  classified as C. Uncertain in Stage 4
- PDFs with publisher DRM: may fail to extract

**Mitigation:** Scanned PDFs require OCR preprocessing (not included in this
pipeline) before Stage 4 will process them.

---

## 8. No ML / LLM components — rule-based only

All scoring, classification, and extraction in this pipeline is rule-based
(keyword matching, regex, fuzzy string similarity). This is a deliberate
design choice for transparency and reproducibility, but it means:
- The pipeline cannot generalise to terminology it has not been configured for
- Extending to new reaction types or languages requires manual configuration
