"""Project what candidate binding would become if Batch 01 were approved.

Read-only with respect to the formal artifacts: it never writes the Gold and
never writes `candidate_binding_v1.csv`. It answers one question — is this
review batch worth a reviewer's time — and writes only
`binding_preview_batch_01.json`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.audit_candidate_binding import audit  # noqa: E402
from tools.apply_human_gold_reviews import _typed  # noqa: E402

PREVIEW_VERSION = "binding-preview-batch-01-v1"


def _apply_proposals(gold_records: list[dict], reviews: list[dict]) -> list[dict]:
    """In-memory only: pretend every proposal was approved."""
    projected = json.loads(json.dumps(gold_records))
    index = {record["gold_case_id"]: record for record in projected}
    for row in reviews:
        record = index.get(row["case_id"])
        if record is None:
            continue
        field = record["fields"].get(row["field"])
        if field is None:
            continue
        state = (row.get("proposed_state") or "").strip()
        field["state"] = state
        field["value"] = _typed(row.get("proposed_value", ""), row.get("unit", "")) if state == "answered" else None
    return projected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--binding", required=True, help="current binding audit CSV")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "benchmark/development_gold/binding_preview_batch_01.json"),
    )
    args = parser.parse_args()

    gold = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with open(args.reviews, newline="", encoding="utf-8-sig") as handle:
        reviews = list(csv.DictReader(handle))
    with open(args.binding, newline="", encoding="utf-8-sig") as handle:
        current = list(csv.DictReader(handle))

    projected_rows = audit(_apply_proposals(gold, reviews), Path(args.source_dir))
    current_counts = Counter(row["binding_status"] for row in current)
    projected_counts = Counter(row["binding_status"] for row in projected_rows)

    changed = []
    current_by_case = {row["gold_case_id"]: row["binding_status"] for row in current}
    for row in projected_rows:
        before = current_by_case.get(row["gold_case_id"])
        if before != row["binding_status"]:
            changed.append(
                {
                    "case": row["gold_case_id"],
                    "before": before,
                    "after": row["binding_status"],
                    "root_cause_after": row["root_cause"],
                }
            )

    preview = {
        "preview_version": PREVIEW_VERSION,
        "hypothetical": True,
        "note": "This is what binding would become if every Batch 01 proposal were approved. No formal artifact was modified.",
        "current": dict(current_counts),
        "projected": dict(projected_counts),
        "changed_cases": changed,
        "projected_exact": projected_counts.get("BOUND_EXACT", 0),
        "projected_ambiguous": projected_counts.get("AMBIGUOUS_BINDING", 0),
        "projected_unrepresentable": projected_counts.get("UNREPRESENTABLE_V1", 0),
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(preview, indent=2) + "\n")
    print(json.dumps(preview, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
