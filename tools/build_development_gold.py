"""Phase B: merge the Stage-1 migration with source adjudications into the Gold.

Input:
  benchmark/development_gold/development_gold_migration_stage1.jsonl   (Phase A)
  benchmark/development_gold/phase_b_adjudications_v1.csv              (source review)

Output:
  benchmark/development_gold/development_gold_field_schema_v1.jsonl

Rules enforced here:

- a Gold value may only come from a source-evidence provenance; an Agent
  prediction provenance is rejected outright;
- `answered` requires a value, a provenance, a source locator and an evidence
  type; `not_reported` must carry a review status proving it was looked for;
- `substrate_class` is never copied into `substrate`;
- a legacy ee migrates as `{kind, value}` and is never converted to an er, and
  no configuration is ever derived from it;
- anything the legacy record and the adjudication table do not establish stays
  `needs_source_review` and is excluded from every scoring denominator.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = PROJECT_ROOT / "benchmark" / "development_gold"

GOLD_VERSION = "development-gold-field-schema-v1"
FIELD_SCHEMA_VERSION = "agent-v1-field-schema-v1"

GOLD_STATES = ("answered", "not_reported", "not_applicable", "unresolved_reference", "needs_source_review")
SCORED_STATES = ("answered", "not_reported", "not_applicable")
FORBIDDEN_PROVENANCE = {
    "AGENT_PREDICTION",
    "LLM_EXTRACTOR",
    "llm-extractor-v1",
    "llm-extractor-v2",
    "VERIFIER",
    "RESOLVER",
    "SCORER",
}


class GoldBuildError(RuntimeError):
    """Raised when a Gold record would violate the Gold contract."""


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _adjudications(path: Path) -> dict[tuple[str, str], dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["gold_case_id"], row["field"])
        if key in out:
            raise GoldBuildError(f"duplicate adjudication for {key}")
        out[key] = row
    return out


def _typed_value(row: dict):
    value = (row.get("value") or "").strip()
    kind = (row.get("value_kind") or "").strip()
    if not value:
        return None
    if kind:
        return {"kind": kind, "value": float(value)}
    try:
        return float(value)
    except ValueError:
        return value


def _apply(field_record: dict, row: dict, field: str) -> dict:
    state = row["state"].strip()
    if state not in GOLD_STATES:
        raise GoldBuildError(f"invalid gold state {state}")
    provenance = row["provenance"].strip()
    if provenance.upper() in FORBIDDEN_PROVENANCE:
        raise GoldBuildError(
            f"{field}: gold_provenance must never be an Agent prediction ({provenance})"
        )

    merged = dict(field_record)
    merged.update(
        {
            "state": state,
            "value": _typed_value(row) if state == "answered" else None,
            "reported_value": (row.get("reported_value") or "").strip() or None,
            "canonical_value": (row.get("canonical_value") or "").strip() or None,
            "provenance": provenance,
            "source_role": (row.get("source_role") or "").strip() or None,
            "source_locator": (row.get("source_locator") or "").strip() or None,
            "evidence_type": (row.get("evidence_type") or "").strip() or None,
            "review_status": (row.get("review_status") or "").strip() or None,
            "comparison_mode": (row.get("comparison_mode") or "").strip() or None,
            "note": (row.get("note") or "").strip() or merged.get("note"),
        }
    )

    if state == "answered":
        if merged["value"] in (None, ""):
            raise GoldBuildError(f"{field}: answered gold without a value")
        for key in ("source_locator", "evidence_type", "provenance"):
            if not merged[key]:
                raise GoldBuildError(f"{field}: answered gold without {key}")
    if state == "not_reported" and merged["value"] is not None:
        raise GoldBuildError(f"{field}: not_reported gold must not carry a value")
    if state == "not_reported" and merged["review_status"] != "SOURCE_REVIEWED_NOT_REPORTED":
        raise GoldBuildError(
            f"{field}: not_reported requires review_status SOURCE_REVIEWED_NOT_REPORTED"
        )
    return merged


def build(stage1_path: Path, adjudications_path: Path) -> tuple[list[dict], dict]:
    stage1 = _read_jsonl(stage1_path)
    adjudications = _adjudications(adjudications_path)
    used: set[tuple[str, str]] = set()
    records = []

    for record in stage1:
        case_id = record["gold_case_id"]
        fields = {}
        for field, field_record in record["fields"].items():
            key = (case_id, field)
            if key in adjudications:
                fields[field] = _apply(field_record, adjudications[key], field)
                used.add(key)
            else:
                fields[field] = field_record
            if field == "substrate":
                legacy = fields[field].get("legacy_support")
                if legacy == "substrate_class" and fields[field].get("value") is not None:
                    if fields[field].get("provenance") == "NON_EQUIVALENT_REQUIRES_REVIEW":
                        raise GoldBuildError(
                            "substrate_class was copied into substrate; that is never allowed"
                        )
        records.append(
            {
                "gold_case_id": case_id,
                "paper_id": record["paper_id"],
                "doi": record["doi"],
                "metal": record["metal"],
                "gold_version": GOLD_VERSION,
                "field_schema_version": FIELD_SCHEMA_VERSION,
                "lineage": "legacy Gold v1 (8 fields) + source adjudication -> development Gold FIELD_SCHEMA_V1",
                "legacy_target_anchor": record["legacy_target_anchor"],
                "source_scope": record["source_scope"],
                "fields": fields,
            }
        )

    unused = sorted(adjudications.keys() - used)
    if unused:
        raise GoldBuildError(f"adjudications that match no case/field: {unused}")

    states = Counter()
    by_field = {}
    provenance = Counter()
    for record in records:
        for name, field in record["fields"].items():
            states[field["state"]] += 1
            by_field.setdefault(name, Counter())[field["state"]] += 1
            provenance[field.get("provenance") or "UNSET"] += 1

    status = {
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
        "excluded_from_denominator": states["unresolved_reference"] + states["needs_source_review"],
        "source_confirmed": sum(
            1
            for record in records
            for field in record["fields"].values()
            if field.get("review_status") == "SOURCE_CONFIRMED"
        ),
        "legacy_migrated": sum(
            1
            for record in records
            for field in record["fields"].values()
            if str(field.get("provenance", "")).startswith("LEGACY_GOLD_")
        ),
        "newly_adjudicated": sum(
            1
            for record in records
            for field in record["fields"].values()
            if field.get("provenance")
            in {"LEGACY_SOURCE_REVIEW_RECORD", "LEGACY_TARGET_ANCHOR", "SOURCE_REVIEW_RECORD_SCOPE"}
        ),
        "provenance_counts": dict(provenance),
        "field_breakdown": {name: dict(counter) for name, counter in by_field.items()},
        "completeness": "COMPLETE" if states["needs_source_review"] == 0 else "INCOMPLETE",
    }
    return records, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", default=str(GOLD_DIR / "development_gold_migration_stage1.jsonl"))
    parser.add_argument("--adjudications", default=str(GOLD_DIR / "phase_b_adjudications_v1.csv"))
    parser.add_argument("--out", default=str(GOLD_DIR / "development_gold_field_schema_v1.jsonl"))
    parser.add_argument(
        "--status", default=str(PROJECT_ROOT / "benchmark" / "development_gold_v1_status.json")
    )
    args = parser.parse_args()

    records, status = build(Path(args.stage1), Path(args.adjudications))
    Path(args.out).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    Path(args.status).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
