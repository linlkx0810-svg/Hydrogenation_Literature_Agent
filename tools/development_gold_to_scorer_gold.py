"""Adapt the development Gold to the scorer's gold format.

The scorer keys on `candidate_id` and skips any field a gold record does not
carry. That is exactly the behaviour we want for unadjudicated slots: a field in
state `needs_source_review` or `unresolved_reference` is **omitted**, so it never
reaches a denominator. Only `answered`, `not_reported` and `not_applicable` are
emitted.

Cases without a bound candidate are skipped and reported, never guessed onto a
chunk.
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

SCORED_STATES = {"answered", "not_reported", "not_applicable"}


def to_scorer_gold(gold_records: list[dict], bindings: dict[str, str]) -> tuple[list[dict], list[str]]:
    rows, skipped = [], []
    for record in gold_records:
        candidate_id = bindings.get(record["gold_case_id"])
        if not candidate_id:
            skipped.append(record["gold_case_id"])
            continue
        fields = {}
        for name, field in record["fields"].items():
            state = field["state"]
            if state not in SCORED_STATES:
                continue
            fields[name] = {"value": field.get("value"), "state": state}
        rows.append(
            {
                "candidate_id": candidate_id,
                "gold_case_id": record["gold_case_id"],
                "paper_id": record["paper_id"],
                "fields": fields,
            }
        )
    return rows, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--crosswalk", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    gold = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with open(args.crosswalk, newline="", encoding="utf-8-sig") as handle:
        bindings = {
            row["gold_case_id"]: row["bound_candidate_id"]
            for row in csv.DictReader(handle)
            if row["bound_candidate_id"]
        }

    rows, skipped = to_scorer_gold(gold, bindings)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(
        json.dumps(
            {
                "scorer_gold_rows": len(rows),
                "scored_field_slots": sum(len(r["fields"]) for r in rows),
                "skipped_unbound_cases": skipped,
                "out": args.out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
