"""Contract tests for llm-extractor-v2, the formal Raw LLM stage."""
import json

import pytest

from modules.raw_llm_extractor_v2 import (
    ABSTENTION_REASONS,
    EXTRACTION_VERSION,
    FIELD_NAMES,
    PROMPT_VERSION,
    RESPONSE_SCHEMA,
    SCHEMA_VERSION,
    RawResponseSchemaError,
    ReplayJSONProvider,
    build_request,
    extract_reaction_chunk,
    validate_response,
)

EVIDENCE = (
    "Hydrogenation of acetophenone with H2 (50 bar) in MeOH at 60 C for 12 h "
    "using BINAP gave the alcohol in 95% yield and 98% ee."
)


def _payload(**overrides):
    values = {name: None for name in FIELD_NAMES}
    values.update(
        {
            "reaction": "asymmetric hydrogenation of a ketone",
            "ligand": "BINAP",
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
    reasons = {
        name: "not_reported" for name in FIELD_NAMES if values[name] is None
    }
    return {**values, "abstention_reasons": reasons}


def test_field_set_comes_from_the_frozen_field_schema():
    assert len(FIELD_NAMES) == 12
    assert "conditions" not in FIELD_NAMES
    assert {"h2_pressure", "temperature", "reaction_time", "solvent"} <= set(FIELD_NAMES)
    assert {"ee_or_er", "stereochemical_outcome"} <= set(FIELD_NAMES)
    assert set(RESPONSE_SCHEMA["required"]) == set(FIELD_NAMES) | {"abstention_reasons"}
    assert RESPONSE_SCHEMA["additionalProperties"] is False


def test_versions_are_v2_and_distinct_from_the_legacy_extractor():
    from modules import llm_extractor as legacy

    assert (EXTRACTION_VERSION, PROMPT_VERSION) == ("llm-extractor-v2", "llm-extractor-prompt-v2")
    assert SCHEMA_VERSION == "raw-extraction-schema-v2"
    assert legacy.EXTRACTION_VERSION == "llm-extractor-v1"
    assert set(legacy.FIELD_NAMES) != set(FIELD_NAMES)


def test_request_carries_only_the_evidence_chunk():
    request = build_request(EVIDENCE)
    assert EVIDENCE in request.user_prompt
    assert request.response_schema is RESPONSE_SCHEMA
    assert request.prompt_version == PROMPT_VERSION
    for leak in ("rule-baseline", "confidence", "gold", "expected"):
        assert leak not in request.user_prompt.lower()
    with pytest.raises(ValueError):
        build_request("   ")


def test_valid_response_round_trips_with_provenance():
    provider = ReplayJSONProvider(json.dumps(_payload()), model_name="gpt-5.6-sol")
    record = extract_reaction_chunk(
        EVIDENCE, provider, candidate_id="rxn-0001",
        source_artifact_id="DEV-SAMPLE", evidence_start=10,
    )
    assert record.values["ligand"] == "BINAP"
    assert record.values["ee_or_er"] == {"value": 98.0, "kind": "ee_percent"}
    assert record.abstention_reasons["catalyst"] == "not_reported"
    assert record.verification_status == "unverified"
    assert record.extraction_version == EXTRACTION_VERSION
    assert record.evidence_start == 10 and record.evidence_end == 10 + len(EVIDENCE)
    assert len(record.evidence_sha256) == 64
    assert set(record.to_dict()["values"]) == set(FIELD_NAMES)


def test_extra_and_missing_keys_are_rejected():
    payload = _payload()
    payload["ee_percent"] = 98.0
    with pytest.raises(RawResponseSchemaError, match="disallowed keys"):
        validate_response(payload)
    payload = _payload()
    del payload["solvent"]
    with pytest.raises(RawResponseSchemaError, match="missing required keys"):
        validate_response(payload)


def test_numeric_bounds_and_types_are_not_coerced():
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(**{"yield": 140.0}))
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(temperature=-300.0))
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(h2_pressure="50 bar"))
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(solvent=""))


def test_selectivity_object_requires_value_and_kind():
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(ee_or_er={"value": 98.0, "kind": None}))
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(ee_or_er={"value": 98.0, "kind": "percent"}))
    with pytest.raises(RawResponseSchemaError):
        validate_response(_payload(ee_or_er={"value": 140.0, "kind": "ee_percent"}))
    values, _ = validate_response(_payload(ee_or_er={"value": 95.5, "kind": "er_ratio"}))
    assert values["ee_or_er"] == {"value": 95.5, "kind": "er_ratio"}


def test_every_null_needs_an_abstention_reason_and_no_others():
    payload = _payload()
    payload["abstention_reasons"].pop("catalyst")
    with pytest.raises(RawResponseSchemaError, match="without an abstention reason"):
        validate_response(payload)

    payload = _payload()
    payload["abstention_reasons"]["ligand"] = "not_reported"
    with pytest.raises(RawResponseSchemaError, match="carries a value"):
        validate_response(payload)

    payload = _payload()
    payload["abstention_reasons"]["catalyst"] = "probably_missing"
    with pytest.raises(RawResponseSchemaError, match="abstention reason"):
        validate_response(payload)

    assert set(ABSTENTION_REASONS) == {
        "not_reported", "not_applicable", "unresolved", "ambiguous"
    }


def test_malformed_provider_output_raises_instead_of_being_repaired():
    with pytest.raises(RawResponseSchemaError, match="Malformed"):
        validate_response("{not json")
    with pytest.raises(RawResponseSchemaError, match="single object"):
        validate_response("[]")
