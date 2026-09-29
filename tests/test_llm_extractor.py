import json

import pytest

from modules.llm_extractor import (
    FIELD_NAMES,
    EXTRACTION_VERSION,
    LLMResponseSchemaError,
    PROMPT_VERSION,
    ReplayJSONProvider,
    build_request,
    extract_reaction_chunk,
    validate_response,
)
from modules.reaction_candidate_extraction import extract_reaction_candidates


def payload(**overrides):
    data = {field: None for field in FIELD_NAMES}
    data.update(overrides)
    return data


def test_missing_ligand_is_preserved_as_abstention():
    provider = ReplayJSONProvider(
        payload(ee_percent=96.0, yield_percent=91.0, ligand=None),
        model_name="test-model",
    )
    result = extract_reaction_chunk(
        "The product was obtained in 91% yield and 96% ee.", provider
    )
    assert result.candidate.ee_percent == 96.0
    assert result.candidate.ligand is None
    assert "ligand" in result.unresolved_fields
    assert result.verification_status == "unverified"


def test_missing_pressure_is_preserved_as_null():
    provider = ReplayJSONProvider(payload(ee_percent=98.0, h2_pressure_bar=None))
    result = extract_reaction_chunk("The reaction gave 98% ee.", provider)
    assert result.candidate.h2_pressure_bar is None
    assert "h2_pressure_bar" in result.unresolved_fields


def test_multiple_ee_values_can_be_explicitly_abstained():
    evidence = "Entry A gave 91% ee, while entry B gave 97% ee; the target entry is unclear."
    provider = ReplayJSONProvider(payload(ee_percent=None))
    result = extract_reaction_chunk(evidence, provider)
    assert result.candidate.ee_percent is None
    assert "ee_percent" in result.unresolved_fields
    assert "multiple candidate values" in provider.last_request.system_prompt


def test_conflicting_values_can_be_left_unresolved():
    evidence = "One statement gives 20 bar H2, but another gives 30 bar H2 for the same label."
    provider = ReplayJSONProvider(payload(h2_pressure_bar=None))
    result = extract_reaction_chunk(evidence, provider)
    assert result.candidate.h2_pressure_bar is None
    assert "conflicting" in provider.last_request.system_prompt.lower()


def test_no_reaction_data_allows_complete_abstention():
    provider = ReplayJSONProvider(payload())
    result = extract_reaction_chunk("This paragraph discusses only background chemistry.", provider)
    assert set(result.unresolved_fields) == set(FIELD_NAMES)
    assert all(result.to_dict()[field] is None for field in FIELD_NAMES)


def test_malformed_json_is_controlled_failure():
    provider = ReplayJSONProvider('{"ee_percent": 95,')
    with pytest.raises(LLMResponseSchemaError, match="Malformed provider JSON"):
        extract_reaction_chunk("The product gave 95% ee.", provider)


def test_explicit_abstention_is_valid_json_contract():
    validated = validate_response(json.dumps(payload(ligand=None, solvent=None)))
    assert validated["ligand"] is None
    assert validated["solvent"] is None


def test_missing_required_key_is_rejected():
    bad = payload()
    del bad["ligand"]
    with pytest.raises(LLMResponseSchemaError, match="missing required keys"):
        validate_response(bad)


def test_extra_explanation_key_is_rejected():
    bad = payload()
    bad["explanation"] = "I inferred the ligand from context"
    with pytest.raises(LLMResponseSchemaError, match="disallowed keys"):
        validate_response(bad)


def test_string_number_is_not_silently_coerced():
    with pytest.raises(LLMResponseSchemaError, match="ee_percent must be a number"):
        validate_response(payload(ee_percent="95"))


def test_out_of_range_percent_is_rejected():
    with pytest.raises(LLMResponseSchemaError, match="ee_percent must be between"):
        validate_response(payload(ee_percent=105))


def test_non_finite_number_is_rejected():
    with pytest.raises(LLMResponseSchemaError, match="must be finite"):
        validate_response(payload(reaction_time_h=float("nan")))


def test_evidence_and_metadata_are_caller_controlled():
    provider = ReplayJSONProvider(
        payload(
            ee_percent=97.5,
            yield_percent=93,
            h2_pressure_bar=20,
            temperature_c=25,
            reaction_time_h=12,
            solvent="THF",
            ligand="BINAP",
            substrate_class="aryl ketone",
        ),
        model_name="example-model",
    )
    evidence = "Synthetic evidence sentence."
    result = extract_reaction_chunk(
        evidence,
        provider,
        candidate_id="case-001",
        evidence_start=100,
        evidence_end=128,
        source_locator={"paper_id": "paper-001", "page": 5},
    )
    output = result.to_dict()
    assert output["candidate_id"] == "case-001"
    assert output["evidence_text"] == evidence
    assert output["evidence_start"] == 100
    assert output["evidence_end"] == 128
    assert output["model_name"] == "example-model"
    assert output["prompt_version"] == PROMPT_VERSION
    assert output["extraction_version"] == EXTRACTION_VERSION
    assert output["extraction_method"] == EXTRACTION_VERSION
    assert output["confidence"] == 0.0
    assert output["source_locator"] == {"paper_id": "paper-001", "page": 5}


def test_request_contains_evidence_and_strict_schema():
    request = build_request("A synthetic chunk with 92% ee.")
    assert "92% ee" in request.user_prompt
    assert request.response_schema["additionalProperties"] is False
    assert set(request.response_schema["required"]) == set(FIELD_NAMES)
    assert request.prompt_version == PROMPT_VERSION


def test_empty_evidence_is_rejected_before_provider_call():
    provider = ReplayJSONProvider(payload())
    with pytest.raises(ValueError, match="non-empty"):
        extract_reaction_chunk("   ", provider)
    assert provider.last_request is None


def test_llm_and_rule_baseline_share_same_scientific_fields():
    evidence = (
        "A synthetic asymmetric hydrogenation was conducted under 20 bar H2 at "
        "25 C for 12 h in THF using BINAP. The aryl ketone product was isolated "
        "in 93% yield with 97.5% ee."
    )
    llm_values = payload(
        ee_percent=97.5,
        yield_percent=93.0,
        h2_pressure_bar=20.0,
        temperature_c=25.0,
        reaction_time_h=12.0,
        solvent="THF",
        ligand="BINAP",
        substrate_class="aryl ketone",
    )
    llm_record = extract_reaction_chunk(
        evidence, ReplayJSONProvider(llm_values)
    ).to_dict()
    baseline_records = extract_reaction_candidates(evidence, context_sentences=1)
    assert len(baseline_records) == 1
    baseline_record = baseline_records[0].to_dict()

    assert all(field in llm_record for field in FIELD_NAMES)
    assert all(field in baseline_record for field in FIELD_NAMES)
    for field in FIELD_NAMES:
        assert llm_record[field] == baseline_record[field]
