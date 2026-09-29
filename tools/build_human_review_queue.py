"""Emit the human-review queue for every Gold slot Claude did not adjudicate.

One row per open slot, with the reason it is open and the locator a reviewer
should start from. No row carries a guessed answer: the `decision_needed`
column states the question, never a proposed value.
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

QUEUE_VERSION = "development-gold-human-review-queue-v1"
OPEN_STATES = {"needs_source_review", "unresolved_reference"}

REASONS = {
    "catalyst": "STRUCTURE_OR_LABEL_ONLY_IDENTITY",
    "product": "STRUCTURE_ONLY_IDENTITY",
    "substrate": "CLASS_LABEL_IS_NOT_AN_IDENTITY",
    "ligand": "MANUAL_STRUCTURE_REVIEW_REQUIRED",
    "stereochemical_outcome": "ABSOLUTE_CONFIGURATION_NOT_ESTABLISHED",
}
DEFAULT_REASON = "VALUE_MUST_BE_READ_FROM_THE_FROZEN_TARGET_ANCHOR"

QUESTIONS = {
    "catalyst": "Which catalyst or precatalyst entity does the frozen target entry report, as reported, without merging metal and ligand?",
    "ligand": "Which ligand does the target entry use, and does the source define the paper-local label explicitly?",
    "substrate": "Which substrate does the target entry use, named rather than classified?",
    "product": "Which product does the target entry give, named rather than classified?",
    "stereochemical_outcome": "Does the source state an absolute configuration for the target entry, or only an ee or er?",
    "h2_pressure": "What H2 pressure does the target entry report, and in which unit?",
    "temperature": "What temperature does the target entry report?",
    "reaction_time": "What reaction time does the target entry report?",
    "solvent": "Which solvent does the target entry report?",
    "yield": "Does the target entry report an isolated yield, or a conversion?",
    "ee_or_er": "Does the target entry report an ee or an er, and with what value?",
    "reaction": "Is the assigned taxonomy label correct for this target reaction?",
}


def build(gold_records: list[dict], binding: dict[str, dict]) -> list[dict]:
    rows = []
    for record in gold_records:
        case = record["gold_case_id"]
        anchor = record.get("legacy_target_anchor", "")
        bind = binding.get(case, {})
        for name, field in record["fields"].items():
            if field["state"] not in OPEN_STATES:
                continue
            rows.append(
                {
                    "case": case,
                    "paper_id": record["paper_id"],
                    "field": name,
                    "gold_state": field["state"],
                    "reason": REASONS.get(name, DEFAULT_REASON),
                    "source_locator": f"{record['source_scope']} @ {anchor}",
                    "binding_status": bind.get("binding_status", ""),
                    "decision_needed": QUESTIONS.get(name, "Establish the reference value from the source."),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "benchmark/development_gold/HUMAN_REVIEW_QUEUE_V1.csv"),
    )
    args = parser.parse_args()

    gold = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with open(args.binding, newline="", encoding="utf-8-sig") as handle:
        binding = {row["gold_case_id"]: row for row in csv.DictReader(handle)}

    rows = build(gold, binding)
    fieldnames = ["case", "paper_id", "field", "gold_state", "reason",
                  "source_locator", "binding_status", "decision_needed"]
    with open(args.out, "w", newline="\n", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "queue_version": QUEUE_VERSION,
                "queued_slots": len(rows),
                "cases_affected": len({row["case"] for row in rows}),
                "fields_affected": dict(Counter(row["field"] for row in rows)),
                "reasons": dict(Counter(row["reason"] for row in rows)),
                "out": args.out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
