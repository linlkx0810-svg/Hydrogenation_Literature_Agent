"""Development Gold validation: shape, states, provenance and migration rules."""
import json
from pathlib import Path

import pytest

from modules.raw_llm_extractor_v2 import FIELD_NAMES
from tools.freeze_development_gold import GoldFreezeError, check, freeze, verify

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "benchmark" / "development_gold"
GOLD_PATH = GOLD_DIR / "development_gold_field_schema_v1.jsonl"
FREEZE_PATH = GOLD_DIR / "development_gold_field_schema_v1.freeze.json"
STAGE1_PATH = GOLD_DIR / "development_gold_migration_stage1.jsonl"
STATUS_PATH = ROOT / "benchmark" / "development_gold_v1_status.json"
CROSSWALK = ROOT / "benchmark" / "development_candidate_id_crosswalk.csv"

GOLD_STATES = {"answered", "not_reported", "not_applicable", "unresolved_reference", "needs_source_review"}
SCORED_STATES = {"answered", "not_reported", "not_applicable"}


def _rows(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


GOLD = _rows(GOLD_PATH)
STATUS = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
MANIFEST = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def test_twelve_cases_twelve_fields_no_duplicates():
    assert len(GOLD) == 12
    ids = [record["gold_case_id"] for record in GOLD]
    assert len(set(ids)) == 12
    papers = [record["paper_id"] for record in GOLD]
    assert len(set(papers)) == 12
    for record in GOLD:
        assert set(record["fields"]) == set(FIELD_NAMES)
    assert STATUS["field_slot_count"] == 144


def test_only_valid_gold_states_are_used():
    for record in GOLD:
        for name, field in record["fields"].items():
            assert field["state"] in GOLD_STATES, f"{record['gold_case_id']}.{name}"
            assert field["state"] != "ambiguous", "ambiguous is a prediction state, not a Gold state"


def test_answered_needs_a_value_and_an_evidence_locator():
    for record in GOLD:
        for name, field in record["fields"].items():
            if field["state"] != "answered":
                continue
            assert field.get("value") not in (None, ""), f"{record['gold_case_id']}.{name}"
            assert field.get("provenance")
            assert field.get("source_locator")
            assert field.get("evidence_type")
            assert field.get("review_status")


def test_not_reported_was_actually_reviewed_and_carries_no_value():
    for record in GOLD:
        for name, field in record["fields"].items():
            if field["state"] != "not_reported":
                continue
            assert field.get("value") is None
            assert field["review_status"] == "SOURCE_REVIEWED_NOT_REPORTED"


def test_no_gold_value_comes_from_an_agent_prediction():
    forbidden = {"agent_prediction", "llm-extractor-v1", "llm-extractor-v2", "verifier",
                 "resolver", "scorer", "evidence-verifier-v1", "evidence-verifier-v1.1"}
    for record in GOLD:
        for name, field in record["fields"].items():
            provenance = str(field.get("provenance") or "").lower()
            assert provenance not in forbidden, f"{record['gold_case_id']}.{name}"


def test_substrate_class_is_never_mechanically_copied_into_substrate():
    stage1 = {r["gold_case_id"]: r for r in _rows(STAGE1_PATH)}
    for record in GOLD:
        substrate = record["fields"]["substrate"]
        if substrate["state"] == "answered":
            assert substrate.get("provenance") != "NON_EQUIVALENT_REQUIRES_REVIEW"
            assert substrate.get("source_locator")
        stage1_substrate = stage1[record["gold_case_id"]]["fields"]["substrate"]
        assert stage1_substrate["value"] is None
        assert stage1_substrate["legacy_support"] == "substrate_class"


def test_ee_migrates_typed_without_conversion_or_configuration_inference():
    for record in GOLD:
        ee = record["fields"]["ee_or_er"]
        if ee["state"] == "answered":
            assert isinstance(ee["value"], dict)
            assert ee["value"]["kind"] in {"ee_percent", "er_ratio"}
            assert isinstance(ee["value"]["value"], (int, float))
        stereo = record["fields"]["stereochemical_outcome"]
        if stereo["state"] == "answered":
            assert stereo.get("provenance") not in {"LEGACY_GOLD_TYPED_MIGRATION"}, (
                "a configuration must never be derived from an ee migration"
            )


def test_reaction_is_blocked_on_a_declared_schema_gap():
    for record in _rows(STAGE1_PATH):
        reaction = record["fields"]["reaction"]
        assert reaction["schema_status"] == "SCHEMA_DEFINITION_GAP"
        assert reaction["value"] is None


def test_unadjudicated_slots_leave_the_denominator():
    excluded = STATUS["unresolved_reference"] + STATUS["needs_source_review"]
    assert STATUS["excluded_from_denominator"] == excluded
    assert STATUS["scored_slots"] + excluded == STATUS["field_slot_count"]
    assert STATUS["scored_slots"] == sum(
        1
        for record in GOLD
        for field in record["fields"].values()
        if field["state"] in SCORED_STATES
    )


def test_freeze_refuses_an_incomplete_gold_and_verifies_the_hash():
    complete = STATUS["completeness"] == "COMPLETE"
    assert MANIFEST["frozen"] is complete
    assert MANIFEST["status"] == ("FROZEN" if complete else "INCOMPLETE_NOT_FROZEN")
    assert MANIFEST["case_count"] == 12
    assert MANIFEST["field_slot_count"] == 144
    assert MANIFEST["blind_eligible"] is False
    assert MANIFEST["legacy_gold_v1_artifact_recovered"] is False
    assert verify(GOLD_PATH, FREEZE_PATH) is True


def test_freeze_rejects_gold_that_breaks_the_contract(tmp_path):
    record = json.loads(json.dumps(GOLD[0]))
    record["fields"]["solvent"] = {
        "state": "answered",
        "value": "THF",
        "provenance": "AGENT_PREDICTION",
        "source_locator": "x",
        "evidence_type": "table_row",
    }
    with pytest.raises(GoldFreezeError, match="Agent-prediction provenance"):
        check([record])

    record = json.loads(json.dumps(GOLD[0]))
    record["fields"]["solvent"] = {
        "state": "answered", "value": "THF", "provenance": "SOURCE_REVIEW",
        "source_locator": "", "evidence_type": "",
    }
    with pytest.raises(GoldFreezeError, match="evidence locator"):
        check([record])

    duplicated = [GOLD[0], json.loads(json.dumps(GOLD[0]))]
    with pytest.raises(GoldFreezeError, match="duplicate gold case ids"):
        check(duplicated)


def test_legacy_gold_inputs_are_unmodified():
    """The legacy record is imported byte-identically, never rewritten."""
    import subprocess

    expected = {
        "manifest_v1.csv": "703c0deef2d7fdb427b4bc9dad05bb1d6008f0ab",
        "source_review_progress_v1.csv": "107f76b03af9c0c1e3f3931b88f1743ff463c3ad",
        "seed_curation_status_v1.csv": "1149b5e147fa4695a657fec491d1fa6463faf2a4",
        "selection_change_log_v1.md": "83f7ffd673dc20db9c4c00e3b70e2ca027a475bc",
        "gold_freeze_attestation_v1.json": "27b9d5461684969405e3a3d1f193b5ff70162a40",
        "gold_record_template_v1.json": "02efccc336f8affceb0c204410d2d370ea994fed",
    }
    for name, blob in expected.items():
        path = GOLD_DIR / "legacy" / name
        actual = subprocess.run(
            ["git", "hash-object", str(path)], capture_output=True, text=True
        ).stdout.strip()
        assert actual == blob, f"{name} is no longer the historical artifact"


def test_candidate_binding_is_recorded_without_guessing():
    import csv

    with open(CROSSWALK, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert len({row["gold_case_id"] for row in rows}) == 12
    bound = [row["bound_candidate_id"] for row in rows if row["bound_candidate_id"]]
    assert len(bound) == len(set(bound))
    for row in rows:
        assert row["binding_status"] in {
            "BOUND", "CANDIDATE_BINDING_FAILURE",
            "BINDING_PENDING_ADJUDICATION", "SOURCE_TEXT_UNAVAILABLE",
        }
        if row["binding_status"] == "BOUND":
            assert row["binding_method"] == "gold_value_pin"
        else:
            assert row["bound_candidate_id"] == ""


def test_scorer_accepts_the_development_gold_and_excludes_unadjudicated_slots(tmp_path):
    """Dry run: development Gold -> scorer gold -> score() with synthetic predictions."""
    import csv as _csv

    from modules.raw_llm_extractor_v2 import FIELD_NAMES as NAMES
    from tools.development_gold_to_scorer_gold import to_scorer_gold
    from tools.score_agent_v1 import score

    with open(CROSSWALK, newline="", encoding="utf-8-sig") as handle:
        bindings = {
            row["gold_case_id"]: row["bound_candidate_id"]
            for row in _csv.DictReader(handle)
            if row["bound_candidate_id"]
        }
    rows, skipped = to_scorer_gold(GOLD, bindings)
    assert rows, "at least one bound case is needed for the dry run"
    assert len(rows) + len(skipped) == 12

    for row in rows:
        for name, field in row["fields"].items():
            assert field["state"] in SCORED_STATES
        gold_case = next(g for g in GOLD if g["gold_case_id"] == row["gold_case_id"])
        for name, field in gold_case["fields"].items():
            if field["state"] not in SCORED_STATES:
                assert name not in row["fields"], f"{name} must leave the denominator"

    gold_row = rows[0]
    values = {name: None for name in NAMES}
    for name, field in gold_row["fields"].items():
        if field["state"] == "answered":
            values[name] = field["value"]
    synthetic_raw = {
        "candidate_id": gold_row["candidate_id"],
        "values": values,
        "abstention_reasons": {n: "not_reported" for n in NAMES if values[n] is None},
    }
    report = score([synthetic_raw], [], rows)
    assert report["n_chunks_scored"] == 1
    assert report["a_raw_extractor"]["n_pairs"] == len(gold_row["fields"])
    assert report["a_raw_extractor"]["incorrect"] == 0
    assert report["a_raw_extractor"]["correct"] == sum(
        1 for f in gold_row["fields"].values() if f["state"] == "answered"
    )
