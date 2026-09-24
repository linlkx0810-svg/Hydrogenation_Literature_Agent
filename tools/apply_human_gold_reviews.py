"""Promote human review decisions into the formal development Gold.

Claude proposes; a human approves. This tool is the only path from a review
row into `development_gold_field_schema_v1.jsonl`, and it fails closed:

- `APPROVE`     -> the proposal becomes Gold, provenance HUMAN_REVIEW_CONFIRMED
- `MODIFY`      -> the reviewer's own value and state become Gold, and the row
                   must carry reviewer_value, reviewer_state and reviewer_note
- `UNRESOLVED`  -> the slot becomes unresolved_reference with reviewer provenance
- `REJECT`      -> nothing changes; the slot stays open
- blank         -> nothing changes; the slot stays open

A row whose decision is empty can never promote, and the tool refuses to run if
a decision column contains anything outside the four verbs. Claude never fills
that column: a test asserts the committed batch ships with every decision blank.
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

PROMOTION_VERSION = "human-gold-review-promotion-v1"
DECISIONS = {"APPROVE", "REJECT", "MODIFY", "UNRESOLVED", ""}
PROMOTING = {"APPROVE", "MODIFY", "UNRESOLVED"}
GOLD_STATES = {"answered", "not_reported", "not_applicable", "unresolved_reference"}


class PromotionError(RuntimeError):
    """Raised when a review row cannot be promoted as given."""


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _typed(value: str, unit: str):
    value = (value or "").strip()
    if not value:
        return None
    if (unit or "").startswith("percent_ee"):
        return {"kind": "ee_percent", "value": float(value)}
    if (unit or "").startswith("ratio_er"):
        major, _, minor = value.partition(":")
        return {"kind": "er_ratio", "major": float(major), "minor": float(minor)}
    try:
        return float(value)
    except ValueError:
        return value


def promote(gold_records: list[dict], reviews: list[dict]) -> tuple[list[dict], dict]:
    index = {record["gold_case_id"]: record for record in gold_records}
    counts = Counter()

    for row in reviews:
        decision = (row.get("reviewer_decision") or "").strip().upper()
        if decision not in DECISIONS:
            raise PromotionError(f"{row['review_id']}: unknown reviewer_decision {decision!r}")
        counts[decision or "BLANK"] += 1
        if decision not in PROMOTING:
            continue

        record = index.get(row["case_id"])
        if record is None:
            raise PromotionError(f"{row['review_id']}: unknown case {row['case_id']}")
        field = record["fields"].get(row["field"])
        if field is None:
            raise PromotionError(f"{row['review_id']}: unknown field {row['field']}")

        if decision == "APPROVE":
            state = (row.get("proposed_state") or "").strip()
            value = _typed(row.get("proposed_value", ""), row.get("unit", ""))
            note = row.get("review_reason", "")
        elif decision == "MODIFY":
            for key in ("reviewer_value", "reviewer_state", "reviewer_note"):
                if not (row.get(key) or "").strip():
                    raise PromotionError(f"{row['review_id']}: MODIFY requires {key}")
            state = row["reviewer_state"].strip()
            value = _typed(row["reviewer_value"], row.get("unit", ""))
            note = row["reviewer_note"]
        else:  # UNRESOLVED
            state, value = "unresolved_reference", None
            note = row.get("reviewer_note") or row.get("review_reason", "")

        if state not in GOLD_STATES:
            raise PromotionError(f"{row['review_id']}: invalid gold state {state!r}")
        if state == "answered" and value in (None, ""):
            raise PromotionError(f"{row['review_id']}: answered promotion without a value")
        if state != "answered" and value not in (None, ""):
            raise PromotionError(f"{row['review_id']}: {state} promotion must not carry a value")

        locator = (row.get("table_or_scheme") or row.get("page") or "").strip()
        if state == "answered" and not locator:
            raise PromotionError(f"{row['review_id']}: answered promotion without an evidence locator")

        field.update(
            {
                "state": state,
                "value": value,
                "reported_value": (row.get("reported_value") or "").strip() or None,
                "provenance": "HUMAN_REVIEW_CONFIRMED",
                "source_role": (row.get("source_role") or "").strip() or None,
                "source_locator": locator or field.get("source_locator"),
                "evidence_type": "human_reviewed_source",
                "review_status": "HUMAN_CONFIRMED",
                "review_decision": decision,
                "review_id": row["review_id"],
                "note": note,
            }
        )

    return gold_records, dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    gold = _read_jsonl(Path(args.gold))
    with open(args.reviews, newline="", encoding="utf-8-sig") as handle:
        reviews = list(csv.DictReader(handle))

    promoted, counts = promote(gold, reviews)
    if not any(counts.get(d) for d in PROMOTING):
        print(
            json.dumps(
                {
                    "promotion_version": PROMOTION_VERSION,
                    "status": "NO_DECISIONS_TO_PROMOTE",
                    "decisions": counts,
                    "gold_written": False,
                    "note": "Every review row is blank or REJECT; the Gold is unchanged.",
                },
                indent=2,
            )
        )
        return 0

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(json.dumps(r, ensure_ascii=False) for r in promoted) + "\n")
    print(
        json.dumps(
            {
                "promotion_version": PROMOTION_VERSION,
                "status": "PROMOTED",
                "decisions": counts,
                "gold_written": True,
                "out": args.out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
