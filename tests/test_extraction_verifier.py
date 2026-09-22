from modules.extraction_verifier import verify_candidate
from modules.reaction_candidate_extraction import extract_reaction_candidates


def test_verifier_accepts_directly_supported_candidate():
    text = (
        "The catalyst bearing BINAP was used for hydrogenation of an aryl ketone. "
        "The reaction was performed under 2.0 MPa H2 in THF at 25 C for 12 h. "
        "The product was isolated in 93% yield and 97.5% ee."
    )
    candidate = extract_reaction_candidates(text)[0]
    verification = verify_candidate(candidate, text)
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
    text = (
        "The catalyst containing ligand L9 was used for hydrogenation of a ketone. "
        "The product was obtained in 90% yield and 91% ee."
    )
    candidate = extract_reaction_candidates(text)[0]
    candidate.ligand = "L9"
    verification = verify_candidate(candidate, text)
    ligand = [
        field for field in verification.fields
        if field.field == "ligand"
    ][0]
    assert ligand.status == "unresolved"
    assert verification.overall_status == "review"


def test_source_defined_alias_is_supported():
    text = (
        "SEGPHOS (L3) was selected as the ligand. "
        "The catalyst containing L3 was used for hydrogenation of a ketone. "
        "The product was obtained in 90% yield and 91% ee."
    )
    candidate = extract_reaction_candidates(text)[0]
    candidate.ligand = "L3"
    verification = verify_candidate(candidate, text)
    ligand = [
        field for field in verification.fields
        if field.field == "ligand"
    ][0]
    assert ligand.status == "supported"
    assert ligand.canonical_id == "LIGAND:SEGPHOS"
