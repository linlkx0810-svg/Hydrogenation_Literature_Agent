"""
modules/reaction_data_extraction.py
─────────────────────────────────────
Stage 5: Reaction data extraction from confirmed PDFs.

Extracts structured catalytic data from A. Confirmed papers:
  metal catalyst, ligand, substrate, ee%, yield%, H2 pressure,
  temperature, solvent, TON/TOF, reaction time.

Entry point
-----------
    from modules.reaction_data_extraction import run
    stats = run(cfg)
"""

import argparse
import json
import re
from pathlib import Path

from utils import load_config, log_event, ProjectState, make_run_id
from utils.text_utils import load_json, timestamp
from utils.excel_io import export_records_xlsx

try:
    from pypdf import PdfReader
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# ── Extraction regex patterns ─────────────────────────────────────────────────

EE_RE      = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*ee", re.I)
YIELD_RE   = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*yield", re.I)
H2_BAR_RE  = re.compile(r"(\d{1,4}(?:\.\d+)?)\s*(?:bar|atm|psi|MPa|kPa)\s*(?:H2|hydrogen)?", re.I)
TEMP_RE    = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*°?C\b", re.I)
TIME_RE    = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*h(?:ours?|r)?\b", re.I)
TON_RE     = re.compile(r"TON\s*(?:of|=|:)?\s*(\d+)", re.I)
TOF_RE     = re.compile(r"TOF\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*h\^?-?1", re.I)

SOLVENT_WORDS = [
    "thf", "dichloromethane", "dcm", "methanol", "ethanol", "toluene",
    "acetonitrile", "dmf", "dmso", "hexane", "heptane", "isopropanol",
    "ethyl acetate", "diethyl ether", "chloroform", "dioxane",
]
SOLVENT_RE = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in SOLVENT_WORDS) + r")\b", re.I)

LIGAND_WORDS = [
    "bisphosphine", "diphosphine", "phosphine", "binap", "josiphos",
    "trost", "xyl-binap", "p-nh-p", "triphos", "dppp", "dppe", "dppm",
    "chiraphos", "biphep", "segphos", "synphos", "mandyphos",
    "chiral ligand", "atrop", "ferrocene",
]
LIGAND_RE = re.compile(r"\b(?:" + "|".join(re.escape(l) for l in LIGAND_WORDS) + r")\b", re.I)

SUBSTRATE_RE = re.compile(
    r"\b(?:ketone|imine|alkene|olefin|aldehyde|ester|acid|amide|lactone|"
    r"enamine|enamide|dehydroamino|acetophenone|aryl ketone)\b", re.I
)


# ── PDF extraction helpers ────────────────────────────────────────────────────

