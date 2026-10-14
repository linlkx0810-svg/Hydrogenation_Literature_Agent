"""Recompute the development Gold status from the Gold file itself.

`tools/build_development_gold.py` builds the pre-review Gold from the legacy
migration plus the adjudication table. Once a human reviewer's decisions have
been promoted into the Gold, that build is no longer the current artifact, so
status must be read from the Gold file rather than regenerated from the inputs.

Rebuild + promote is still fully reproducible: CI rebuilds from the committed
inputs, replays the recorded decisions and compares the result byte for byte to
the committed Gold.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

GOLD_VERSION = "development-gold-field-schema-v1"
FIELD_SCHEMA_VERSION = "agent-v1-field-schema-v1"
SCORED_STATES = ("answered", "not_reported", "not_applicable")


def status_from(records: list[dict]) -> dict:
    states = Counter()
    by_field: dict[str, Counter] = {}
    provenance = Counter()
    review_status = Counter()

    for record in records:
        for name, field in record["fields"].items():
            states[field["state"]] += 1
            by_field.setdefault(name, Counter())[field["state"]] += 1
            provenance[field.get("provenance") or "UNSET"] += 1
            review_status[field.get("review_status") or "UNSET"] += 1

    excluded = states["unresolved_reference"] + states["needs_source_review"]
    return {
        "gold_version": GOLD_VERSION,
        "field_schema_version": FIELD_SCHEMA_VERSION,
        "cases": len(records),
        "field_slot_count": len(records) * 12,
        "answered": states["answered"],
        "not_reported": states["not_reported"],
        "not_applicable": states["not_applicable"],
        "unresolved_reference": states["unresolved_reference"],
        "needs_source_review": states["needs_source_review"],
        "scored_slots": sum(states[s] for s in SCORED_STATES),
        "excluded_from_denominator": excluded,
        "source_confirmed": review_status.get("SOURCE_CONFIRMED", 0),
        "human_confirmed": review_status.get("HUMAN_CONFIRMED", 0),
        "legacy_migrated": sum(
            count for name, count in provenance.items() if name.startswith("LEGACY_GOLD_")
        ),
        "newly_adjudicated": sum(
            provenance.get(name, 0)
            for name in (
                "LEGACY_SOURCE_REVIEW_RECORD",
                "LEGACY_TARGET_ANCHOR",
                "SOURCE_REVIEW_RECORD_SCOPE",
                "LEGACY_CORPUS_TAXONOMY",
            )
        ),
        "provenance_counts": dict(provenance),
        "review_status_counts": dict(review_status),
        "field_breakdown": {name: dict(counter) for name, counter in by_field.items()},
        "completeness": "COMPLETE" if states["needs_source_review"] == 0 else "INCOMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in Path(args.gold).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    status = status_from(records)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
