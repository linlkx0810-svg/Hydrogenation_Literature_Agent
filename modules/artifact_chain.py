"""Fail-closed loading of the frozen raw artifact.

Every stage after the raw freeze reads the raw predictions through this module.
It verifies, before returning a single record:

1. the raw file hash against the freeze manifest;
2. the candidate-id set against the manifest digest;
3. the field schema version;
4. the extractor and prompt versions.

Any mismatch raises. Nothing downstream is allowed to proceed on an artifact it
cannot prove is the one that was frozen.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from modules.raw_llm_extractor_v2 import (
    EXTRACTION_VERSION,
    FIELD_SCHEMA,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)


class FrozenArtifactError(RuntimeError):
    """Raised when a frozen artifact fails its integrity or version checks."""


def candidate_ids_digest(candidate_ids) -> str:
    """Order-independent digest of the candidate-id set."""
    joined = "\n".join(sorted(candidate_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_frozen_raw(predictions: Path, manifest_path: Path) -> tuple[list[dict], dict]:
    """Return (records, manifest) only when every integrity check passes."""
    predictions, manifest_path = Path(predictions), Path(manifest_path)
    if not predictions.exists():
        raise FrozenArtifactError(f"raw prediction file not found: {predictions}")
    if not manifest_path.exists():
        raise FrozenArtifactError(
            f"freeze manifest not found: {manifest_path}; run tools/freeze_raw_predictions.py first"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("frozen"):
        raise FrozenArtifactError(f"{manifest_path} does not declare frozen=true")

    digest = hashlib.sha256(predictions.read_bytes()).hexdigest()
    if digest != manifest.get("raw_predictions_sha256"):
        raise FrozenArtifactError(
            "raw prediction file does not match its freeze manifest; the run is void"
        )

    records = _read_jsonl(predictions)
    if len(records) != manifest.get("record_count"):
        raise FrozenArtifactError(
            f"record count {len(records)} does not match the frozen count {manifest.get('record_count')}"
        )

    ids = [record["candidate_id"] for record in records]
    if len(set(ids)) != len(ids):
        raise FrozenArtifactError("duplicate candidate ids in the frozen raw artifact")
    if candidate_ids_digest(ids) != manifest.get("candidate_ids_sha256"):
        raise FrozenArtifactError("candidate id set does not match the freeze manifest")

    if manifest.get("field_schema_version") != FIELD_SCHEMA["schema_version"]:
        raise FrozenArtifactError(
            f"field schema version {manifest.get('field_schema_version')} is not "
            f"{FIELD_SCHEMA['schema_version']}"
        )
    if manifest.get("extraction_version") != EXTRACTION_VERSION:
        raise FrozenArtifactError(
            f"extractor version {manifest.get('extraction_version')} is not {EXTRACTION_VERSION}"
        )
    if manifest.get("prompt_version") != PROMPT_VERSION:
        raise FrozenArtifactError(
            f"prompt version {manifest.get('prompt_version')} is not {PROMPT_VERSION}"
        )
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FrozenArtifactError(
            f"response schema version {manifest.get('schema_version')} is not {SCHEMA_VERSION}"
        )

    for record in records:
        if record.get("verification_status") != "unverified":
            raise FrozenArtifactError(
                f"{record.get('candidate_id')} is marked {record.get('verification_status')} "
                "inside the raw artifact; verification state belongs in a downstream artifact"
            )
        for forbidden in ("canonical_values", "verification", "score", "gold", "correct"):
            if forbidden in record:
                raise FrozenArtifactError(
                    f"{record.get('candidate_id')} carries downstream key '{forbidden}'; "
                    "the raw artifact must stay immutable and stage-pure"
                )

    return records, manifest
