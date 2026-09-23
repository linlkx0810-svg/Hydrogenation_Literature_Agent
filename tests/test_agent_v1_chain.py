"""Chain tests: frozen raw immutability, fail-closed loading, normalization, scoring."""
import hashlib
import json

import pytest

from modules.artifact_chain import FrozenArtifactError, candidate_ids_digest, load_frozen_raw
from modules.prediction_normalizer import NORMALIZER_VERSION, normalize_record
from modules.raw_llm_extractor_v2 import FIELD_NAMES, ReplayJSONProvider, extract_reaction_chunk
from tools import run_chain, score_agent_v1
from tools.freeze_raw_predictions import freeze

SOURCE = (
    "SEGPHOS (L3) was selected as the ligand. "
    "Using L3, hydrogenation of acetophenone with H2 (50 bar) in MeOH at 60 C for 12 h "
    "gave the alcohol in 95% yield and 98% ee."
)


def _raw_record(candidate_id="rxn-0001", **overrides):
    values = {name: None for name in FIELD_NAMES}
    values.update(
        {
            "ligand": "L3",
            "substrate": "acetophenone",
            "h2_pressure": 50.0,
            "temperature": 60.0,
            "reaction_time": 12.0,
            "solvent": "MeOH",
            "yield": 95.0,
            "ee_or_er": {"value": 98.0, "kind": "ee_percent"},
        }
    )
    values.update(overrides)
    payload = {
        **values,
        "abstention_reasons": {
            name: "not_reported" for name in FIELD_NAMES if values[name] is None
        },
    }
    provider = ReplayJSONProvider(json.dumps(payload), model_name="replay-json")
    start = SOURCE.index("Using L3")
    return extract_reaction_chunk(
        SOURCE[start:],
        provider,
        candidate_id=candidate_id,
        source_artifact_id="TEST",
        evidence_start=start,
    ).to_dict()


def _write_chain(tmp_path, records=None):
    records = records or [_raw_record()]
    raw = tmp_path / "raw_predictions.jsonl"
    raw.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    manifest = tmp_path / "raw_predictions.freeze.json"
    freeze(raw, manifest)
    source = tmp_path / "source.txt"
    source.write_text(SOURCE, encoding="utf-8")
    return raw, manifest, source


