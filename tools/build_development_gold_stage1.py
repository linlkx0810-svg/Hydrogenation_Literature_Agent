"""Phase A: mechanical migration of the legacy development Gold.

This tool recovers what the legacy Gold v1 record actually establishes and
migrates it into the FIELD_SCHEMA_V1 shape. It performs **no** source
adjudication and fills **no** value that the legacy record does not state.

What the legacy record gives us:

- the 12 cases, their stable `dev_id`, `combined_record_id` and DOI;
- the frozen target anchor per case;
- the per-case list of fields that were finalized as null (`final_null_fields`);
- a small number of values quoted in the source-review notes.

What it does not give us: the populated Gold values themselves. The populated
artifact was kept local/private and is not recoverable (see
`docs/DEVELOPMENT_GOLD_MIGRATION_AUDIT.md`). Everything that is not established
by the legacy record is emitted as `NEEDS_SOURCE_REVIEW`, never as a value.

Output: `benchmark/development_gold/development_gold_migration_stage1.jsonl`
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY = PROJECT_ROOT / "benchmark" / "development_gold" / "legacy"
OUT_DIR = PROJECT_ROOT / "benchmark" / "development_gold"

FIELD_SCHEMA_VERSION = "agent-v1-field-schema-v1"
STAGE1_VERSION = "development-gold-migration-stage1"

# old field -> (new field, migration type)
LOSSLESS = {
    "h2_pressure_bar": "h2_pressure",
    "temperature_c": "temperature",
    "reaction_time_h": "reaction_time",
    "solvent": "solvent",
    "yield_percent": "yield",
    "ligand": "ligand",
}
TYPED = {"ee_percent": "ee_or_er"}
NON_EQUIVALENT = {"substrate_class": "substrate"}
NEW_FIELDS = ("reaction", "catalyst", "product", "stereochemical_outcome")

GOLD_STATES = ("answered", "not_reported", "not_applicable", "unresolved_reference")


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _legacy_null_fields(row: dict) -> set[str]:
    raw = (row.get("final_null_fields") or "").strip()
    return {part.strip() for part in raw.split(";") if part.strip()}


def build() -> list[dict]:
    manifest = {r["dev_id"]: r for r in _rows(LEGACY / "manifest_v1.csv")}
    progress = _rows(LEGACY / "source_review_progress_v1.csv")
    records = []

    for row in progress:
        dev_id = row["dev_id"]
        meta = manifest[dev_id]
        nulls = _legacy_null_fields(row)
        fields: dict[str, dict] = {}

        for legacy_field, new_field in LOSSLESS.items():
            if legacy_field in nulls:
                fields[new_field] = {
                    "state": "not_reported",
                    "value": None,
                    "provenance": "LEGACY_GOLD_LOSSLESS_MIGRATION",
                    "legacy_field": legacy_field,
                    "review_status": "SOURCE_REVIEWED_NOT_REPORTED",
                    "note": "Recorded as a final null by the legacy source review.",
                }
            else:
                fields[new_field] = {
                    "state": "needs_source_review",
                    "value": None,
                    "provenance": "LEGACY_GOLD_LOSSLESS_MIGRATION",
                    "legacy_field": legacy_field,
                    "review_status": "NEEDS_SOURCE_REVIEW",
                    "note": (
                        "The legacy record establishes that this slot was answered, "
                        "but the populated Gold artifact is unrecoverable, so the value "
                        "must be re-read from the frozen target anchor."
                    ),
                }

        for legacy_field, new_field in TYPED.items():
            answered = legacy_field not in nulls
            fields[new_field] = {
                "state": "needs_source_review" if answered else "not_reported",
                "value": None,
                "provenance": "LEGACY_GOLD_TYPED_MIGRATION",
                "legacy_field": legacy_field,
                "review_status": "NEEDS_SOURCE_REVIEW" if answered else "SOURCE_REVIEWED_NOT_REPORTED",
                "typed_migration_rule": (
                    "A legacy ee_percent becomes {kind: ee_percent, value: n}. No ee-to-er "
                    "conversion, and no configuration is inferred from an ee."
                ),
            }

        for legacy_field, new_field in NON_EQUIVALENT.items():
            fields[new_field] = {
                "state": "needs_source_review",
                "value": None,
                "provenance": "NON_EQUIVALENT_REQUIRES_REVIEW",
                "legacy_support": legacy_field,
                "review_status": "NEEDS_SOURCE_REVIEW",
                "note": (
                    "substrate_class is a class label and is never copied into substrate. "
                    "The substrate identity must be adjudicated from the target anchor."
                ),
            }

        for new_field in NEW_FIELDS:
            note = "This field does not exist in the legacy 8-field Gold and cannot be migrated."
            if new_field == "reaction":
                note += (
                    " SCHEMA_DEFINITION_GAP: FIELD_SCHEMA_V1 calls reaction a controlled "
                    "reaction type but defines no controlled vocabulary, so no Gold value "
                    "is written until the schema is amended explicitly."
                )
            fields[new_field] = {
                "state": "needs_source_review",
                "value": None,
                "provenance": "NOT_IN_LEGACY_GOLD",
                "review_status": "NEEDS_SOURCE_REVIEW",
                "schema_status": "SCHEMA_DEFINITION_GAP" if new_field == "reaction" else None,
                "note": note,
            }

        records.append(
            {
                "gold_case_id": dev_id,
                "paper_id": meta["combined_record_id"],
                "doi": meta["doi"],
                "metal": meta["metal"],
                "field_schema_version": FIELD_SCHEMA_VERSION,
                "stage": STAGE1_VERSION,
                "legacy_target_anchor": row["target_anchor_status"],
                "legacy_finalized_field_slots": int(row["finalized_field_slots"]),
                "legacy_final_null_fields": sorted(nulls),
                "legacy_review_status": row["review_status"],
                "legacy_source_review_note": row["public_note"],
                "source_scope": meta["source_basis"],
                "fields": fields,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(OUT_DIR / "development_gold_migration_stage1.jsonl")
    )
    args = parser.parse_args()

    records = build()
    assert len(records) == 12, f"expected 12 legacy cases, got {len(records)}"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")

    states = {}
    for record in records:
        for field in record["fields"].values():
            states[field["state"]] = states.get(field["state"], 0) + 1
    print(
        json.dumps(
            {
                "stage": STAGE1_VERSION,
                "cases": len(records),
                "field_slots": len(records) * 12,
                "state_counts": states,
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
