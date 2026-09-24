"""Bind development Gold cases to evidence-builder candidate chunks.

The Agent's evaluation unit is `candidate x field`, so every Gold case must be
bound to a candidate the deterministic evidence builder actually produces. This
tool runs the builder over each case's local source text and records the result.

It never picks "the first candidate". A binding is only recorded when an
adjudicated Gold value pins exactly one chunk. Everything else is reported as
`CANDIDATE_BINDING_FAILURE` or `BINDING_PENDING_ADJUDICATION`, which are real
pipeline findings, not bookkeeping noise.

Source files stay outside the repository: the tool takes a directory of local
source text and writes only identifiers, counts and statuses.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.reaction_candidate_extraction import extract_reaction_candidates  # noqa: E402

BINDING_VERSION = "development-gold-candidate-binding-v1"
FIELDS = ("h2_pressure", "temperature", "reaction_time", "yield", "ee_or_er", "solvent")


def _answered_values(record: dict) -> dict:
    out = {}
    for name in FIELDS:
        field = record["fields"].get(name, {})
        if field.get("state") != "answered":
            continue
        value = field.get("value")
        if isinstance(value, dict):
            value = value.get("value")
        out[name] = value
    return out


def _matches(candidate, values: dict) -> bool:
    checks = {
        "h2_pressure": candidate.h2_pressure_bar,
        "temperature": candidate.temperature_c,
        "reaction_time": candidate.reaction_time_h,
        "yield": candidate.yield_percent,
        "ee_or_er": candidate.ee_percent,
        "solvent": candidate.solvent,
    }
    hits = 0
    for name, expected in values.items():
        actual = checks.get(name)
        if actual is None:
            continue
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if abs(float(expected) - float(actual)) < 1e-4:
                hits += 1
        elif isinstance(expected, str) and isinstance(actual, str):
            if expected.strip().lower() == actual.strip().lower():
                hits += 1
    return hits >= 2


def bind(gold_records: list[dict], source_dir: Path) -> list[dict]:
    rows = []
    for record in gold_records:
        paper_id = record["paper_id"]
        text_path = source_dir / f"{paper_id}.txt"
        values = _answered_values(record)

        if not text_path.exists():
            rows.append(
                {
                    "gold_case_id": record["gold_case_id"],
                    "paper_id": paper_id,
                    "source_text_available": False,
                    "candidate_count": 0,
                    "bound_candidate_id": "",
                    "binding_method": "",
                    "binding_status": "SOURCE_TEXT_UNAVAILABLE",
                    "note": "No extracted source text for this paper in the supplied directory.",
                }
            )
            continue

        text = text_path.read_text(encoding="utf-8", errors="ignore")
        candidates = extract_reaction_candidates(text)

        if not values:
            status, bound, method = "BINDING_PENDING_ADJUDICATION", "", ""
            note = "No adjudicated numeric Gold value yet, so no chunk can be pinned."
        else:
            matching = [c for c in candidates if _matches(c, values)]
            if len(matching) == 1:
                status, bound, method = "BOUND", matching[0].candidate_id, "gold_value_pin"
                note = "Exactly one candidate chunk reproduces the adjudicated Gold values."
            elif len(matching) > 1:
                status, bound, method = "CANDIDATE_BINDING_FAILURE", "", "gold_value_pin"
                note = f"{len(matching)} candidate chunks match the adjudicated values; the target is not uniquely pinned."
            else:
                status, bound, method = "CANDIDATE_BINDING_FAILURE", "", "gold_value_pin"
                note = "No candidate chunk reproduces the adjudicated Gold values; the evidence builder does not surface this target."

        rows.append(
            {
                "gold_case_id": record["gold_case_id"],
                "paper_id": paper_id,
                "source_text_available": True,
                "candidate_count": len(candidates),
                "bound_candidate_id": bound,
                "binding_method": method,
                "binding_status": status,
                "note": note,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--source-dir", required=True, help="directory with <paper_id>.txt files")
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "benchmark" / "development_candidate_id_crosswalk.csv"),
    )
    args = parser.parse_args()

    gold = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = bind(gold, Path(args.source_dir))

    fieldnames = [
        "gold_case_id",
        "paper_id",
        "source_text_available",
        "candidate_count",
        "bound_candidate_id",
        "binding_method",
        "binding_status",
        "note",
    ]
    with open(args.out, "w", newline="\n", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary = {}
    for row in rows:
        summary[row["binding_status"]] = summary.get(row["binding_status"], 0) + 1
    bound_ids = [row["bound_candidate_id"] for row in rows if row["bound_candidate_id"]]
    print(
        json.dumps(
            {
                "binding_version": BINDING_VERSION,
                "cases": len(rows),
                "status_counts": summary,
                "duplicate_bound_ids": len(bound_ids) != len(set(bound_ids)),
                "out": args.out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
