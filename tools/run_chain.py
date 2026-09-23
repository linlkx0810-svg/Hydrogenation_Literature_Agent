"""Run the post-freeze half of the Agent v1.0 chain.

    frozen raw prediction  ->  normalization  ->  evidence verifier  ->  verified prediction

The raw artifact is read through `modules.artifact_chain`, which fails closed on
any hash, identity, schema or version mismatch. Nothing here writes back to the
raw file: each stage emits its own artifact, and the artifacts are joined by
`candidate_id`, never by list position.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.artifact_chain import FrozenArtifactError, load_frozen_raw  # noqa: E402
from modules.extraction_verifier import verify_candidate  # noqa: E402
from modules.prediction_normalizer import (  # noqa: E402
    NORMALIZER_VERSION,
    normalize_record,
)
from modules.raw_llm_extractor_v2 import FIELD_NAMES  # noqa: E402
from modules.reaction_candidate_extraction import ReactionCandidate  # noqa: E402

CHAIN_VERSION = "agent-v1-chain-runner-v1"
NOT_CHECKED = "not_checked_v1"

_LEGACY_FIELD_MAP = {
    "ee_percent": ("ee_or_er", "ee"),
    "yield_percent": ("yield", None),
    "h2_pressure_bar": ("h2_pressure", None),
    "temperature_c": ("temperature", None),
    "reaction_time_h": ("reaction_time", None),
    "solvent": ("solvent", None),
    "ligand": ("ligand", None),
    "substrate_class": ("substrate", None),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _candidate_from_normalized(record, normalized) -> ReactionCandidate:
    """Adapt a normalized record to the evidence verifier's candidate shape.

    The verifier checks values against the bound evidence window using the
    deterministic patterns of the candidate builder, so it needs the legacy
    numeric field names. Only canonical (post-normalization) values are passed;
    the raw values stay in their own artifact.
    """
    values = {}
    for legacy, (field, part) in _LEGACY_FIELD_MAP.items():
        value = normalized.canonical(field)
        if part == "ee" and isinstance(value, dict):
            value = value.get("value") if value.get("kind") == "ee_percent" else None
        values[legacy] = value
    return ReactionCandidate(
        candidate_id=record["candidate_id"],
        confidence=0.0,
        evidence_text="",  # filled by the caller from the source text
        evidence_start=record["evidence_start"],
        evidence_end=record["evidence_end"],
        extraction_method=record["extraction_version"],
        **values,
    )


def _verified_fields(verification, record, normalized) -> list[dict]:
    """Re-express verification outcomes in FIELD_SCHEMA_V1 field names.

    `evidence-verifier-v1` checks only the eight legacy quantities. The fields it
    has no check for are reported as `not_checked_v1` rather than being left out,
    so a reader can see the verifier's coverage instead of inferring it.
    """
    legacy_to_schema = {legacy: field for legacy, (field, _) in _LEGACY_FIELD_MAP.items()}
    checked: dict[str, dict] = {}
    for result in verification.fields:
        schema_name = legacy_to_schema.get(result.field, result.field)
        entry = result.to_dict()
        entry["field"] = schema_name
        entry["checked_by_verifier"] = True
        checked[schema_name] = entry

    rows = []
    for name in FIELD_NAMES:
        if name in checked:
            rows.append(checked[name])
            continue
        rows.append(
            {
                "field": name,
                "value": normalized.canonical(name),
                "status": NOT_CHECKED,
                "reason": "evidence-verifier-v1 implements no evidence check for this field.",
                "evidence_text": "",
                "canonical_id": None,
                "canonical_name": None,
                "checked_by_verifier": False,
            }
        )
    return rows


def run(raw_path: Path, freeze_path: Path, source_path: Path, out_dir: Path) -> dict:
    records, manifest = load_frozen_raw(raw_path, freeze_path)
    source_text = Path(source_path).read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)

    normalized_rows, verified_rows = [], []
    decisions = {"accept": 0, "review": 0, "reject": 0}

    for record in records:
        evidence = source_text[record["evidence_start"]: record["evidence_end"]]
        if hashlib.sha256(evidence.encode("utf-8")).hexdigest() != record["evidence_sha256"]:
            raise FrozenArtifactError(
                f"{record['candidate_id']}: source text does not reproduce the frozen "
                "evidence chunk; the source artifact is not the one that was extracted"
            )

        normalized = normalize_record(record, source_text)
        normalized_rows.append(normalized.to_dict())

        candidate = _candidate_from_normalized(record, normalized)
        candidate.evidence_text = evidence
        verification = verify_candidate(candidate, source_text, normalized)
        decisions[verification.overall_status] = decisions.get(verification.overall_status, 0) + 1

        verified_rows.append(
            {
                "candidate_id": record["candidate_id"],
                "source_artifact_id": record["source_artifact_id"],
                "raw_predictions_sha256": manifest["raw_predictions_sha256"],
                "normalizer_version": NORMALIZER_VERSION,
                "verifier_version": "evidence-verifier-v1",
                "evidence_integrity": verification.evidence_integrity,
                "overall_status": verification.overall_status,
                "fields": _verified_fields(verification, record, normalized),
            }
        )

    normalized_path = out_dir / "normalized_predictions.jsonl"
    verified_path = out_dir / "verified_predictions.jsonl"
    normalized_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in normalized_rows) + "\n",
        encoding="utf-8",
    )
    verified_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in verified_rows) + "\n",
        encoding="utf-8",
    )

    report = {
        "chain_version": CHAIN_VERSION,
        "raw_predictions_sha256": manifest["raw_predictions_sha256"],
        "raw_artifact_unmodified": _sha(raw_path) == manifest["raw_predictions_sha256"],
        "candidate_ids_sha256": manifest["candidate_ids_sha256"],
        "record_count": len(records),
        "normalizer_version": NORMALIZER_VERSION,
        "verifier_version": "evidence-verifier-v1",
        "normalized_predictions": normalized_path.name,
        "normalized_predictions_sha256": _sha(normalized_path),
        "verified_predictions": verified_path.name,
        "verified_predictions_sha256": _sha(verified_path),
        "candidate_decisions": decisions,
    }
    (out_dir / "chain_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, help="frozen raw prediction JSONL")
    parser.add_argument("--freeze", required=True, help="raw freeze manifest JSON")
    parser.add_argument("--source", required=True, help="source text used for extraction")
    parser.add_argument("--out-dir", required=True, help="directory for chain artifacts")
    args = parser.parse_args()

    try:
        report = run(Path(args.raw), Path(args.freeze), Path(args.source), Path(args.out_dir))
    except FrozenArtifactError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
