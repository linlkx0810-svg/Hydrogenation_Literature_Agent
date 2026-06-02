"""
modules/fulltext_screening.py
──────────────────────────────
Stage 4: Full-text PDF screening.

Reads downloaded PDFs, extracts text, applies metal-specific
classification rules. Outputs classified Excel with sheets:
  A_confirmed, B_excluded, C_uncertain.

Entry point
-----------
    from modules.fulltext_screening import run
    stats = run(cfg)
"""

import argparse
import json
import re
from pathlib import Path

from utils import load_config, log_event, ProjectState, make_run_id
from utils.text_utils import load_json, normalize_doi, timestamp
from utils.excel_io import export_records_xlsx

try:
    from pypdf import PdfReader
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

SCREENING_COLUMNS = [
    "Classification", "Decision reason",
    "Title", "Authors", "Year", "Journal", "DOI", "URL",
    "Original tier", "PDF access status", "PDF source", "PDF URL", "PDF path",
    "Metal catalyst used", "Hydrogen source identified",
    "Asymmetric / enantioselective evidence", "ee value found",
    "Experimental substrate scope", "Evidence sentence",
    "Page number", "Table / Scheme reference",
    "Matched exclusion keywords", "Notes",
]

# Universal patterns
ASYMMETRIC_RE = re.compile(r"\b(?:asymmetric|enantioselective|enantioenriched|enantioselectivity|chiral)\b", re.I)
H2_RE         = re.compile(r"\b(?:molecular\s+hydrogen|hydrogen\s+gas|h(?:2|₂))\b", re.I)
SCOPE_RE      = re.compile(r"\b(?:substrate\s+scope|scope\s+of\s+substrates|various\s+substrates|"
                            r"substrates?\s+were|examples?\s+were|table\s+\d+)\b", re.I)
TABLE_RE      = re.compile(r"\b(?:table|scheme|figure|entry)\s+[A-Za-z0-9.-]+\b", re.I)
REVIEW_RE     = re.compile(r"\b(?:review|overview|perspective|chapter)\b", re.I)
NON_PRIMARY_RE= re.compile(r"\b(?:machine\s+learning|high\s+throughput\s+experimentation|"
                            r"review|overview|perspective|chapter)\b", re.I)
EE_PATTERNS   = [
    re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%\s*ee\b", re.I),
    re.compile(r"\bee\s*(?:of|=|:|up\s+to)?\s*>?\s*\d{1,3}(?:\.\d+)?\s*%", re.I),
    re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%\s*(?:enantioselectivity|enantiomeric\s+excess)\b", re.I),
]

UNIVERSAL_EXCLUSION = [
    ("transfer hydrogenation", re.compile(r"\b(?:asymmetric\s+)?transfer\s+hydrogenation\b", re.I)),
    ("ATH",                    re.compile(r"\bath\b", re.I)),
    ("hydrosilylation",        re.compile(r"\bhydrosilylation\b", re.I)),
    ("silane reagent",         re.compile(r"\b(?:silane|hsir3|phsih3|pmhs|tmds)\b", re.I)),
    ("hydroboration",          re.compile(r"\bhydroboration\b", re.I)),
    ("borane reagent",         re.compile(r"\b(?:ammonia\s+borane|borane|hbpin|hbcat|9[-\s]?bbn|catecholborane|bh3)\b", re.I)),
    ("NaBH4/KBH4/LiAlH4",     re.compile(r"\b(?:nabh4|kbh4|lialh4)\b", re.I)),
    ("formic acid",            re.compile(r"\b(?:formic\s+acid|hcooh)\b", re.I)),
    ("isopropanol",            re.compile(r"\b(?:isopropanol|i[-\s]?proh)\b", re.I)),
    ("Hantzsch ester",         re.compile(r"\bhantzsch\s+ester\b", re.I)),
    ("photocatalysis",         re.compile(r"\bphotocatal", re.I)),
    ("electrocatalysis",       re.compile(r"\belectrocatal", re.I)),
    ("borrowing hydrogen",     re.compile(r"\bborrowing\s+hydrogen\b", re.I)),
    ("DFT-only",               re.compile(r"\b(?:density\s+functional\s+theory|dft|first[-\s]principles?|computational\s+study)\b", re.I)),
]


# ── PDF text extraction ───────────────────────────────────────────────────────

def _read_pdf(pdf_path: Path) -> list[str]:
    if not _PDF_AVAILABLE:
        raise ImportError("pypdf not installed. Run: pip install pypdf")
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", compact) if p.strip()]


def _find_context(pages: list[str], patterns: list[re.Pattern]) -> tuple[str, str, str]:
    for page_num, text in enumerate(pages, 1):
        for sentence in _sentences(text):
            if all(p.search(sentence) for p in patterns):
                table = TABLE_RE.search(sentence)
                return sentence[:800], str(page_num), table.group(0) if table else ""
    for page_num, text in enumerate(pages, 1):
        if all(p.search(text) for p in patterns):
            for sentence in _sentences(text):
                if any(p.search(sentence) for p in patterns):
                    table = TABLE_RE.search(sentence) or TABLE_RE.search(text)
                    return sentence[:800], str(page_num), table.group(0) if table else ""
    return "", "", ""


