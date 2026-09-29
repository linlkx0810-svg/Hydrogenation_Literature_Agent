from modules.extraction_verifier import verify_candidate
from modules.prediction_normalizer import normalize_record
from modules.reaction_candidate_extraction import extract_reaction_candidates
from modules.raw_llm_extractor_v2 import FIELD_NAMES


def _normalization_for(candidate, text):
    """Build the normalization record the verifier now consumes.

    The verifier no longer resolves anything itself, so a caller must run
    modules.prediction_normalizer first. This helper mirrors what the chain
    runner does for one candidate.
    """
    values = {name: None for name in FIELD_NAMES}
    values["ligand"] = candidate.ligand
    raw_record = {
        "candidate_id": candidate.candidate_id,
        "source_artifact_id": "test",
        "values": values,
        "abstention_reasons": {
            name: "not_reported" for name in FIELD_NAMES if values[name] is None
        },
    }
    return normalize_record(raw_record, text)


def test_verifier_accepts_directly_supported_candidate():
    text = (
        "The catalyst bearing BINAP was used for hydrogenation of an aryl ketone. "
        "The reaction was performed under 2.0 MPa H2 in THF at 25 C for 12 h. "
        "The product was isolated in 93% yield and 97.5% ee."
    )
    candidate = extract_reaction_candidates(text)[0]
    verification = verify_candidate(candidate, text, _normalization_for(candidate, text))
    assert verification.evidence_integrity == "verified"
    assert verification.overall_status == "accept"
    assert all(field.status == "supported" for field in verification.fields)


def test_verifier_rejects_tampered_evidence_offsets():
    text = "The reaction gave 90% yield and 91% ee."
    candidate = extract_reaction_candidates(text, context_sentences=0)[0]
    candidate.evidence_text = "tampered"
    verification = verify_candidate(candidate, text)
    assert verification.overall_status == "reject"
    assert verification.evidence_integrity == "mismatch"


def test_undefined_ligand_alias_routes_to_review_not_guess():
    text = "Using L9, hydrogenation of a ketone gave 90% yield and 91% ee."
    candidate = extract_reaction_candidates(text, context_sentences=0)[0]
    assert candidate.ligand == "L9"
    verification = verify_candidate(candidate, text, _normalization_for(candidate, text))
    ligand = [field for field in verification.fields if field.field == "ligand"][0]
    assert ligand.status == "unresolved"
    assert verification.overall_status == "review"


def test_source_defined_alias_is_supported_via_the_normalizer():
    text = (
        "SEGPHOS (L3) was selected as the ligand. "
        "Using L3, hydrogenation of a ketone gave 90% yield and 91% ee."
    )
    candidate = extract_reaction_candidates(text, context_sentences=0)[0]
    assert candidate.ligand == "L3"
    verification = verify_candidate(candidate, text, _normalization_for(candidate, text))
    ligand = [field for field in verification.fields if field.field == "ligand"][0]
    assert ligand.status == "supported"
    assert ligand.value == "L3", "the raw mention must survive verification"
    assert ligand.canonical_name == "SEGPHOS"


def test_verifier_never_normalizes_on_its_own():
    """Without a normalization record the ligand is unresolved, not guessed."""
    text = (
        "SEGPHOS (L3) was selected as the ligand. "
        "Using L3, hydrogenation of a ketone gave 90% yield and 91% ee."
    )
    candidate = extract_reaction_candidates(text, context_sentences=0)[0]
    verification = verify_candidate(candidate, text)
    ligand = [field for field in verification.fields if field.field == "ligand"][0]
    assert ligand.status == "unresolved"
    assert "normalization_missing" in ligand.reason
    assert ligand.canonical_name is None

    source = (__import__("pathlib").Path(__file__).resolve().parents[1]
              / "modules" / "extraction_verifier.py").read_text(encoding="utf-8")
    assert "ligand_resolver" not in source, "the verifier must not import the resolver"
