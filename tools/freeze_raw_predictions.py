"""Freeze a raw-prediction file before normalization or verification runs.

The scoring contract requires raw predictions to exist, and to be hashed, before
anything downstream may read them. This tool writes that freeze record and can
re-verify it later. It performs no scientific interpretation: it checks record
shape, version consistency and identity uniqueness, then hashes the bytes.
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
from modules.raw_llm_extractor_v2 import (  # noqa: E402
    EXTRACTION_VERSION,
    FIELD_NAMES,
    FIELD_SCHEMA,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)

FREEZE_VERSION = "raw-prediction-freeze-v1"
REQUIRED_KEYS = {
    "candidate_id",
    "source_artifact_id",
    "evidence_start",
    "evidence_end",
    "evidence_sha256",
    "values",
    "abstention_reasons",
    "model_name",
    "extraction_version",
    "prompt_version",
    "schema_version",
    "field_schema_version",
    "verification_status",
}


class RawFreezeError(RuntimeError):
    """Raised when a raw-prediction file cannot be frozen as given."""


def load_records(path: Path) -> list[dict]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise RawFreezeError(f"{path} contains no raw prediction records")
    return records


def check_records(records: list[dict]) -> dict:
    """Validate record shape and version consistency; return summary counts."""
    ids = Counter()
    models = Counter()
    for index, record in enumerate(records, start=1):
        missing = REQUIRED_KEYS - set(record)
        extra = set(record) - REQUIRED_KEYS
        if missing:
            raise RawFreezeError(f"record {index} is missing keys: {sorted(missing)}")
        if extra:
            raise RawFreezeError(f"record {index} has unexpected keys: {sorted(extra)}")
        if record["extraction_version"] != EXTRACTION_VERSION:
            raise RawFreezeError(
                f"record {index} was produced by {record['extraction_version']}, "
                f"expected {EXTRACTION_VERSION}"
            )
        if record["prompt_version"] != PROMPT_VERSION:
            raise RawFreezeError(f"record {index} has prompt {record['prompt_version']}")
        if record["schema_version"] != SCHEMA_VERSION:
            raise RawFreezeError(f"record {index} has schema {record['schema_version']}")
        if record["verification_status"] != "unverified":
            raise RawFreezeError(
                f"record {index} is already marked {record['verification_status']}; "
                "a raw freeze must happen before verification"
            )
        if set(record["values"]) != set(FIELD_NAMES):
            raise RawFreezeError(f"record {index} does not carry the frozen field set")
        for name, reason in record["abstention_reasons"].items():
            if record["values"].get(name) is not None:
                raise RawFreezeError(
                    f"record {index} gives an abstention reason for {name}, which has a value"
                )
            if reason is None:
                raise RawFreezeError(f"record {index} has an empty abstention reason for {name}")
        ids[record["candidate_id"]] += 1
        models[record["model_name"]] += 1

    duplicates = sorted(cid for cid, count in ids.items() if count > 1)
    if duplicates:
        raise RawFreezeError(f"duplicate candidate ids: {duplicates}")

    answered = sum(
        1
        for record in records
        for value in record["values"].values()
        if value is not None
    )
    return {
        "record_count": len(records),
        "distinct_candidate_ids": len(ids),
        "candidate_ids_sha256": candidate_ids_digest(ids),
        "models": dict(models),
        "answered_field_values": answered,
        "null_field_values": len(records) * len(FIELD_NAMES) - answered,
    }


def freeze(predictions: Path, out: Path) -> dict:
    records = load_records(predictions)
    summary = check_records(records)
    digest = hashlib.sha256(predictions.read_bytes()).hexdigest()
    manifest = {
        "freeze_version": FREEZE_VERSION,
        "artifact": predictions.name,
        "raw_predictions_path": predictions.name,
        "raw_predictions_sha256": digest,
        "extraction_version": EXTRACTION_VERSION,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "field_schema_version": FIELD_SCHEMA["schema_version"],
        "field_count": len(FIELD_NAMES),
        "frozen": True,
        "normalization_run": False,
        "verification_run": False,
        "scoring_run": False,
        "integrity_rule": (
            "Raw predictions are immutable after this freeze. Any edit voids the run; "
            "verification and scoring read this file and never write to it."
        ),
        **summary,
    }
    if out.exists():
        previous = json.loads(out.read_text(encoding="utf-8"))
        if previous.get("raw_predictions_sha256") != digest:
            raise RawFreezeError(
                f"{out} already freezes a different raw file "
                f"({previous.get('raw_predictions_sha256')}); refusing to overwrite"
            )
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify(predictions: Path, manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(predictions.read_bytes()).hexdigest()
    return digest == manifest.get("raw_predictions_sha256")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, help="raw prediction JSONL")
    parser.add_argument("--out", help="freeze manifest path (default: <predictions>.freeze.json)")
    parser.add_argument("--verify", action="store_true", help="verify against an existing manifest")
    args = parser.parse_args()

    predictions = Path(args.predictions)
    out = Path(args.out) if args.out else predictions.with_suffix(predictions.suffix + ".freeze.json")

    if args.verify:
        ok = verify(predictions, out)
        print(json.dumps({"verified": ok, "manifest": str(out)}, indent=2))
        return 0 if ok else 2

    manifest = freeze(predictions, out)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
