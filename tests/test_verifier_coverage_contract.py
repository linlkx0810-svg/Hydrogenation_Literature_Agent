"""Verifier coverage contract: modes, the four previously uncovered fields, and denominators."""
import json
from pathlib import Path

import pytest

from modules.field_verifiers import (
    CHECKED_FIELDS,
    COVERAGE_CONTRACT,
    FIELD_MODES,
    NOT_CHECKED,
    NOT_VERIFIABLE,
    literal_match,
    verify_catalyst,
    verify_extended_field,
    verify_product,
    verify_stereochemical_outcome,
)
from modules.raw_llm_extractor_v2 import FIELD_NAMES

ROOT = Path(__file__).resolve().parents[1]


def test_every_schema_field_has_exactly_one_coverage_mode():
    fields = [entry["field"] for entry in COVERAGE_CONTRACT["fields"]]
    assert sorted(fields) == sorted(FIELD_NAMES)
    assert len(fields) == len(set(fields))
    modes = set(COVERAGE_CONTRACT["coverage_modes"])
    for entry in COVERAGE_CONTRACT["fields"]:
        assert entry["coverage_mode"] in modes
        assert isinstance(entry["checked_by_verifier"], bool)
        assert isinstance(entry["can_block"], bool)
        assert isinstance(entry["can_accept"], bool)
        assert entry["limitations"]
        if entry["coverage_mode"] == NOT_CHECKED.upper().replace("_V1", "_V1"):
            assert entry["checked_by_verifier"] is False


def test_reaction_is_declared_unchecked_and_nothing_pretends_otherwise():
    assert FIELD_MODES["reaction"] == "NOT_CHECKED_V1"
    assert CHECKED_FIELDS["reaction"] is False
    verdict = verify_extended_field("reaction", "asymmetric hydrogenation", "anything at all")
    assert verdict.status == NOT_CHECKED


def test_catalyst_supported_only_on_a_literal_mention():
    evidence = "The Ni(OAc)2 precursor was used with the chiral ligand."
    assert verify_catalyst("Ni(OAc)2", evidence).status == "supported"


def test_catalyst_without_identity_evidence_is_not_verifiable_not_unsupported():
    evidence = "A nickel catalyst was used for the hydrogenation."
    verdict = verify_catalyst("Ni(OAc)2/(S)-BINAP", evidence)
    assert verdict.status == NOT_VERIFIABLE
    assert verdict.status != "unsupported"


def test_product_supported_only_on_a_literal_mention():
    evidence = "The reaction delivered 1-phenylethanol in 95% yield."
    assert verify_product("1-phenylethanol", evidence).status == "supported"


def test_product_present_only_in_a_scheme_is_not_verifiable():
    evidence = "The product was obtained in 95% yield (Scheme 2)."
    verdict = verify_product("(R)-1-phenylethanol", evidence)
    assert verdict.status == NOT_VERIFIABLE


def test_stereo_supported_on_an_explicit_descriptor():
    evidence = "The (R)-alcohol was obtained in 98% ee."
    assert verify_stereochemical_outcome("R", evidence).status == "supported"
    assert verify_stereochemical_outcome("(R)", evidence).status == "supported"


def test_stereo_with_only_an_ee_value_is_not_verifiable():
    evidence = "The alcohol was obtained in 98% ee and 95% yield."
    verdict = verify_stereochemical_outcome("R", evidence)
    assert verdict.status == NOT_VERIFIABLE
    assert "never inferred" in verdict.reason


def test_stereo_contradicted_by_an_explicit_descriptor_is_unsupported():
    evidence = "The (S)-configured product was isolated."
    assert verify_stereochemical_outcome("R", evidence).status == "unsupported"


def test_stereo_matching_is_boundary_aware():
    evidence = "Rapid reduction of the ring system gave the alcohol in 98% ee."
    assert verify_stereochemical_outcome("R", evidence).status == NOT_VERIFIABLE
    assert verify_stereochemical_outcome("S", "A resin support was used.").status == NOT_VERIFIABLE


def test_literal_matching_is_safe_and_not_fuzzy():
    assert literal_match("Ni(OAc)2", "we used ni(oac)2 as the precursor")
    assert literal_match("1-phenylethanol", "gave 1‐phenylethanol in 95%")  # unicode hyphen
    assert not literal_match("BINAP", "BINAPHANE was used")  # boundary aware
    assert not literal_match("Ni(OAc)2", "Ni(OTf)2 was used")  # no edit-distance rescue
    assert not literal_match("acetophenone", "aceto phenone")  # no token rescue


@pytest.mark.parametrize("field", ["catalyst", "product", "stereochemical_outcome"])
def test_verifier_never_performs_recovery_extraction(field):
    """A null prediction stays null even when the evidence contains the answer."""
    evidence = "The (R)-1-phenylethanol was formed with Ni(OAc)2 in 98% ee."
    verdict = verify_extended_field(field, None, evidence)
    assert verdict.value is None
    assert verdict.status == NOT_VERIFIABLE


def test_scoring_contract_documents_the_new_denominators():
    text = (ROOT / "benchmark" / "SCORING_CONTRACT_V1.md").read_text(encoding="utf-8")
    for term in (
        "verifier_eligible_units",
        "verifier_checked_units",
        "verifier_coverage_rate",
        "not_checked_v1",
        "not_verifiable_v1",
        "UNVERIFIED_PASS_THROUGH",
        "final_stream_end_to_end_accuracy",
    ):
        assert term in text, f"{term} missing from the scoring contract"


def test_execution_manifest_does_not_claim_full_verifier_coverage():
    manifest = json.loads(
        (ROOT / "benchmark" / "agent_v1_execution_manifest.json").read_text(encoding="utf-8")
    )
    verifier = manifest["verifier"]
    assert verifier["verifier_coverage_contract"] == "verifier-coverage-contract-v1"
    assert verifier["version"] == COVERAGE_CONTRACT["verifier_version"]
    assert "12/12" not in json.dumps(manifest)
    assert set(verifier["unchecked_field_modes"]) == {"reaction"}
    assert set(verifier["checked_field_modes"]) == set(FIELD_NAMES) - {"reaction"}


def test_trust_benchmark_no_longer_calls_the_rule_baseline_raw():
    source = (ROOT / "tools" / "run_trust_benchmark.py").read_text(encoding="utf-8")
    assert "rule_baseline" in source
    assert '"raw"' not in source, "the deterministic baseline must not be labelled raw"
    assert "raw[" not in source