def _read_pdf(path: Path) -> str:
    if not _PDF_AVAILABLE:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _first(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return m.group(1) if m else ""


def _all_matches(pattern: re.Pattern, text: str) -> list[str]:
    return pattern.findall(text)


def _best_ee(text: str) -> str:
    """Return the highest ee% found in text."""
    matches = [float(v) for v in EE_RE.findall(text) if v]
    return f"{max(matches):.1f}" if matches else ""


def _best_yield(text: str) -> str:
    matches = [float(v) for v in YIELD_RE.findall(text) if v]
    return f"{max(matches):.1f}" if matches else ""


def _extract_solvent(text: str) -> str:
    m = SOLVENT_RE.search(text)
    return m.group(0) if m else ""


def _extract_ligand(text: str, metal_aliases: list[str]) -> str:
    m = LIGAND_RE.search(text)
    return m.group(0) if m else ""


def _extract_substrate(text: str) -> str:
    m = SUBSTRATE_RE.search(text)
    return m.group(0) if m else ""


def extract_record(record: dict, cfg: dict, project_root: Path) -> dict:
    """Extract reaction data from a single confirmed-paper record."""
    doi      = record.get("DOI", "")
    title    = record.get("Title", "")
    authors  = record.get("Authors", "")
    year     = record.get("Year", "")
    journal  = record.get("Journal", "")
    pdf_path = record.get("PDF path", "") or record.get("PDF_path", "") or ""

    base = {
        "DOI":     doi,
        "Title":   title,
        "Authors": authors,
        "Year":    year,
        "Journal": journal,
        "PDF_path": pdf_path,
    }

    if not pdf_path:
        return {**base,
                "Metal_catalyst": "", "Ligand": "", "Substrate_class": "",
                "Substrate_example": "", "Product": "",
                "ee_percent": "", "yield_percent": "", "H2_pressure_bar": "",
                "Temperature_C": "", "Solvent": "", "Reaction_time_h": "",
                "TON": "", "TOF": "", "Evidence_sentence": "",
                "Page_number": "", "Notes": "No PDF available for extraction."}

    full_path = Path(pdf_path) if Path(pdf_path).is_absolute() else project_root / pdf_path
    text = _read_pdf(full_path)

    if not text.strip():
        return {**base,
                "Metal_catalyst": "", "Ligand": "", "Substrate_class": "",
                "Substrate_example": "", "Product": "",
                "ee_percent": "", "yield_percent": "", "H2_pressure_bar": "",
                "Temperature_C": "", "Solvent": "", "Reaction_time_h": "",
                "TON": "", "TOF": "", "Evidence_sentence": "",
                "Page_number": "",
                "Notes": "PDF text extraction returned empty content."}

    metal_re = re.compile(cfg["metal"]["regex"], re.I)
    m_metal  = metal_re.search(text)
    metal_str = m_metal.group(0) if m_metal else cfg["metal"]["name"]

    aliases = cfg["metal"].get("aliases", [])
    ligand  = _extract_ligand(text, aliases)

    # Find sentence with best evidence
    evidence_sentence = ""
    h2_re = re.compile(r"\b(?:molecular\s+hydrogen|hydrogen\s+gas|h(?:2|₂))\b", re.I)
    ee_re_pattern = re.compile(r"\d{1,3}(?:\.\d+)?\s*%\s*ee", re.I)
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        if metal_re.search(sent) and h2_re.search(sent) and ee_re_pattern.search(sent):
            evidence_sentence = sent[:600]
            break
    if not evidence_sentence:
        m = ee_re_pattern.search(text)
        if m:
            start = max(0, m.start() - 100)
            evidence_sentence = text[start: m.end() + 200].replace("\n", " ").strip()[:600]

    return {
        **base,
        "Metal_catalyst":    metal_str,
        "Ligand":            ligand,
        "Substrate_class":   _extract_substrate(text),
        "Substrate_example": "",   # Requires manual curation
        "Product":           "",   # Requires manual curation
        "ee_percent":        _best_ee(text),
        "yield_percent":     _best_yield(text),
        "H2_pressure_bar":   _first(H2_BAR_RE, text),
        "Temperature_C":     _first(TEMP_RE, text),
        "Solvent":           _extract_solvent(text),
        "Reaction_time_h":   _first(TIME_RE, text),
        "TON":               _first(TON_RE, text),
        "TOF":               _first(TOF_RE, text),
        "Evidence_sentence": evidence_sentence,
        "Page_number":       "",
        "Notes": "Automated extraction — verify all values manually before use.",
    }


# ── Main run function ─────────────────────────────────────────────────────────

def run(cfg: dict) -> dict:
    """Execute Stage 5: reaction data extraction from confirmed PDFs."""
    prefix        = cfg["output"]["prefix"]
    outputs_dir   = Path(cfg["output"]["outputs_dir"])
    logs_dir      = Path(cfg["output"]["logs_dir"])
    data_dir      = Path(cfg["output"]["data_subdir"])
    extraction_excel = outputs_dir / cfg["output"]["extraction_excel"]
    project_root  = Path(cfg["_project_root"])
    columns       = cfg.get("extraction", {}).get("columns", [])

    fulltext_path = data_dir / "fulltext_screening.json"
    if not fulltext_path.exists():
        raise FileNotFoundError(f"Stage 4 output not found: {fulltext_path}")
    all_records = load_json(fulltext_path, [])

    confirmed = [r for r in all_records if r.get("Classification") == "A. Confirmed"]
    print(f"[extraction] {prefix} — {len(confirmed)} confirmed records to process")

    extracted = []
    for idx, record in enumerate(confirmed, 1):
        result = extract_record(record, cfg, project_root)
        extracted.append(result)
        ee_val = result.get("ee_percent", "") or "?"
        print(f"  [{idx}/{len(confirmed)}] {record.get('DOI','')[:40]:<42} ee={ee_val}%")

    # Build column list from config if specified, else use all keys
    if not columns:
        columns = list(extracted[0].keys()) if extracted else []

    confirmed_columns = list(dict.fromkeys(
        key for record in confirmed for key in record
    )) or columns
    export_records_xlsx(
        extracted, columns, extraction_excel,
        sheet_name="reaction_data",
        extra_sheets={"all_confirmed_metadata": confirmed},
        extra_sheet_columns={"all_confirmed_metadata": confirmed_columns},
    )
    (data_dir / "reaction_data.json").write_text(
        json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log_event(logs_dir / "pipeline.jsonl", "extraction_complete",
              prefix=prefix, records=len(extracted))
    print(f"[extraction] Done. Output: {extraction_excel}")
    return {"records_extracted": len(extracted), "output_excel": str(extraction_excel)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 5: Reaction data extraction")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg    = load_config(args.config)
    state  = ProjectState()
    run_id = make_run_id(cfg["project"]["name"])
    state.start_stage(run_id, "reaction_data_extraction", config=args.config)
    try:
        stats = run(cfg)
        state.finish_stage(run_id, "reaction_data_extraction", **stats)
        print(state.summary(run_id))
    except Exception as exc:
        state.fail_stage(run_id, "reaction_data_extraction", str(exc))
        raise


if __name__ == "__main__":
    main()