def _rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_freeze_manifest_carries_identity_and_schema_pins(tmp_path):
    raw, manifest_path, _ = _write_chain(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["frozen"] is True
    assert manifest["artifact"] == "raw_predictions.jsonl"
    assert manifest["candidate_ids_sha256"] == candidate_ids_digest(["rxn-0001"])
    assert manifest["field_schema_version"] == "agent-v1-field-schema-v1"
    records, _ = load_frozen_raw(raw, manifest_path)
    assert len(records) == 1


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("raw_predictions_sha256", "0" * 64, "does not match"),
        ("candidate_ids_sha256", "0" * 64, "candidate id set"),
        ("field_schema_version", "other", "field schema version"),
        ("extraction_version", "llm-extractor-v1", "extractor version"),
        ("prompt_version", "llm-extractor-prompt-v1", "prompt version"),
        ("schema_version", "raw-extraction-schema-v1", "response schema version"),
        ("frozen", False, "frozen=true"),
        ("record_count", 99, "record count"),
    ],
)
def test_loader_fails_closed_on_every_pin(tmp_path, key, value, message):
    raw, manifest_path, _ = _write_chain(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[key] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(FrozenArtifactError, match=message):
        load_frozen_raw(raw, manifest_path)


def test_loader_rejects_downstream_state_inside_the_raw_artifact(tmp_path):
    record = _raw_record()
    record["verification_status"] = "accepted"
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps(record) + "\n", encoding="utf-8")
    manifest_path = tmp_path / "freeze.json"
    manifest_path.write_text(
        json.dumps(
            {
                "frozen": True,
                "raw_predictions_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "record_count": 1,
                "candidate_ids_sha256": candidate_ids_digest(["rxn-0001"]),
                "field_schema_version": "agent-v1-field-schema-v1",
                "extraction_version": "llm-extractor-v2",
                "prompt_version": "llm-extractor-prompt-v2",
                "schema_version": "raw-extraction-schema-v2",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FrozenArtifactError, match="verification state belongs"):
        load_frozen_raw(raw, manifest_path)


def test_normalizer_keeps_raw_next_to_canonical_and_only_ligand_is_active():
    normalized = normalize_record(_raw_record(), SOURCE)
    ligand = normalized.fields["ligand"]
    assert ligand.raw_value == "L3"
    assert ligand.canonical_value == "SEGPHOS"
    assert ligand.normalization_status == "resolved"
    solvent = normalized.fields["solvent"]
    assert solvent.raw_value == solvent.canonical_value == "MeOH"
    assert solvent.normalization_method == "PASS_THROUGH_V1"
    assert normalized.normalizer_version == NORMALIZER_VERSION
    assert normalized.active_fields == ("ligand",)


def test_undefined_alias_stays_unresolved_and_is_not_guessed():
    normalized = normalize_record(
        _raw_record(ligand="L9"), "Using L9, the reaction gave 90% yield."
    )
    assert normalized.fields["ligand"].normalization_status == "unresolved"
    assert normalized.fields["ligand"].canonical_value is None


def test_chain_run_leaves_the_raw_artifact_byte_identical(tmp_path):
    raw, manifest_path, source = _write_chain(tmp_path)
    before = raw.read_bytes()
    report = run_chain.run(raw, manifest_path, source, tmp_path / "out")
    assert raw.read_bytes() == before
    assert report["raw_artifact_unmodified"] is True

    normalized = _rows(tmp_path / "out" / "normalized_predictions.jsonl")
    verified = _rows(tmp_path / "out" / "verified_predictions.jsonl")
    assert normalized[0]["fields"]["ligand"]["raw_value"] == "L3"
    assert normalized[0]["fields"]["ligand"]["canonical_value"] == "SEGPHOS"
    assert {f["field"] for f in verified[0]["fields"]} == set(FIELD_NAMES)
    row = {f["field"]: f for f in verified[0]["fields"]}
    assert row["reaction"]["verification_status"] == "not_checked_v1"
    assert row["reaction"]["final_action"] == "pass_through_unchecked"
    assert row["ligand"]["raw_value"] == "L3"
    assert row["ligand"]["canonical_value"] == "SEGPHOS"
    assert row["ligand"]["raw_state"] == "answered"


def test_chain_refuses_a_source_that_does_not_reproduce_the_frozen_evidence(tmp_path):
    raw, manifest_path, source = _write_chain(tmp_path)
    source.write_text(SOURCE.replace("50 bar", "60 bar"), encoding="utf-8")
    with pytest.raises(FrozenArtifactError, match="does not reproduce"):
        run_chain.run(raw, manifest_path, source, tmp_path / "out")


def _gold(candidate_id="rxn-0001", **overrides):
    fields = {
        "ligand": "L3",
        "substrate": "acetophenone",
        "h2_pressure": 50.0,
        "temperature": 60.0,
        "reaction_time": 12.0,
        "solvent": "MeOH",
        "yield": 95.0,
        "ee_or_er": {"value": 98.0, "kind": "ee_percent"},
        "reaction": {"value": None, "state": "not_reported"},
        "catalyst": {"value": None, "state": "not_reported"},
        "product": {"value": None, "state": "not_reported"},
        "stereochemical_outcome": {"value": None, "state": "not_applicable"},
    }
    fields.update(overrides)
    return {"candidate_id": candidate_id, "fields": fields}


def test_scorer_joins_on_candidate_id_not_position(tmp_path):
    raw, manifest_path, source = _write_chain(
        tmp_path, [_raw_record("rxn-0001"), _raw_record("rxn-0002", solvent="THF")]
    )
    run_chain.run(raw, manifest_path, source, tmp_path / "out")
    verified = _rows(tmp_path / "out" / "verified_predictions.jsonl")
    records, _ = load_frozen_raw(raw, manifest_path)

    gold = [_gold("rxn-0002", solvent="THF"), _gold("rxn-0001")]
    report = score_agent_v1.score(records, list(reversed(verified)), gold)
    assert report["n_chunks_scored"] == 2
    assert report["a_raw_extractor"]["incorrect"] == 0
    assert report["a_raw_extractor"]["correct"] == 16


def test_scorer_state_semantics_and_verifier_reporting(tmp_path):
    raw, manifest_path, source = _write_chain(tmp_path)
    run_chain.run(raw, manifest_path, source, tmp_path / "out")
    verified = _rows(tmp_path / "out" / "verified_predictions.jsonl")
    records, _ = load_frozen_raw(raw, manifest_path)

    report = score_agent_v1.score(records, verified, [_gold()])
    assert report["a_raw_extractor"]["not_applicable_excluded"] == 1
    assert report["a_raw_extractor"]["correct"] == 8
    assert report["a_raw_extractor"]["n_pairs"] == 11
    assert report["b_verifier_checked_subset"]["verifier_checked_units"] <= report[
        "b_verifier_checked_subset"]["verifier_eligible_units"]
    assert report["b_verifier_checked_subset"]["correct_value_retention"] == 1.0
    assert report["c_unchecked_and_unverifiable"]["not_checked_v1_by_field"] == {"reaction": 1}
    assert report["join_key"] == "candidate_id"

    wrong = _gold()
    wrong["fields"]["yield"] = 42.0
    report = score_agent_v1.score(records, verified, [wrong])
    assert report["a_raw_extractor"]["incorrect"] == 1
    assert report["d_final_stream"]["final_incorrect"] == 1, (
        "the verifier found the value supported by the evidence, so it must not be "
        "silently withheld or corrected"
    )
    assert report["b_verifier_checked_subset"]["n_raw_incorrect_in_subset"] == 1


def test_unresolved_is_never_counted_as_incorrect(tmp_path):
    raw, manifest_path, source = _write_chain(tmp_path, [_raw_record(ligand=None)])
    records, _ = load_frozen_raw(raw, manifest_path)
    run_chain.run(raw, manifest_path, source, tmp_path / "out")
    verified = _rows(tmp_path / "out" / "verified_predictions.jsonl")

    record = records[0]
    record["abstention_reasons"]["ligand"] = "unresolved"
    report = score_agent_v1.score([record], verified, [_gold()])
    assert report["a_raw_extractor"]["unresolved"] == 1
    assert report["a_raw_extractor"]["incorrect"] == 0
    assert report["a_raw_extractor"]["miss"] == 0
