"""Contract tests for the Agent v1.0 schema, scoring contract and manifests.

These tests read only committed developer-side artifacts. They never touch a
blind cohort, a blind manifest or any prospective-blind source.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
DOCS = ROOT / "docs"

SCHEMA = json.loads((BENCH / "FIELD_SCHEMA_V1.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((BENCH / "agent_v1_execution_manifest.json").read_text(encoding="utf-8"))
FREEZE = json.loads((BENCH / "agent_v1_system_freeze_candidate.json").read_text(encoding="utf-8"))
UNRESOLVED = "UNRESOLVED_BEFORE_FREEZE"


def test_field_schema_is_atomic_and_complete():
    names = [f["name"] for f in SCHEMA["fields"]]
    assert len(names) == len(set(names)) == SCHEMA["field_count"] == 12
    assert "conditions" not in names, "conditions must be scored as atomic fields"
    assert SCHEMA["aggregate_conditions_field"] is False
    for atomic in ("h2_pressure", "temperature", "reaction_time", "solvent"):
        assert atomic in names
    assert SCHEMA["selectivity_option"] == "B"
    assert "selectivity" not in names
    assert {"ee_or_er", "stereochemical_outcome"} <= set(names)
    for field in SCHEMA["fields"]:
        for key in ("type", "definition", "canonicalization", "evidence_requirement", "scored"):
            assert field[key] not in (None, ""), f"{field['name']} missing {key}"


def test_value_states_keep_unresolved_separate_from_incorrect():
    states = SCHEMA["value_states"]
    assert set(states) == {"answered", "not_reported", "not_applicable", "unresolved", "ambiguous"}
    rules = " ".join(SCHEMA["value_state_rules"]).lower()
    assert "unresolved is not incorrect" in rules
    assert "does not count toward answer coverage" in rules


def test_crosswalk_covers_every_scored_field_and_both_legacy_lists():
    text = (DOCS / "FIELD_SCHEMA_CROSSWALK_V1.md").read_text(encoding="utf-8")
    for field in SCHEMA["fields"]:
        assert f"`{field['name']}`" in text, f"{field['name']} missing from the crosswalk"
    for legacy in ("ee_percent", "yield_percent", "h2_pressure_bar", "temperature_c",
                   "reaction_time_h", "substrate_class"):
        assert legacy in text
    for high_level in ("reaction", "catalyst", "substrate", "product", "conditions", "selectivity"):
        assert high_level in text


def test_scoring_contract_defines_raw_and_verifier_metrics():
    text = (BENCH / "SCORING_CONTRACT_V1.md").read_text(encoding="utf-8").lower()
    for metric in ("coverage", "selective accuracy", "end-to-end accuracy",
                   "hallucination rate", "evidence support rate", "unsupported answer rate",
                   "reasonable abstention rate", "wrong-value block rate", "correct-value retention"):
        assert metric in text, f"{metric} missing from the scoring contract"
    assert "never as a bare accuracy delta" in text
    assert "index-position pairing is forbidden" in text


def test_execution_graph_names_one_verifier_and_one_raw_layer():
    text = (DOCS / "AGENT_V1_EXECUTION_GRAPH.md").read_text(encoding="utf-8")
    for marker in ("ACTIVE_IN_FORMAL_RUN", "DEFERRED_TO_V1_1", "LEGACY_NOT_USED", "DEVELOPMENT_ONLY"):
        assert marker in text
    assert MANIFEST["verifier"]["version"] == "evidence-verifier-v1"
    assert MANIFEST["deferred_verifier"]["status"] == "DEFERRED_TO_V1_1"
    assert MANIFEST["raw_llm_extractor"]["version"] == "llm-extractor-v2"
    assert MANIFEST["raw_llm_extractor"]["status"] == "ACTIVE_IN_FORMAL_RUN"
    assert MANIFEST["legacy_raw_llm_extractor"]["version"] == "llm-extractor-v1"
    assert MANIFEST["legacy_raw_llm_extractor"]["status"] == "LEGACY_NOT_USED"
    assert MANIFEST["legacy_raw_llm_extractor"]["byte_identical_to_old_freeze"] is True


def test_manifest_marks_unknowns_instead_of_guessing():
    assert MANIFEST["model_runtime"]["openai_sdk_version"] == UNRESOLVED
    assert MANIFEST["model_runtime"]["seed"] == "unsupported/unset"
    assert MANIFEST["candidate_builder"]["regex_field_values_role"].startswith("SELECTION_SIGNAL")
    assert MANIFEST["blind_binding"]["prospective_blind_v3"] == "NOT_BOUND"
    for component in ("candidate_builder", "normalizer", "verifier",
                      "raw_llm_extractor", "legacy_raw_llm_extractor", "raw_prediction_freeze"):
        assert re.fullmatch(r"[0-9a-f]{40}", MANIFEST[component]["git_blob_sha"])


def test_raw_stage_is_wired_and_field_driven():
    from modules import raw_llm_extractor_v2 as raw

    assert raw.FIELD_NAMES == tuple(f["name"] for f in SCHEMA["fields"])
    assert MANIFEST["raw_llm_extractor"]["field_source_of_truth"] == "benchmark/FIELD_SCHEMA_V1.json"
    assert MANIFEST["raw_prediction_freeze"]["status"] == "ACTIVE_IN_FORMAL_RUN"
    assert FREEZE["phase_a_legacy_port"]["status"] == "LEGACY_PORT_VALIDATED"
    assert FREEZE["phase_a_legacy_port"]["byte_identical"] is True
    assert (ROOT / "examples/raw_chain_sample.txt").exists()
    assert (ROOT / "examples/raw_llm_replay_example.jsonl").exists()


def test_freeze_candidate_is_not_a_blind_freeze_and_is_honest_about_readiness():
    assert FREEZE["artifact_kind"] == "NOT_A_BLIND_EVALUATION_FREEZE"
    ready = FREEZE["AGENT_V1_SYSTEM_FREEZE_READY"]
    assert ready in {"YES", "NO"}
    states = {k: v["state"] for k, v in FREEZE["readiness"].items()}
    all_green = all(s == "YES" for s in states.values())
    assert (ready == "YES") == all_green
    if ready == "NO":
        assert FREEZE["blocking_gaps"]
    assert not (ROOT / "benchmarks/prospective_blind_v3/evaluation_freeze_v1.json").exists()


def test_developer_artifacts_do_not_reference_blind_sources():
    forbidden = re.compile(r"pbv3_identity_manifest|prospective_blind_v3_manifest|custodian_private", re.I)
    for path in list(BENCH.glob("*.json")) + list(BENCH.glob("*.md")) + list(DOCS.glob("*.md")):
        assert not forbidden.search(path.read_text(encoding="utf-8")), f"{path.name} references custodian-private material"
