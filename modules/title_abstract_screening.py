"""
modules/title_abstract_screening.py
────────────────────────────────────
Stage 2: Title/abstract screening.

Reads the master records from Stage 1, applies metal-specific
and universal exclusion rules, scores records, and outputs:
  - screened Excel (all records with decisions)
  - strict-H2-only Excel (records without H2 evidence excluded)

Entry point
-----------
    from modules.title_abstract_screening import run
    stats = run(cfg)
"""

import argparse
import json
import re
from pathlib import Path

from utils import load_config, log_event, ProjectState, make_run_id
from utils.excel_io import export_records_xlsx
from utils.text_utils import LITERATURE_COLUMNS, load_json

ASYMMETRIC_RE    = re.compile(r"\b(?:asymmetric|enantioselective|enantioenriched|chiral|\bee\b)\b", re.I)
HYDROGENATION_RE = re.compile(r"\bhydrogenation\b", re.I)
H2_RE            = re.compile(r"\b(?:molecular hydrogen|hydrogen gas|h2)\b", re.I)
EXPERIMENT_RE    = re.compile(r"\b(?:catalyst|ligand|yield|substrate|scope|pressure|\bee\b|synthesis|complex)\b", re.I)
REVIEW_RE        = re.compile(r"\b(?:review|perspective|overview|progress|advances?)\b", re.I)

SCREENED_COLUMNS = LITERATURE_COLUMNS + ["Original tier"]

STRICT_H2_COLUMNS = [
    "Title", "Authors", "Year", "Journal", "DOI", "URL",
    "Source database", "Search query",
    "Record type: primary / review / book chapter / unknown",
    "Inclusion decision", "Exclusion reason", "Confidence score",
    "H2 evidence", "Strict H2-only decision", "Notes",
    "Original tier",
]


def _compile_metal_re(cfg: dict) -> re.Pattern:
    pattern = cfg["metal"].get("regex", r"\b(?:iron|fe)\b")
    return re.compile(pattern, re.I)


def _compile_other_metal_re(cfg: dict) -> re.Pattern | None:
    pattern = cfg.get("screening", {}).get("other_metal_regex", "")
    if not pattern:
        return None
    cleaned = " ".join(pattern.split())
    try:
        return re.compile(cleaned, re.I)
    except re.error:
        return None


def _build_exclusion_patterns(cfg: dict) -> list[tuple[str, re.Pattern]]:
    universal = cfg.get("screening", {}).get("universal_exclusion_terms", [])
    metal_specific = cfg.get("screening", {}).get("metal_exclusion_terms", [])
    terms = list(universal) + list(metal_specific)
    patterns = []
    for term in terms:
        try:
            patterns.append((term, re.compile(re.escape(term), re.I)))
        except re.error:
            pass
    return patterns


def classify_record(record: dict, cfg: dict,
                    metal_re: re.Pattern,
                    exclusion_patterns: list[tuple[str, re.Pattern]]) -> dict:
    text = f"{record.get('Title', '')} {record.get('Abstract', '')}".lower()
    metal_name = cfg["metal"]["name"].lower()
    symbol     = cfg["metal"]["symbol"].lower()

    current_type = record.get("Record type: primary / review / book chapter / unknown", "unknown")
    if REVIEW_RE.search(text):
        current_type = "review"
    record["Record type: primary / review / book chapter / unknown"] = current_type or "unknown"

    score   = 0
    missing = []
    checks  = [
        (metal_re.search(text),       25, f"{metal_name.capitalize()} / {symbol.upper()} catalyst"),
        (ASYMMETRIC_RE.search(text),  20, "asymmetric or enantioselective wording"),
        (HYDROGENATION_RE.search(text), 20, "hydrogenation"),
        (H2_RE.search(text),          20, "molecular H2 wording"),
        (EXPERIMENT_RE.search(text),  15, "experimental detail wording"),
    ]
    for matched, points, reason in checks:
        if matched:
            score += points
        else:
            missing.append(reason)

    for term, pattern in exclusion_patterns:
        if pattern.search(text):
            record["Inclusion decision"] = "Exclude"
            record["Exclusion reason"]   = term.capitalize()
            record["Confidence score"]   = str(score)
            return record

    if current_type == "review":
        record["Inclusion decision"] = "Review source - citation mining"
        record["Exclusion reason"]   = "Review excluded from final primary-paper dataset"
    elif score == 100:
        record["Inclusion decision"] = "Include - metadata supports criteria; manual verification required"
        record["Exclusion reason"]   = ""
    else:
        record["Inclusion decision"] = "Primary candidate - manual review required"
        record["Exclusion reason"]   = f"Not explicit in searchable metadata: {', '.join(missing)}"
    record["Confidence score"] = str(score)
    return record


