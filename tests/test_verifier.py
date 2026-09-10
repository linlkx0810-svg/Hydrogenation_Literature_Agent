import pytest

from modules.llm_extractor import FIELD_NAMES
from modules.verifier import (
    ReplayVerifierProvider,
    VerificationSchemaError,
    build_verification_request,
    summarize_verification,
    validate_verifier_response,
    verify_candidate,
    verify_field,
)


def accepted():
    return {"status": "accepted", "reason_code": "supported"}


def unresolved(reason="missing"):
    return {"status": "unresolved", "reason_code": reason}


def rejected(reason="wrong_entity"):
    return {"status": "rejected", "reason_code": reason}


def all_responses(default=None):
    default = default or unresolved()
    return {field: dict(default) for field in FIELD_NAMES}


def test_supported_exact_value_can_be_accepted():
    provider = ReplayVerifierProvider({"ee_percent": accepted()})
    result = verify_field(
        field_name="ee_percent",
        extracted_value=97.5,
        evidence_text="The product was obtained with 97.5% ee.",
        provider=provider,
    )
    assert result.status == "accepted"
    assert result.reason_code == "supported"
    assert result.extracted_value == 97.5


def test_plausible_but_unsupported_value_is_not_accepted():
    provider = ReplayVerifierProvider({"ligand": unresolved("missing")})
    result = verify_field(
        field_name="ligand",
        extracted_value="BINAP",
        evidence_text="A chiral phosphine ligand was used.",
        provider=provider,
    )
    assert result.status == "unresolved"
    assert result.reason_code == "missing"


def test_wrong_ligand_association_can_be_rejected():
    provider = ReplayVerifierProvider({"ligand": rejected("wrong_entity")})
    result = verify_field(
        field_name="ligand",
        extracted_value="BINAP",
        evidence_text="Entry 1 used SEGPHOS; entry 2 used BINAP. The reported result refers to entry 1.",
        provider=provider,
    )
    assert result.status == "rejected"
    assert result.reason_code == "wrong_entity"


def test_wrong_row_reaction_association_can_be_rejected():
    provider = ReplayVerifierProvider({"yield_percent": rejected("wrong_reaction")})
    result = verify_field(
        field_name="yield_percent",
        extracted_value=92.0,
        evidence_text="Entry A gave 81% yield. Entry B gave 92% yield. The target is entry A.",
        provider=provider,
    )
    assert result.status == "rejected"
    assert result.reason_code == "wrong_reaction"


def test_conflicting_pressure_remains_unresolved():
    provider = ReplayVerifierProvider({"h2_pressure_bar": unresolved("conflict")})
    result = verify_field(
        field_name="h2_pressure_bar",
        extracted_value=20.0,
        evidence_text="The main text states 20 bar H2, whereas the SI states 30 bar H2 for the same reaction.",
        provider=provider,
    )
    assert result.status == "unresolved"
    assert result.reason_code == "conflict"


def test_stereochemical_placeholder_can_remain_ambiguous():
    provider = ReplayVerifierProvider({"ligand": unresolved("ambiguous")})
    result = verify_field(
        field_name="ligand",
        extracted_value="L1",
        evidence_text="Ligand L1 was used; the provided text does not specify which stereoisomer of L1.",
        provider=provider,
    )
    assert result.status == "unresolved"
    assert result.reason_code == "ambiguous"


def test_invalid_status_reason_pair_is_rejected():
    with pytest.raises(VerificationSchemaError, match="Invalid status/reason pairing"):
        validate_verifier_response(
            {"status": "accepted", "reason_code": "ambiguous"}
        )


def test_extra_explanation_is_rejected():
    with pytest.raises(VerificationSchemaError, match="disallowed keys"):
        validate_verifier_response(
            {
                "status": "accepted",
                "reason_code": "supported",
                "explanation": "looks correct",
            }
        )


def test_missing_verifier_key_is_rejected():
    with pytest.raises(VerificationSchemaError, match="missing required keys"):
        validate_verifier_response({"status": "accepted"})


def test_verification_request_is_field_bounded():
    request = build_verification_request(
        "ee_percent", 95.0, "The product was obtained with 95% ee."
    )
    assert request.field_name == "ee_percent"
    assert "95.0" in request.user_prompt
    assert "The product was obtained with 95% ee." in request.user_prompt
    assert request.response_schema["additionalProperties"] is False


def test_verify_candidate_preserves_original_candidate_values():
    candidate = {
        "candidate_id": "rxn-001",
        "ee_percent": 97.5,
        "yield_percent": 93.0,
        "h2_pressure_bar": 20.0,
        "temperature_c": 25.0,
        "reaction_time_h": 12.0,
        "solvent": "THF",
        "ligand": "BINAP",
        "substrate_class": "aryl ketone",
        "evidence_text": "Synthetic evidence.",
        "source_locator": {"paper_id": "paper-001", "page": 5},
    }
    before = dict(candidate)
    provider = ReplayVerifierProvider(all_responses(accepted()))
    result = verify_candidate(candidate, provider=provider)
    assert candidate == before
    assert result.candidate_id == "rxn-001"
    assert all(v.status == "accepted" for v in result.field_verifications.values())
    assert result.field_verifications["ee_percent"].evidence_locator == {
        "paper_id": "paper-001",
        "page": 5,
    }


def test_summary_separates_extraction_coverage_from_verification():
    responses = all_responses(unresolved("missing"))
    responses["ee_percent"] = accepted()
    responses["yield_percent"] = rejected("wrong_reaction")
    candidate = {field: None for field in FIELD_NAMES}
    candidate.update(
        {
            "candidate_id": "rxn-002",
            "ee_percent": 95.0,
            "yield_percent": 90.0,
            "evidence_text": "Synthetic evidence.",
        }
    )
    result = verify_candidate(
        candidate,
        provider=ReplayVerifierProvider(responses),
    )
    summary = summarize_verification(result.field_verifications.values())
    assert summary["extraction_coverage"] == 2 / 8
    assert summary["accepted_extracted_fraction"] == 1 / 2
    assert summary["status_counts"]["accepted"] == 1
    assert summary["status_counts"]["rejected"] == 1


def test_replay_provider_requires_response_for_every_verified_field():
    candidate = {
        **{field: None for field in FIELD_NAMES},
        "candidate_id": "rxn-003",
        "evidence_text": "Synthetic evidence.",
    }
    with pytest.raises(Exception, match="no response for field"):
        verify_candidate(
            candidate,
            provider=ReplayVerifierProvider({"ee_percent": unresolved()}),
        )
