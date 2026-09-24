"""Audit how each development Gold case binds to an evidence candidate chunk.

Binding and Gold truth are separate contracts. This tool never changes a Gold
value, and a Gold value is never weakened because the builder cannot reach it.

A case binds only when the adjudicated Gold values pin exactly one candidate
chunk. There is no positional fallback: no first-candidate, no index match, no
zip. Everything else gets a fixed root-cause code.

Source scope: the builder runs over each source artifact of the case separately
(main article and SI are distinct artifacts), because a frozen target anchor may
live in either.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.reaction_candidate_extraction import extract_reaction_candidates  # noqa: E402

AUDIT_VERSION = "development-candidate-binding-v2"

BINDING_STATUSES = {"BOUND_EXACT", "BOUND_AFTER_GENERAL_FIX", "UNREPRESENTABLE_V1", "AMBIGUOUS_BINDING"}
ROOT_CAUSES = {
    "ANCHOR_OUTSIDE_CONTEXT_WINDOW",
    "TABLE_ONLY_TARGET",
    "SCHEME_ONLY_TARGET",
    "TARGET_WITHOUT_YIELD_EE_ANCHOR",
    "REGEX_MISSED_VALID_ANCHOR",
    "MULTIPLE_CANDIDATES_AMBIGUOUS",
    "SOURCE_TEXT_EXTRACTION_FAILURE",
    "TARGET_NOT_REPRESENTABLE_BY_CURRENT_BUILDER",
    "INSUFFICIENT_ADJUDICATED_VALUES",
    "OTHER_DOCUMENTED",
    "",
}

PIN_FIELDS = ("h2_pressure", "temperature", "reaction_time", "yield", "ee_or_er", "solvent")
CANDIDATE_ATTR = {
    "h2_pressure": "h2_pressure_bar",
    "temperature": "temperature_c",
    "reaction_time": "reaction_time_h",
    "yield": "yield_percent",
    "ee_or_er": "ee_percent",
    "solvent": "solvent",
}


def _pin_values(record: dict) -> dict:
    out = {}
    for name in PIN_FIELDS:
        field = record["fields"].get(name, {})
        if field.get("state") != "answered":
            continue
        value = field.get("value")
        if isinstance(value, dict):
            if value.get("kind") != "ee_percent":
                continue  # an er ratio is not comparable to the builder's ee capture
            value = value.get("value")
        out[name] = value
    return out


def _match_count(candidate, values: dict) -> int:
    hits = 0
    for name, expected in values.items():
        actual = getattr(candidate, CANDIDATE_ATTR[name], None)
        if actual is None:
            continue
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            hits += int(abs(float(expected) - float(actual)) < 1e-4)
        elif isinstance(expected, str) and isinstance(actual, str):
            hits += int(expected.strip().lower() == actual.strip().lower())
    return hits


def _artifacts(source_dir: Path, paper_id: str) -> list[tuple[str, Path]]:
    out = []
    main = source_dir / f"{paper_id}.txt"
    si = source_dir / f"{paper_id}_SI.txt"
    if main.exists():
        out.append(("MAIN", main))
    if si.exists():
        out.append(("SI", si))
    return out


def audit(gold_records: list[dict], source_dir: Path) -> list[dict]:
    rows = []
    for record in gold_records:
        case = record["gold_case_id"]
        paper_id = record["paper_id"]
        anchor = record.get("legacy_target_anchor", "")
        values = _pin_values(record)
        artifacts = _artifacts(source_dir, paper_id)

        if not artifacts:
            rows.append(_row(case, paper_id, anchor, "", "", "UNREPRESENTABLE_V1",
                             "", "SOURCE_TEXT_EXTRACTION_FAILURE",
                             "No extracted source text for this paper."))
            continue

        best = []
        total_candidates = 0
        for role, path in artifacts:
            text = path.read_text(encoding="utf-8", errors="ignore")
            candidates = extract_reaction_candidates(text)
            total_candidates += len(candidates)
            for candidate in candidates:
                hits = _match_count(candidate, values)
                if values and hits >= 2:
                    best.append((role, candidate, hits))

        if not values:
            rows.append(_row(case, paper_id, anchor, "", "", "UNREPRESENTABLE_V1",
                             "gold_value_pin", "INSUFFICIENT_ADJUDICATED_VALUES",
                             f"No adjudicated numeric Gold value yet; {total_candidates} candidates exist."))
            continue
        if len(values) < 2:
            rows.append(_row(case, paper_id, anchor, "", "", "AMBIGUOUS_BINDING",
                             "gold_value_pin", "INSUFFICIENT_ADJUDICATED_VALUES",
                             f"Only {len(values)} adjudicated value(s); a single value cannot pin a chunk uniquely."))
            continue

        best.sort(key=lambda item: -item[2])
        top = [item for item in best if item[2] == best[0][2]] if best else []
        if len(top) == 1:
            role, candidate, hits = top[0]
            rows.append(_row(case, paper_id, anchor, candidate.candidate_id,
                             f"{paper_id}:{role}:{candidate.evidence_start}-{candidate.evidence_end}",
                             "BOUND_EXACT", "gold_value_pin", "",
                             f"{hits} adjudicated values reproduced in one chunk of the {role} artifact."))
        elif len(top) > 1:
            rows.append(_row(case, paper_id, anchor, "", "", "AMBIGUOUS_BINDING",
                             "gold_value_pin", "MULTIPLE_CANDIDATES_AMBIGUOUS",
                             f"{len(top)} chunks reproduce the adjudicated values equally well."))
        else:
            cause = _diagnose(artifacts, values)
            rows.append(_row(case, paper_id, anchor, "", "", "UNREPRESENTABLE_V1",
                             "gold_value_pin", cause,
                             f"No chunk reproduces the adjudicated values across {len(artifacts)} artifact(s)."))
    return rows


def _diagnose(artifacts, values) -> str:
    """Name why the builder cannot reach the target, from the text itself."""
    joined = ""
    for _, path in artifacts:
        joined += path.read_text(encoding="utf-8", errors="ignore")
    has_ee = re.search(r"\d{1,3}(?:\.\d+)?\s*%\s*ee", joined, re.I)
    has_yield = re.search(r"\d{1,3}(?:\.\d+)?\s*%\s*yield", joined, re.I)
    has_er = re.search(r"\d{1,3}\s*:\s*\d{1,3}", joined)
    if not has_ee and not has_yield and has_er:
        return "REGEX_MISSED_VALID_ANCHOR"
    if not has_ee and not has_yield:
        return "TARGET_WITHOUT_YIELD_EE_ANCHOR"
    return "TARGET_NOT_REPRESENTABLE_BY_CURRENT_BUILDER"


def _row(case, paper_id, anchor, candidate_id, chunk_id, status, method, cause, note):
    assert status in BINDING_STATUSES, status
    assert cause in ROOT_CAUSES, cause
    return {
        "gold_case_id": case,
        "paper_id": paper_id,
        "target_anchor_id": anchor,
        "candidate_id": candidate_id,
        "source_chunk_id": chunk_id,
        "binding_status": status,
        "binding_method": method,
        "root_cause": cause,
        "review_status": "PROVISIONAL_SOURCE_ADJUDICATION",
        "note": note,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "benchmark/development_gold/candidate_binding_v1.csv"),
    )
    args = parser.parse_args()

    gold = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = audit(gold, Path(args.source_dir))

    fieldnames = [
        "gold_case_id", "paper_id", "target_anchor_id", "candidate_id", "source_chunk_id",
        "binding_status", "binding_method", "root_cause", "review_status", "note",
    ]
    with open(args.out, "w", newline="\n", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    statuses, causes = {}, {}
    for row in rows:
        statuses[row["binding_status"]] = statuses.get(row["binding_status"], 0) + 1
        if row["root_cause"]:
            causes[row["root_cause"]] = causes.get(row["root_cause"], 0) + 1
    print(json.dumps({"audit_version": AUDIT_VERSION, "cases": len(rows),
                      "binding_status": statuses, "root_cause": causes,
                      "out": args.out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
