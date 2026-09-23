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
from modules.field_verifiers import (  # noqa: E402
    CHECKED_FIELDS,
    COVERAGE_CONTRACT,
    FIELD_MODES,
    NOT_CHECKED,
    NOT_VERIFIABLE,
    verify_extended_field,
)
from modules.prediction_normalizer import (  # noqa: E402
    NORMALIZER_VERSION,
    normalize_record,
)
from modules.raw_llm_extractor_v2 import FIELD_NAMES  # noqa: E402
from modules.reaction_candidate_extraction import ReactionCandidate  # noqa: E402

CHAIN_VERSION = "agent-v1-chain-runner-v2"
VERIFIER_VERSION = COVERAGE_CONTRACT["verifier_version"]

FINAL_ACTION = {
    "supported": "retain",
    "partial": "flag_review",
    "unsupported": "suppress",
    "unresolved": "suppress",
    "ambiguous": "suppress",
    NOT_VERIFIABLE: "flag_review",
    NOT_CHECKED: "pass_through_unchecked",
}

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
    """One row per FIELD_SCHEMA_V1 field, under the verifier coverage contract.

    Each row keeps the raw value and raw state next to the canonical value and
    the verdict, so nothing downstream has to guess which layer a number came
    from. `final_action` says what happens to the value in the final stream.
    """
    legacy_to_schema = {legacy: field for legacy, (field, _) in _LEGACY_FIELD_MAP.items()}
    verdicts: dict[str, dict] = {}
    for result in verification.fields:
        schema_name = legacy_to_schema.get(result.field, result.field)
        verdicts[schema_name] = {
            "status": result.status,
            "reason": result.reason,
            "evidence_text": result.evidence_text,
            "canonical_id": result.canonical_id,
            "canonical_name": result.canonical_name,
        }

    evidence = record and normalized and verification.fields
    evidence_text = verification.fields[0].evidence_text if verification.fields else ""
    raw_values = record["values"]
    raw_reasons = record.get("abstention_reasons", {})

    rows = []
    for name in FIELD_NAMES:
        raw_value = raw_values.get(name)
        raw_state = "answered" if raw_value is not None else (
            raw_reasons.get(name) or "not_reported"
        )
        normalization = normalized.fields.get(name)
        canonical_value = normalized.canonical(name)
        mode = FIELD_MODES.get(name, NOT_CHECKED)
        checked = CHECKED_FIELDS.get(name, False)

        if raw_value is None:
            status = NOT_VERIFIABLE if checked else NOT_CHECKED
            reason = "No raw value to verify."
        elif name in verdicts:
            status = verdicts[name]["status"]
            reason = verdicts[name]["reason"]
        elif name in ("catalyst", "product", "stereochemical_outcome"):
            verdict = verify_extended_field(name, canonical_value, evidence_text)
            status, reason = verdict.status, verdict.reason
        elif name == "ee_or_er" and isinstance(raw_value, dict) and raw_value.get("kind") != "ee_percent":
            status = NOT_VERIFIABLE
            reason = "An er ratio is not converted to ee by this check."
        else:
            status = NOT_CHECKED
            reason = "No verifier exists for this field in v1."

        rows.append(
            {
                "field": name,
                "coverage_mode": mode,
                "raw_value": raw_value,
                "raw_state": raw_state,
                "canonical_value": canonical_value,
                "normalization_status": (
                    normalization.normalization_status if normalization else None
                ),
                "verification_status": status,
                "reason": reason,
                "checked_by_verifier": bool(checked and raw_value is not None),
                "final_action": FINAL_ACTION.get(status, "flag_review"),
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
                "verifier_version": VERIFIER_VERSION,
                "verifier_coverage_contract": COVERAGE_CONTRACT["contract_version"],
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
        "verifier_version": VERIFIER_VERSION,
        "verifier_coverage_contract": COVERAGE_CONTRACT["contract_version"],
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
