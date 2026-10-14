import pytest

from modules.reaction_candidate_extraction import (
    _sentence_spans,
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


def test_a_labelled_enantiomer_ratio_is_captured_as_two_terms():
    """`65:35 e.r.` is a ratio, not a 30% ee. The builder must not do that sum."""
    text = (
        "The iron complex bearing BINAP reduced the aryl ketone under 50 bar H2 in THF at 65 C. "
        "2r: >99% GC yield, 65:35 e.r.."
    )
    candidates = extract_reaction_candidates(text)
    assert candidates, "a labelled er must anchor a candidate on its own"
    c = candidates[0]
    assert (c.er_major, c.er_minor) == (65.0, 35.0)
    assert c.ee_percent is None, "an er must never be recorded as an ee"


def test_an_er_anchors_a_window_that_no_ee_or_yield_regex_reaches():
    """`>99% GC yield` matches no yield pattern, so only the er can anchor here."""
    text = "Product 2r was obtained. 2r: >99% GC yield, 65:35 e.r.."
    candidates = extract_reaction_candidates(text)
    assert len(candidates) == 1
    assert candidates[0].yield_percent is None
    assert (candidates[0].er_major, candidates[0].er_minor) == (65.0, 35.0)


def test_er_is_read_in_either_word_order():
    for text, expected in (
        ("the enantiomer ratio (82:18 vs 76:24) improved", (82.0, 18.0)),
        ("an enantiomeric ratio of 99:1", (99.0, 1.0)),
        ("entry 1, 1a, 88% yield, 91:9 er", (91.0, 9.0)),
    ):
        candidates = extract_reaction_candidates(text)
        assert candidates, text
        assert (candidates[0].er_major, candidates[0].er_minor) == expected, text


def test_an_abbreviation_period_does_not_end_a_sentence():
    """`e.r.` used to be cut from its own ratio by the sentence splitter."""
    candidates = extract_reaction_candidates("e.r. = 95:5 was measured")
    assert candidates and (candidates[0].er_major, candidates[0].er_minor) == (95.0, 5.0)


def test_sentence_splitting_still_ends_a_real_sentence():
    """The abbreviation rule must not glue ordinary sentences together."""
    for text, expected in (
        # a single capital before the period is a unit, not an abbreviation
        ("The reaction ran at 25 C. The product was isolated in 88% yield.", 2),
        ("Purified by chiral GC. The e.r. was 95:5.", 2),
        ("Solvent was THF. Yield was 90%.", 2),
        # an abbreviation followed by a sentence period leaves a bare dot last
        ("2r: >99% GC yield, 65:35 e.r.. Next sentence here.", 2),
        # a mid-sentence abbreviation keeps its sentence whole
        ("the m.p. = 120 C was recorded", 1),
        ("Several solvents, e.g. THF, were tried. It worked.", 2),
    ):
        assert len(_sentence_spans(text)) == expected, text


def test_sentence_spans_report_exact_offsets():
    """Spans are cut from the boundaries, so a repeated sentence keeps its place."""
    text = "The yield was 90%. The yield was 90%. A third sentence."
    spans = _sentence_spans(text)
    assert len(spans) == 3
    assert [text[start:end] for start, end, _ in spans] == [part for _, _, part in spans]
    assert spans[0][0] == 0 and spans[1][0] == 19


def test_an_unlabelled_ratio_is_never_read_as_a_selectivity():
    """Solvent ratios, eluent gradients and loadings are all `d:d` too."""
    for text in (
        "purified on silica with n-hexane/ethyl acetate 10:1 to 8:1, giving 88% yield",
        "run at S:C:B 225:1:15 to give 88% yield",
        "a 80:20 mixture of toluene and THF gave 88% yield",
        "dr 95:5 by NMR, 88% yield",
    ):
        candidates = extract_reaction_candidates(text)
        for c in candidates:
            assert c.er_major is None, f"unlabelled ratio read as an er in: {text}"


def test_an_ee_paper_gains_no_er_and_keeps_its_confidence():
    """Adding er support must not change what an ee-only window reports."""
    text = (
        "A BINAP catalyst hydrogenated an aryl ketone under 20 bar H2 in THF at 25 C "
        "for 12 h, giving 93% yield and 97.5% ee."
    )
    candidates = extract_reaction_candidates(text)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.ee_percent == 97.5
    assert c.er_major is None and c.er_minor is None


def test_er_and_ee_earn_the_same_confidence_credit():
    ee_text = "The product was isolated in 88% yield and 30% ee."
    er_text = "The product was isolated in 88% yield, 65:35 e.r.."
    ee_c = extract_reaction_candidates(ee_text)[0]
    er_c = extract_reaction_candidates(er_text)[0]
    assert ee_c.confidence == er_c.confidence