def _assign_tier(record: dict) -> str:
    decision = record.get("Inclusion decision", "")
    score    = int(record.get("Confidence score") or 0)
    if decision.startswith("Include") or score >= 80:
        return "Tier 1"
    return "Tier 2"


def _strict_h2_decision(record: dict) -> tuple[str, str]:
    """Return (h2_evidence, strict_decision)."""
    text = f"{record.get('Title','')} {record.get('Abstract','')}".lower()
    h2_evidence = H2_RE.search(text)
    if h2_evidence:
        return h2_evidence.group(0), "Include in H2-only dataset - explicit H2 evidence in metadata"
    return "", "Exclude from H2-only dataset - insufficient explicit evidence"


def run(cfg: dict) -> dict:
    """Execute Stage 2: title/abstract screening."""
    prefix        = cfg["output"]["prefix"]
    outputs_dir   = Path(cfg["output"]["outputs_dir"])
    logs_dir      = Path(cfg["output"]["logs_dir"])
    data_dir      = Path(cfg["output"]["data_subdir"])
    master_excel  = outputs_dir / cfg["output"]["master_excel"]
    screened_excel = outputs_dir / cfg["output"]["screened_excel"]
    strict_excel   = outputs_dir / cfg["output"]["strict_h2_excel"]

    records_path  = data_dir / "master_records.json"
    if not records_path.exists():
        raise FileNotFoundError(
            f"Stage 1 output not found: {records_path}\n"
            "Run literature_search first."
        )
    records = load_json(records_path, [])

    metal_re          = _compile_metal_re(cfg)
    excl_patterns     = _build_exclusion_patterns(cfg)
    other_metal_re    = _compile_other_metal_re(cfg)

    screened = []
    for rec in records:
        rec = classify_record(dict(rec), cfg, metal_re, excl_patterns)
        rec["Original tier"] = _assign_tier(rec)
        screened.append(rec)

    included  = [r for r in screened if not r["Inclusion decision"].startswith("Exclude")]
    reviews   = [r for r in screened if r.get("Record type: primary / review / book chapter / unknown") == "review"]
    excluded  = [r for r in screened if r["Inclusion decision"].startswith("Exclude")]

    # Export screened Excel
    export_records_xlsx(
        screened, SCREENED_COLUMNS, screened_excel,
        sheet_name="all_screened",
        extra_sheets={
            "included":  included,
            "reviews":   reviews,
            "excluded":  excluded,
        },
    )

    # Strict H2-only pass
    strict_records = []
    for rec in screened:
        if rec["Inclusion decision"].startswith("Exclude"):
            continue
        h2_ev, decision = _strict_h2_decision(rec)
        strict_rec = dict(rec)
        strict_rec["H2 evidence"]         = h2_ev
        strict_rec["Strict H2-only decision"] = decision
        strict_records.append(strict_rec)

    strict_h2   = [r for r in strict_records if "Include" in r["Strict H2-only decision"]]
    non_h2      = [r for r in strict_records if "Exclude" in r["Strict H2-only decision"]]

    export_records_xlsx(
        strict_records, STRICT_H2_COLUMNS, strict_excel,
        sheet_name="Strict_H2_candidates",
        extra_sheets={
            "Included_H2":       strict_h2,
            "Excluded_non_H2":   non_h2,
        },
    )

    # Save JSON for next stage
    (data_dir / "screened_records.json").write_text(
        json.dumps(screened, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "strict_h2_records.json").write_text(
        json.dumps(strict_h2, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log_event(logs_dir / "pipeline.jsonl", "screening_complete",
              prefix=prefix, total=len(screened),
              included=len(included), excluded=len(excluded),
              strict_h2=len(strict_h2))

    print(f"[screening] {prefix} — {len(screened)} records screened")
    print(f"  Included (all tiers): {len(included)} | Excluded: {len(excluded)}")
    print(f"  Strict H2-only candidates: {len(strict_h2)}")
    print(f"  Output: {screened_excel}")

    return {
        "total":       len(screened),
        "included":    len(included),
        "excluded":    len(excluded),
        "strict_h2":   len(strict_h2),
        "screened_excel": str(screened_excel),
        "strict_excel":   str(strict_excel),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Title/abstract screening")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg    = load_config(args.config)
    state  = ProjectState()
    run_id = make_run_id(cfg["project"]["name"])
    state.start_stage(run_id, "title_abstract_screening", config=args.config)
    try:
        stats = run(cfg)
        state.finish_stage(run_id, "title_abstract_screening", **stats)
        print(state.summary(run_id))
    except Exception as exc:
        state.fail_stage(run_id, "title_abstract_screening", str(exc))
        raise


if __name__ == "__main__":
    main()
