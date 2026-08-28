from modules.reaction_candidate_extraction import (
    extract_reaction_candidates,
    pressure_to_bar,
)


def test_pressure_normalisation():
    assert pressure_to_bar(1.0, "MPa") == 10.0
    assert round(pressure_to_bar(1.0, "atm"), 5) == 1.01325


def test_candidate_keeps_local_provenance_and_conditions():
    text = (
        "The iron complex bearing BINAP was used for asymmetric hydrogenation of an aryl ketone. "
        "The reaction was performed under 2.0 MPa H2 in THF at 25 C for 12 h. "
        "The product was isolated in 93% yield and 97.5% ee."
    )
    candidates = extract_reaction_candidates(text)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.ee_percent == 97.5
    assert c.yield_percent == 93.0
    assert c.h2_pressure_bar == 20.0
    assert c.reaction_time_h == 12.0
    assert c.ligand.lower() == "binap"
    assert c.solvent.lower() == "thf"
    assert "97.5% ee" in c.evidence_text
    assert c.evidence_start >= 0
    assert c.evidence_end > c.evidence_start
    assert c.confidence >= 0.8


def test_separate_results_do_not_collapse_to_global_maximum():
    text = (
        "Substrate A was hydrogenated under 10 bar H2 and gave 80% yield and 82% ee.\n"
        "A separate optimisation experiment used 50 bar H2 and afforded 95% yield and 96% ee."
    )
    candidates = extract_reaction_candidates(text, context_sentences=0)
    assert len(candidates) == 2
    assert candidates[0].ee_percent == 82.0
    assert candidates[1].ee_percent == 96.0
    assert candidates[0].h2_pressure_bar == 10.0
    assert candidates[1].h2_pressure_bar == 50.0


def test_no_result_anchor_means_no_candidate():
    text = "The article discusses hydrogenation catalysts but reports no numerical yield or ee."
    assert extract_reaction_candidates(text) == []
