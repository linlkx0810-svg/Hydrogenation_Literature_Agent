from modules.extraction_backends import CallableBackend, RuleBasedBackend, get_backend
from modules.reaction_candidate_extraction import ReactionCandidate


def test_rule_backend_resolves_and_extracts_candidate():
    backend = get_backend("rule")
    assert isinstance(backend, RuleBasedBackend)

    text = (
        "Using BINAP, an aryl ketone was hydrogenated under 20 bar H2 in THF "
        "at 25 C for 12 h. The product was obtained in 93% yield and 97.5% ee."
    )
    candidates = backend.extract(text)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.ee_percent == 97.5
    assert candidate.yield_percent == 93.0
    assert candidate.h2_pressure_bar == 20.0
    assert candidate.extraction_method == "rule-baseline-v1"


def test_callable_backend_enforces_common_schema():
    def extractor(text: str, context: int):
        return [
            ReactionCandidate(
                candidate_id="rxn-0001",
                ee_percent=90.0,
                yield_percent=88.0,
                h2_pressure_bar=10.0,
                temperature_c=25.0,
                reaction_time_h=4.0,
                solvent="THF",
                ligand="BINAP",
                substrate_class="ketone",
                confidence=0.9,
                evidence_text=text,
                evidence_start=0,
                evidence_end=len(text),
                extraction_method="mock-model",
            )
        ]

    backend = CallableBackend(extractor=extractor, name="mock-model")
    candidates = backend.extract("synthetic evidence")
    assert candidates[0].extraction_method == "mock-model"


def test_unknown_backend_fails_explicitly():
    try:
        get_backend("llm")
    except ValueError as exc:
        assert "Unknown backend" in str(exc)
    else:
        raise AssertionError("Unknown backend should raise ValueError")
