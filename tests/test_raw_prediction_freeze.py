"""Tests for the raw-prediction freeze: raw output must exist and be hashed first."""
import json

import pytest

from modules.raw_llm_extractor_v2 import (
    FIELD_NAMES,
    ReplayJSONProvider,
    extract_reaction_chunk,
)
from tools.freeze_raw_predictions import RawFreezeError, check_records, freeze, verify

EVIDENCE = "Hydrogenation with H2 (50 bar) in MeOH gave 95% yield and 98% ee."


def _record(candidate_id="rxn-0001"):
    values = {name: None for name in FIELD_NAMES}
    values.update({"solvent": "MeOH", "h2_pressure": 50.0, "yield": 95.0})
    payload = {
        **values,
        "abstention_reasons": {
            name: "not_reported" for name in FIELD_NAMES if values[name] is None
        },
    }
    provider = ReplayJSONProvider(json.dumps(payload), model_name="gpt-5.6-sol")
    return extract_reaction_chunk(
        EVIDENCE, provider, candidate_id=candidate_id, source_artifact_id="DEV-SAMPLE"
    ).to_dict()


def _write(tmp_path, records, name="raw.jsonl"):
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


def test_freeze_records_hash_counts_and_pipeline_state(tmp_path):
    path = _write(tmp_path, [_record("rxn-0001"), _record("rxn-0002")])
    manifest = freeze(path, tmp_path / "raw.freeze.json")
    assert manifest["record_count"] == 2
    assert manifest["distinct_candidate_ids"] == 2
    assert len(manifest["raw_predictions_sha256"]) == 64
    assert manifest["extraction_version"] == "llm-extractor-v2"
    assert manifest["field_count"] == 12
    for stage in ("normalization_run", "verification_run", "scoring_run"):
        assert manifest[stage] is False
    assert verify(path, tmp_path / "raw.freeze.json") is True


def test_edited_raw_file_fails_verification(tmp_path):
    path = _write(tmp_path, [_record()])
    freeze(path, tmp_path / "raw.freeze.json")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["values"]["yield"] = 99.0
    _write(tmp_path, rows)
    assert verify(path, tmp_path / "raw.freeze.json") is False


def test_refuses_to_overwrite_a_freeze_with_different_content(tmp_path):
    first = _write(tmp_path, [_record("rxn-0001")], "a.jsonl")
    out = tmp_path / "shared.freeze.json"
    freeze(first, out)
    second = _write(tmp_path, [_record("rxn-0002")], "b.jsonl")
    with pytest.raises(RawFreezeError, match="refusing to overwrite"):
        freeze(second, out)


def test_duplicate_ids_and_already_verified_records_are_rejected():
    with pytest.raises(RawFreezeError, match="duplicate candidate ids"):
        check_records([_record("rxn-0001"), _record("rxn-0001")])

    record = _record()
    record["verification_status"] = "accepted"
    with pytest.raises(RawFreezeError, match="before verification"):
        check_records([record])


def test_version_and_shape_drift_is_rejected():
    record = _record()
    record["extraction_version"] = "llm-extractor-v1"
    with pytest.raises(RawFreezeError, match="expected llm-extractor-v2"):
        check_records([record])

    record = _record()
    record["values"].pop("solvent")
    with pytest.raises(RawFreezeError, match="frozen field set"):
        check_records([record])

    record = _record()
    record["abstention_reasons"]["solvent"] = "not_reported"
    with pytest.raises(RawFreezeError, match="which has a value"):
        check_records([record])
