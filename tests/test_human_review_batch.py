"""Human review batch 01, after the reviewer's decisions were recorded.

Claude proposed; the human reviewer decided; `tools/apply_human_gold_reviews.py`
applied exactly those decisions. These tests pin that chain: what promoted, what
stayed open, and that nothing else moved.
"""
import csv
import json
from pathlib import Path

import pytest

from tools.apply_human_gold_reviews import PromotionError, promote

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "benchmark/development_gold"
BATCH = GOLD_DIR / "human_review_batch_01.csv"
GOLD_PATH = GOLD_DIR / "development_gold_field_schema_v1.jsonl"
STRUCTURE_ONLY_FIELDS = {"catalyst", "product", "stereochemical_outcome"}
DECISIONS = {"APPROVE", "REJECT", "MODIFY", "UNRESOLVED", ""}


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _gold():
    return [
        json.loads(line)
        for line in GOLD_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


BATCH_ROWS = _rows(BATCH)
GOLD = {record["gold_case_id"]: record for record in _gold()}
APPROVED = [r for r in BATCH_ROWS if r["reviewer_decision"] == "APPROVE"]
PENDING = [r for r in BATCH_ROWS if not r["reviewer_decision"].strip()]


def test_decisions_come_from_the_fixed_vocabulary():
    for row in BATCH_ROWS:
        assert row["reviewer_decision"] in DECISIONS, row["review_id"]
    assert len(APPROVED) + len(PENDING) + len(
        [r for r in BATCH_ROWS if r["reviewer_decision"] in {"REJECT", "MODIFY", "UNRESOLVED"}]
    ) == len(BATCH_ROWS)
    assert len(APPROVED) == 19, "batch 01 is closed: every row carries a decision"
    assert len(PENDING) == 0


def test_every_approved_row_landed_in_gold_with_human_provenance():
    for row in APPROVED:
        field = GOLD[row["case_id"]]["fields"][row["field"]]
        assert field["state"] == row["proposed_state"]
        assert field["provenance"] == "HUMAN_REVIEW_CONFIRMED"
        assert field["review_status"] == "HUMAN_CONFIRMED"
        assert field["review_id"] == row["review_id"]
        assert field["source_locator"], "a promoted answer keeps its evidence locator"


def test_pending_rows_did_not_touch_gold():
    """Vacuous once batch 01 closed, but it guards the next batch."""
    for row in PENDING:
        field = GOLD[row["case_id"]]["fields"][row["field"]]
        assert field["state"] == "needs_source_review"
        assert field.get("review_status") != "HUMAN_CONFIRMED"
        assert field.get("review_id") is None


def test_dev007_conditions_come_from_the_entry_row_not_a_table_default():
    """The reviewer's note bases 017/018 on entry 7, so Gold must point there."""
    fields = GOLD["DEV-007"]["fields"]
    for name in ("h2_pressure", "temperature"):
        field = fields[name]
        assert field["state"] == "answered"
        assert field["source_locator"] == "Table 2 entry 7"
        assert "no row-specific footnote" in field["reviewer_note"]
    solvent = fields["solvent"]
    assert solvent["value"] == "isopropanol"
    assert solvent["reported_value"] == "basic isopropanol"
    assert "Scheme 3" in solvent["source_locator"]
    assert "KOtBu is separately represented as the base" in solvent["reviewer_note"]


def test_a_converted_pressure_keeps_the_source_value_and_unit():
    """50 atm -> 50.6625 bar must stay auditable in both directions."""
    converted = [r for r in APPROVED if r["field"] == "h2_pressure" and r["reported_unit"] == "atm"]
    assert converted, "batch 01 contains at least one converted pressure"
    for row in converted:
        field = GOLD[row["case_id"]]["fields"]["h2_pressure"]
        assert field["unit"] == "bar"
        assert field["reported_unit"] == "atm"
        assert field["reported_value"] and "atm" in field["reported_value"]
        assert isinstance(field["value"], float) and field["value"] != 50.0 or field["value"] == 50.6625
    for row in [r for r in APPROVED if r["field"] == "h2_pressure"]:
        field = GOLD[row["case_id"]]["fields"]["h2_pressure"]
        assert field["reported_value"] and field["reported_unit"] and field["unit"]


def test_b01_016_keeps_both_the_reported_and_the_canonical_solvent_form():
    field = GOLD["DEV-012"]["fields"]["solvent"]
    assert field["reported_value"] == "CF3CH2OH", "the source spelling must not be lost"
    assert field["canonical_value"] == "TFE"
    assert field["value"] == "TFE"
    assert "CF3CH2OH" in field["reviewer_note"] and "TFE" in field["reviewer_note"]


def test_reviewer_notes_survive_promotion():
    for review_id in ("B01-011", "B01-016"):
        row = next(r for r in BATCH_ROWS if r["review_id"] == review_id)
        field = GOLD[row["case_id"]]["fields"][row["field"]]
        assert field["reviewer_note"] == row["reviewer_note"]
        assert field["note"] == row["reviewer_note"], "the reviewer's words outrank the assistant's"


def test_solvent_alias_lives_in_the_comparator_spec_not_in_extraction_rules():
    spec = json.loads((ROOT / "benchmark/DEVELOPMENT_COMPARATOR_SPEC_V1.json").read_text(encoding="utf-8"))
    group = next(g for g in spec["alias_groups"] if g["identity"] == "TFE")
    assert set(group["aliases"]) == {"CF3CH2OH", "TFE", "2,2,2-trifluoroethanol"}
    assert spec["scope"] == "comparison only"
    for module in ("modules/raw_llm_extractor_v2.py", "modules/prediction_normalizer.py",
                   "modules/extraction_verifier.py", "modules/field_verifiers.py"):
        source = (ROOT / module).read_text(encoding="utf-8")
        assert "CF3CH2OH" not in source, f"{module} must not learn a comparator alias"


def test_batch_touches_no_structure_only_field():
    for row in BATCH_ROWS:
        assert row["field"] not in STRUCTURE_ONLY_FIELDS


def test_promotion_is_idempotent():
    before = GOLD_PATH.read_bytes()
    promoted, counts = promote(_gold(), BATCH_ROWS)
    assert counts["APPROVE"] == 19
    rendered = "\n".join(json.dumps(r, ensure_ascii=False) for r in promoted) + "\n"
    assert rendered.encode("utf-8") == before, "replaying the same decisions must not drift"


def _row_for_an_open_slot():
    """A synthetic review row aimed at a slot that is still needs_source_review."""
    template = dict(BATCH_ROWS[0])
    for record in _gold():
        for name, field in record["fields"].items():
            if field["state"] == "needs_source_review" and name == "h2_pressure":
                template.update(
                    {
                        "review_id": "SYNTH-001",
                        "case_id": record["gold_case_id"],
                        "paper_id": record["paper_id"],
                        "field": name,
                        "current_gold_state": "needs_source_review",
                        "reviewer_decision": "",
                        "reviewer_note": "",
                    }
                )
                return template
    raise AssertionError("no open slot left to exercise the promotion verbs")


def test_reject_and_blank_never_promote():
    open_row = _row_for_an_open_slot()
    gold = _gold()

    open_row["reviewer_decision"] = "REJECT"
    promoted, counts = promote(json.loads(json.dumps(gold)), [open_row])
    field = next(r for r in promoted if r["gold_case_id"] == open_row["case_id"])["fields"][open_row["field"]]
    assert field["state"] == "needs_source_review"
    assert counts["REJECT"] == 1

    open_row["reviewer_decision"] = ""
    promoted, counts = promote(json.loads(json.dumps(gold)), [open_row])
    field = next(r for r in promoted if r["gold_case_id"] == open_row["case_id"])["fields"][open_row["field"]]
    assert field["state"] == "needs_source_review"
    assert counts["BLANK"] == 1


def test_unresolved_promotes_to_a_terminal_reference_state():
    open_row = _row_for_an_open_slot()
    open_row["reviewer_decision"] = "UNRESOLVED"
    promoted, _ = promote(_gold(), [open_row])
    field = next(r for r in promoted if r["gold_case_id"] == open_row["case_id"])["fields"][open_row["field"]]
    assert field["state"] == "unresolved_reference"
    assert field["value"] is None


def test_modify_requires_reviewer_value_state_and_note():
    open_row = _row_for_an_open_slot()
    open_row["reviewer_decision"] = "MODIFY"
    with pytest.raises(PromotionError, match="MODIFY requires"):
        promote(_gold(), [open_row])

    open_row.update({"reviewer_value": "26", "reviewer_state": "answered", "reviewer_note": "read 26 bar"})
    promoted, _ = promote(_gold(), [open_row])
    field = next(r for r in promoted if r["gold_case_id"] == open_row["case_id"])["fields"][open_row["field"]]
    assert field["value"] == 26.0
    assert field["provenance"] == "HUMAN_REVIEW_CONFIRMED"


def test_unknown_decision_fails_closed():
    row = dict(BATCH_ROWS[0])
    row["reviewer_decision"] = "looks fine"
    with pytest.raises(PromotionError, match="unknown reviewer_decision"):
        promote(_gold(), [row])


def test_ee_is_never_converted_and_conversion_is_never_a_yield():
    for row in BATCH_ROWS:
        if row["field"] == "ee_or_er":
            assert row["unit"] in {"percent_ee", "ratio_er"}
            assert ":" not in row["proposed_value"]
            field = GOLD[row["case_id"]]["fields"]["ee_or_er"]
            if field["state"] == "answered":
                assert field["value"]["kind"] == "ee_percent"
        if row["field"] == "yield":
            assert "conversion" not in row["reported_value"].lower()


def test_gold_freeze_stays_incomplete_while_slots_are_open():
    manifest = json.loads(
        (GOLD_DIR / "development_gold_field_schema_v1.freeze.json").read_text(encoding="utf-8")
    )
    status = json.loads((ROOT / "benchmark/development_gold_v1_status.json").read_text(encoding="utf-8"))
    assert status["needs_source_review"] > 0
    assert manifest["frozen"] is False
    assert manifest["status"] == "INCOMPLETE_NOT_FROZEN"