def _first_match(pages: list[str], pattern: re.Pattern) -> tuple[str, str]:
    for page_num, text in enumerate(pages, 1):
        m = pattern.search(text)
        if m:
            return m.group(0), str(page_num)
    return "", ""


def _first_ee(pages: list[str]) -> tuple[str, str]:
    for page_num, text in enumerate(pages, 1):
        for p in EE_PATTERNS:
            m = p.search(text)
            if m:
                return m.group(0), str(page_num)
    return "", ""


# ── Classification ────────────────────────────────────────────────────────────

def classify_fulltext(record: dict, cfg: dict,
                      access_status: str, pdf_source: str,
                      pdf_url: str, pdf_path: str,
                      project_root: Path) -> dict:
    metal_re       = re.compile(cfg["metal"]["regex"], re.I)
    metal_name     = cfg["metal"]["name"]
    other_metal_pattern = cfg.get("screening", {}).get("other_metal_regex", "")
    other_metal_re = None
    if other_metal_pattern:
        try:
            other_metal_re = re.compile(" ".join(other_metal_pattern.split()), re.I)
        except re.error:
            pass

    base = {
        "Title": record.get("Title", ""),
        "Authors": record.get("Authors", ""),
        "Year": record.get("Year", ""),
        "Journal": record.get("Journal", ""),
        "DOI": record.get("DOI", ""),
        "URL": record.get("URL", ""),
        "Original tier": record.get("Original tier", ""),
        "PDF access status": access_status,
        "PDF source": pdf_source,
        "PDF URL": pdf_url,
        "PDF path": pdf_path,
    }

    if not pdf_path:
        return {
            "Classification": "C. Uncertain", "Decision reason": "No accessible PDF.",
            **base,
            "Metal catalyst used": "Not verified",
            "Hydrogen source identified": "Not verified",
            "Asymmetric / enantioselective evidence": "Not verified",
            "ee value found": "Not verified",
            "Experimental substrate scope": "Not verified",
            "Evidence sentence": "No accessible PDF available for full-text screening.",
            "Page number": "Not available",
            "Table / Scheme reference": "Not available",
            "Matched exclusion keywords": "Not verified",
            "Notes": "No paywall bypass attempted.",
        }

    full_path = Path(pdf_path) if Path(pdf_path).is_absolute() else project_root / pdf_path
    try:
        pages = _read_pdf(full_path)
    except Exception as exc:
        return {
            "Classification": "C. Uncertain",
            "Decision reason": "PDF text extraction failed.",
            **base,
            "Metal catalyst used": "Not verified",
            "Hydrogen source identified": "Not verified",
            "Asymmetric / enantioselective evidence": "Not verified",
            "ee value found": "Not verified",
            "Experimental substrate scope": "Not verified",
            "Evidence sentence": str(exc),
            "Page number": "Not available",
            "Table / Scheme reference": "Not available",
            "Matched exclusion keywords": "Not verified",
            "Notes": "Manual review required.",
        }

    combined = "\n".join(pages)
    exclusions = [label for label, pattern in UNIVERSAL_EXCLUSION if pattern.search(combined)]
    title = record.get("Title", "")

    title_metal      = bool(metal_re.search(title))
    title_asymmetric = bool(ASYMMETRIC_RE.search(title))
    title_h2         = bool(re.search(r"\bhydrogenation\b", title, re.I))
    title_other      = other_metal_re.search(title) if other_metal_re else None
    title_exclusions = [lbl for lbl, pat in UNIVERSAL_EXCLUSION if pat.search(title)]

    metal_match = metal_re.search(title)
    metal_str   = f"{metal_match.group(0)} (title evidence)" if metal_match else ""
    metal_page  = "Title" if metal_str else ""

    hydrogen, hydrogen_page  = _first_match(pages, H2_RE)
    asymmetric, asym_page    = _first_match(pages, ASYMMETRIC_RE)
    ee, ee_page              = _first_ee(pages)
    scope, scope_page        = _first_match(pages, SCOPE_RE)
    evidence, ev_page, table = _find_context(pages, [metal_re, H2_RE, ASYMMETRIC_RE])
    if not evidence:
        evidence, ev_page, table = _find_context(pages, [H2_RE])

    ev_other = other_metal_re.search(evidence or "") if other_metal_re else None

    if title_exclusions:
        classification = "B. Excluded"
        reason = f"Title: prohibited system ({', '.join(title_exclusions)})"
    elif title_other and not title_metal:
        classification = "B. Excluded"
        reason = f"Title identifies non-{metal_name} catalyst: {title_other.group(0)}"
    elif not title_metal and ev_other:
        classification = "B. Excluded"
        reason = f"H2 evidence sentence identifies non-{metal_name} catalyst: {ev_other.group(0)}"
    elif title_metal and title_h2 and not title_asymmetric:
        classification = "B. Excluded"
        reason = f"Title identifies {metal_name}-catalysed hydrogenation but not asymmetric."
    elif NON_PRIMARY_RE.search(title):
        classification = "B. Excluded"
        reason = "Non-primary record (review/ML/HTE)."
    elif title_metal and title_asymmetric and title_h2 and hydrogen and ee and scope:
        classification = "A. Confirmed"
        reason = (f"Full text explicitly supports {metal_name} catalyst, molecular H2, "
                  f"asymmetric reaction, ee value, and experimental substrate scope.")
    elif REVIEW_RE.search(title):
        classification = "B. Excluded"
        reason = "Review or chapter."
    else:
        classification = "C. Uncertain"
        missing = []
        if not title_metal:
            missing.append(f"{metal_name} catalyst")
        if not hydrogen:
            missing.append("molecular H2")
        if not title_asymmetric:
            missing.append("asymmetric reaction")
        if not ee:
            missing.append("ee value")
        if not scope:
            missing.append("substrate scope")
        reason = f"Full-text evidence incomplete: {', '.join(missing)}"

    pages_used = ", ".join(dict.fromkeys(filter(None, [ev_page, hydrogen_page, asym_page, ee_page, scope_page])))
    return {
        "Classification": classification,
        "Decision reason": reason,
        **base,
        "Metal catalyst used":                    metal_str or "Not found",
        "Hydrogen source identified":             hydrogen or "Not found",
        "Asymmetric / enantioselective evidence": asymmetric or "Not found",
        "ee value found":                         ee or "Not found",
        "Experimental substrate scope":           scope or "Not found",
        "Evidence sentence":                      evidence or "No single evidence sentence found.",
        "Page number":                            pages_used or "Not found",
        "Table / Scheme reference":               table or "Not found",
        "Matched exclusion keywords":             "; ".join(exclusions) or "None",
        "Notes": "Machine-assisted screen. Manually verify before use.",
    }


