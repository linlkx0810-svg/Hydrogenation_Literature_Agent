"""Freeze the development Gold, or refuse to.

Mirrors `tools/freeze_raw_predictions.py`: it hashes the artifact, pins the
identity set and the schema version, and fails closed.

It refuses to set `frozen: true` while any slot is still `needs_source_review`.
An incomplete Gold gets a manifest with `frozen: false` and
`status: INCOMPLETE_NOT_FROZEN`, so nothing downstream can mistake a partial
Gold for a frozen one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.artifact_chain import candidate_ids_digest  # noqa: E402
from modules.raw_llm_extractor_v2 import FIELD_NAMES, FIELD_SCHEMA  # noqa: E402

FREEZE_VERSION = "development-gold-freeze-v1"
GOLD_VERSION = "development-gold-field-schema-v1"
SCORED_STATES = {"answered", "not_reported", "not_applicable"}
EXCLUDED_STATES = {"unresolved_reference", "needs_source_review"}
FORBIDDEN_PROVENANCE = {"AGENT_PREDICTION", "LLM_EXTRACTOR", "VERIFIER", "RESOLVER", "SCORER"}


class GoldFreezeError(RuntimeError):
    """Raised when the Gold cannot be frozen as given."""


def load_gold(path: Path) -> list[dict]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise GoldFreezeError(f"{path} contains no Gold records")
    return records


def check(records: list[dict]) -> dict:
    ids = Counter()
    states = Counter()
    for index, record in enumerate(records, start=1):
        if record.get("gold_version") != GOLD_VERSION:
            raise GoldFreezeError(f"record {index} has gold_version {record.get('gold_version')}")
        if record.get("field_schema_version") != FIELD_SCHEMA["schema_version"]:
            raise GoldFreezeError(f"record {index} has the wrong field schema version")
        if set(record["fields"]) != set(FIELD_NAMES):
            raise GoldFreezeError(f"record {index} does not carry all 12 schema fields")
        ids[record["gold_case_id"]] += 1
        for name, field in record["fields"].items():
            states[field["state"]] += 1
            provenance = str(field.get("provenance") or "").upper()
            if provenance in FORBIDDEN_PROVENANCE:
                raise GoldFreezeError(
                    f"record {index} field {name} has an Agent-prediction provenance"
                )
            if field["state"] == "answered":
                if field.get("value") in (None, ""):
                    raise GoldFreezeError(f"record {index} field {name}: answered without a value")
                if not field.get("source_locator") or not field.get("evidence_type"):
                    raise GoldFreezeError(
                        f"record {index} field {name}: answered without an evidence locator"
                    )
            if field["state"] == "not_reported" and field.get("value") is not None:
                raise GoldFreezeError(
                    f"record {index} field {name}: not_reported must not carry a value"
                )

    duplicates = sorted(cid for cid, count in ids.items() if count > 1)
    if duplicates:
        raise GoldFreezeError(f"duplicate gold case ids: {duplicates}")

    return {
        "case_count": len(records),
        "field_slot_count": len(records) * len(FIELD_NAMES),
        "candidate_ids_sha256": candidate_ids_digest(ids),
        "state_counts": dict(states),
        "scored_slots": sum(states[s] for s in SCORED_STATES),
        "excluded_slots": sum(states[s] for s in EXCLUDED_STATES),
    }


def freeze(gold_path: Path, out: Path) -> dict:
    records = load_gold(gold_path)
    summary = check(records)
    complete = summary["state_counts"].get("needs_source_review", 0) == 0
    digest = hashlib.sha256(Path(gold_path).read_bytes()).hexdigest()

    manifest = {
        "freeze_version": FREEZE_VERSION,
        "artifact": Path(gold_path).name,
        "sha256": digest,
        "gold_version": GOLD_VERSION,
        "field_schema_version": FIELD_SCHEMA["schema_version"],
        "frozen": complete,
        "status": "FROZEN" if complete else "INCOMPLETE_NOT_FROZEN",
        "lineage": "legacy Gold v1 (8 fields) + source adjudication -> development Gold FIELD_SCHEMA_V1",
        "legacy_gold_v1_sha256": "990799475b89051a2013c77fbcbb3128b3af278817dd67ba008ee93109c25cc5",
        "legacy_gold_v1_artifact_recovered": False,
        "development_only": True,
        "blind_eligible": False,
        "integrity_rule": (
            "This Gold is for development evaluation only. It is never a blind benchmark, "
            "and a slot marked needs_source_review or unresolved_reference is excluded from "
            "every accuracy denominator."
        ),
        **summary,
    }
    if out.exists():
        previous = json.loads(out.read_text(encoding="utf-8"))
        if previous.get("frozen") and previous.get("sha256") != digest:
            raise GoldFreezeError(
                f"{out} already freezes a different Gold ({previous.get('sha256')}); "
                "refusing to overwrite a frozen manifest"
            )
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(gold_path: Path, manifest_path: Path) -> bool:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(gold_path).read_bytes()).hexdigest()
    return digest == manifest.get("sha256")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--out")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    gold = Path(args.gold)
    out = Path(args.out) if args.out else gold.with_suffix(gold.suffix + ".freeze.json")

    if args.verify:
        ok = verify(gold, out)
        print(json.dumps({"verified": ok, "manifest": str(out)}, indent=2))
        return 0 if ok else 2

    manifest = freeze(gold, out)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["frozen"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
