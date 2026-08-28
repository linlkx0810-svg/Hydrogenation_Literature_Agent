"""Regression tests for Stage 5 reaction-data extraction helpers.

These tests intentionally use synthetic text rather than copyrighted article
content. They provide a small, deterministic safety net for the rule-based
extractor while the project develops a manually curated scientific benchmark.
"""

import pytest

from modules.reaction_data_extraction import (
    EE_RE,
    H2_BAR_RE,
    TEMP_RE,
    TIME_RE,
    TOF_RE,
    TON_RE,
    YIELD_RE,
    _best_ee,
    _best_yield,
    _extract_ligand,
    _extract_solvent,
    _extract_substrate,
    _first,
)


def test_best_ee_returns_highest_reported_value():
    text = "The products were obtained in 81% ee, 94.5% ee, and 90% ee."
    assert _best_ee(text) == "94.5"


def test_best_yield_returns_highest_reported_value():
    text = "Screening gave 62% yield; optimisation afforded 91.5% yield."
    assert _best_yield(text) == "91.5"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hydrogenation at 50 bar H2", "50"),
        ("performed under 1.5 MPa hydrogen", "1.5"),
        ("reaction at 40 atm H2", "40"),
    ],
)
def test_pressure_pattern_detects_supported_units(text, expected):
    assert _first(H2_BAR_RE, text) == expected


def test_common_condition_patterns():
    text = "The reaction was run at 25 °C for 18 h with TON = 1200 and TOF: 66.7 h-1."
    assert _first(TEMP_RE, text) == "25"
    assert _first(TIME_RE, text) == "18"
    assert _first(TON_RE, text) == "1200"
    assert _first(TOF_RE, text) == "66.7"


def test_chemical_vocabulary_extractors_are_case_insensitive():
    text = "A BINAP complex hydrogenated the aryl ketone in THF."
    assert _extract_ligand(text, []) == "BINAP"
    assert _extract_substrate(text).lower() == "aryl ketone"
    assert _extract_solvent(text).lower() == "thf"


def test_missing_values_return_empty_strings():
    text = "No numerical catalytic result is reported in this synthetic example."
    assert _best_ee(text) == ""
    assert _best_yield(text) == ""
    assert _first(EE_RE, text) == ""
    assert _first(YIELD_RE, text) == ""