# ── Main run function ─────────────────────────────────────────────────────────

def run(cfg: dict) -> dict:
    """Execute Stage 4: full-text screening."""
    prefix       = cfg["output"]["prefix"]
    outputs_dir  = Path(cfg["output"]["outputs_dir"])
    logs_dir     = Path(cfg["output"]["logs_dir"])
    data_dir     = Path(cfg["output"]["data_subdir"])
    fulltext_excel = outputs_dir / cfg["output"]["fulltext_excel"]
    project_root = Path(cfg["_project_root"])

    records_path = data_dir / "strict_h2_records.json"
    if not records_path.exists():
        raise FileNotFoundError(f"Stage 2 output not found: {records_path}")
    records = load_json(records_path, [])

    results = []
    for idx, record in enumerate(records, 1):
        pdf_path   = record.get("pdf_path", "") or record.get("PDF_path", "") or ""
        access     = record.get("PDF access status", "")
        pdf_source = record.get("PDF source", "")
        pdf_url    = record.get("PDF URL", "")

        classified = classify_fulltext(
            record, cfg, access, pdf_source, pdf_url, pdf_path, project_root
        )
        results.append(classified)
        print(f"  [{idx}/{len(records)}] {record.get('DOI','')[:40]:<42} {classified['Classification']}")

    confirmed  = [r for r in results if r["Classification"] == "A. Confirmed"]
    excluded   = [r for r in results if r["Classification"] == "B. Excluded"]
    uncertain  = [r for r in results if r["Classification"] == "C. Uncertain"]

    export_records_xlsx(
        results, SCREENING_COLUMNS, fulltext_excel,
        sheet_name="fulltext_screening",
        extra_sheets={
            "A_confirmed": confirmed,
            "B_excluded":  excluded,
            "C_uncertain": uncertain,
        },
    )
    (data_dir / "fulltext_screening.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log_event(logs_dir / "pipeline.jsonl", "fulltext_screening_complete",
              prefix=prefix, total=len(results),
              confirmed=len(confirmed), excluded=len(excluded), uncertain=len(uncertain))
    print(f"[fulltext] {prefix}: confirmed={len(confirmed)}, "
          f"excluded={len(excluded)}, uncertain={len(uncertain)}")
    print(f"  Output: {fulltext_excel}")

    return {
        "total":     len(results),
        "confirmed": len(confirmed),
        "excluded":  len(excluded),
        "uncertain": len(uncertain),
        "output_excel": str(fulltext_excel),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: Full-text screening")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg    = load_config(args.config)
    state  = ProjectState()
    run_id = make_run_id(cfg["project"]["name"])
    state.start_stage(run_id, "fulltext_screening", config=args.config)
    try:
        stats = run(cfg)
        state.finish_stage(run_id, "fulltext_screening", **stats)
        print(state.summary(run_id))
    except Exception as exc:
        state.fail_stage(run_id, "fulltext_screening", str(exc))
        raise


if __name__ == "__main__":
    main()
