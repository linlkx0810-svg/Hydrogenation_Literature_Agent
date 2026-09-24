"""Human review batch 01: proposals stay proposals until a human decides."""
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


def test_batch_ships_with_no_decisions_prefilled():
    for row in BATCH_ROWS:
        assert (row["reviewer_decision"] or "").strip() == "", (
            f"{row['review_id']} ships with a decision; Claude must never approve its own proposal"
        )
    status = json.loads((GOLD_DIR / "HUMAN_REVIEW_STATUS_V1.json").read_text(encoding="utf-8"))
    assert status["decisions_prefilled"] is False
    assert status["formal_gold_changed"] is False
    assert status["claude_role"] == "SOURCE_REVIEW_ASSISTANT"


def test_batch_covers_only_the_requested_queue_reason_and_no_structure_only_field():
    queue = {(row["case"], row["field"]): row for row in _rows(GOLD_DIR / "HUMAN_REVIEW_QUEUE_V1.csv")}
    for row in BATCH_ROWS:
        assert row["field"] not in STRUCTURE_ONLY_FIELDS, (
            f"{row['review_id']} touches a structure-only field, which belongs to batch 02"
        )
        queued = queue.get((row["case_id"], row["field"]))
        if queued is None:
            # the only legal exception is a field already answered in Gold that the
            # source names differently, raised for the reviewer to reconcile
            assert row["current_gold_state"] == "answered"
            continue
        assert queued["reason"] == "VALUE_MUST_BE_READ_FROM_THE_FROZEN_TARGET_ANCHOR"


def test_proposed_states_and_confidence_are_from_the_fixed_vocabularies():
    for row in BATCH_ROWS:
        assert row["proposed_state"] in {"answered", "not_reported", "not_applicable", "unresolved_reference"}
        assert row["confidence"] in {"HIGH", "MEDIUM", "LOW"}
        if row["proposed_state"] == "answered":
            assert row["proposed_value"].strip()
            assert row["source_role"] and row["table_or_scheme"]
        else:
            assert not row["proposed_value"].strip()


def test_ee_is_never_converted_and_conversion_is_never_a_yield():
    for row in BATCH_ROWS:
        if row["field"] == "ee_or_er":
            assert row["unit"] in {"percent_ee", "ratio_er"}
            reported = row["reported_value"].lower()
            if "% ee" in reported:
                assert row["unit"] == "percent_ee"
            assert ":" not in row["proposed_value"], "an ee value must not be written as a ratio"
        if row["field"] == "yield":
            assert "conversion" not in row["reported_value"].lower(), (
                "a conversion may never be proposed as a yield"
            )


def test_proposals_do_not_mutate_the_formal_gold():
    before = GOLD_PATH.read_bytes()
    gold = _gold()
    promote(gold, BATCH_ROWS)  # every decision is blank
    assert GOLD_PATH.read_bytes() == before
    for record in _gold():
        for name, field in record["fields"].items():
            assert field.get("review_status") != "HUMAN_CONFIRMED"
            assert field.get("provenance") != "HUMAN_REVIEW_CONFIRMED"


def test_only_approve_modify_and_unresolved_promote():
    gold = _gold()
    row = dict(BATCH_ROWS[0])

    row["reviewer_decision"] = "REJECT"
    promoted, counts = promote(json.loads(json.dumps(gold)), [row])
    field = next(r for r in promoted if r["gold_case_id"] == row["case_id"])["fields"][row["field"]]
    assert field["state"] == "needs_source_review"
    assert counts["REJECT"] == 1

    row["reviewer_decision"] = ""
    promoted, counts = promote(json.loads(json.dumps(gold)), [row])
    field = next(r for r in promoted if r["gold_case_id"] == row["case_id"])["fields"][row["field"]]
    assert field["state"] == "needs_source_review"
    assert counts["BLANK"] == 1

    row["reviewer_decision"] = "APPROVE"
    promoted, _ = promote(json.loads(json.dumps(gold)), [row])
    field = next(r for r in promoted if r["gold_case_id"] == row["case_id"])["fields"][row["field"]]
    assert field["state"] == "answered"
    assert field["provenance"] == "HUMAN_REVIEW_CONFIRMED"
    assert field["review_status"] == "HUMAN_CONFIRMED"
    assert field["source_locator"], "promotion must preserve an evidence locator"

    row["reviewer_decision"] = "UNRESOLVED"
    promoted, _ = promote(json.loads(json.dumps(gold)), [row])
    field = next(r for r in promoted if r["gold_case_id"] == row["case_id"])["fields"][row["field"]]
    assert field["state"] == "unresolved_reference"
    assert field["value"] is None


def test_modify_requires_reviewer_value_state_and_note():
    gold = _gold()
    row = dict(BATCH_ROWS[0])
    row["reviewer_decision"] = "MODIFY"
    with pytest.raises(PromotionError, match="MODIFY requires"):
        promote(json.loads(json.dumps(gold)), [row])

    row.update({"reviewer_value": "51", "reviewer_state": "answered", "reviewer_note": "read 51 bar"})
    promoted, _ = promote(json.loads(json.dumps(gold)), [row])
    field = next(r for r in promoted if r["gold_case_id"] == row["case_id"])["fields"][row["field"]]
    assert field["value"] == 51.0
    assert field["provenance"] == "HUMAN_REVIEW_CONFIRMED"


def test_unknown_decision_fails_closed():
    row = dict(BATCH_ROWS[0])
    row["reviewer_decision"] = "looks fine"
    with pytest.raises(PromotionError, match="unknown reviewer_decision"):
        promote(_gold(), [row])


def test_binding_preview_does_not_alter_the_binding_audit():
    preview = json.loads((GOLD_DIR / "binding_preview_batch_01.json").read_text(encoding="utf-8"))
    assert preview["hypothetical"] is True
    audit = _rows(GOLD_DIR / "candidate_binding_v1.csv")
    counts = {}
    for row in audit:
        counts[row["binding_status"]] = counts.get(row["binding_status"], 0) + 1
    assert preview["current"] == counts, "the preview must describe the committed audit, not replace it"


def test_gold_freeze_stays_incomplete_before_human_review():
    manifest = json.loads(
        (GOLD_DIR / "development_gold_field_schema_v1.freeze.json").read_text(encoding="utf-8")
    )
    assert manifest["frozen"] is False
    assert manifest["status"] == "INCOMPLETE_NOT_FROZEN"
