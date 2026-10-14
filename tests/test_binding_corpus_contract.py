"""The binding result must stay tied to the text it was computed over.

`candidate_binding_v1.csv` was produced outside the repository from a corpus
nobody recorded, so it could not be regenerated and nothing noticed when it
drifted from the Gold it describes. Two things close that:

- a committed corpus manifest naming the sha256 of every text artifact, so the
  input is reconstructible from the PDFs and verifiable without them;
- a consistency check between the committed binding CSV and the committed Gold,
  which needs no corpus and therefore runs in CI.
"""
import csv
import json
from pathlib import Path

from tools.audit_candidate_binding import PIN_FIELDS, _pin_values
from tools.build_binding_corpus import verify as verify_corpus

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "benchmark/development_gold"
MANIFEST = json.loads((GOLD_DIR / "binding_corpus_manifest.json").read_text(encoding="utf-8"))
GOLD = [
    json.loads(line)
    for line in (GOLD_DIR / "development_gold_field_schema_v1.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
BINDING = {
    row["gold_case_id"]: row
    for row in csv.DictReader(
        open(GOLD_DIR / "candidate_binding_v1.csv", newline="", encoding="utf-8-sig")
    )
}


def test_manifest_covers_every_development_paper():
    papers = {record["paper_id"] for record in GOLD}
    assert set(MANIFEST["artifacts"]) == papers
    assert MANIFEST["papers"] == len(papers)


def test_every_manifest_entry_names_a_main_artifact_and_a_sha256():
    for paper_id, roles in MANIFEST["artifacts"].items():
        assert "MAIN" in roles, f"{paper_id} has no main article"
        assert set(roles) <= {"MAIN", "SI"}
        for role, digest in roles.items():
            assert len(digest) == 64 and set(digest) <= set("0123456789abcdef"), (
                f"{paper_id}/{role} is not a sha256"
            )


def test_manifest_pins_the_extractor_that_produced_it():
    assert MANIFEST["corpus_version"] == "binding-corpus-v1"
    assert MANIFEST["pypdf_version"]
    assert "pypdf" in MANIFEST["extractor"]
    assert "LF" in MANIFEST["normalization"]


def test_verify_reports_a_missing_or_altered_corpus(tmp_path):
    """The audit refuses to run on a corpus that does not match the manifest."""
    assert verify_corpus(MANIFEST, tmp_path), "an empty directory must not verify"

    paper_id, roles = next(iter(MANIFEST["artifacts"].items()))
    (tmp_path / f"{paper_id}.txt").write_bytes(b"not the paper")
    problems = verify_corpus(MANIFEST, tmp_path)
    assert any(f"{paper_id}.txt" in p and "sha256" in p for p in problems)


def test_binding_agrees_with_the_gold_about_which_values_are_usable():
    """This is the check that catches a binding CSV left behind by a Gold edit."""
    for record in GOLD:
        case_id = record["gold_case_id"]
        values, unusable = _pin_values(record)
        row = BINDING[case_id]
        note, cause = row["note"], row["root_cause"]

        if unusable:
            assert "cannot capture" in note, (
                f"{case_id}: Gold holds {unusable} the builder cannot use, "
                f"but the binding note does not say so: {note!r}"
            )
            for entry in unusable:
                assert entry in note, f"{case_id}: {entry} missing from {note!r}"
        else:
            assert "cannot capture" not in note, (
                f"{case_id}: the binding claims an unusable value the Gold does not have"
            )

        if not values and unusable:
            assert cause == "TARGET_NOT_REPRESENTABLE_BY_CURRENT_BUILDER"
            assert row["binding_status"] == "UNREPRESENTABLE_V1"
        elif len(values) == 1:
            assert row["binding_status"] == "AMBIGUOUS_BINDING"
            assert cause == "INSUFFICIENT_ADJUDICATED_VALUES"


def test_a_bound_case_names_the_chunk_it_bound_to():
    for case_id, row in BINDING.items():
        if row["binding_status"] == "BOUND_EXACT":
            assert row["candidate_id"], f"{case_id} is bound without a candidate"
            assert row["source_chunk_id"], f"{case_id} is bound without a chunk"
            assert row["binding_method"] == "gold_value_pin"
            assert not row["root_cause"]
        else:
            assert not row["candidate_id"], f"{case_id} is unbound but names a candidate"


def test_an_er_pins_as_a_ratio_and_never_against_an_ee():
    """The builder captures both forms, and the two never match each other."""
    for record in GOLD:
        values, unusable = _pin_values(record)
        ee = record["fields"]["ee_or_er"]
        if ee["state"] != "answered":
            continue
        if ee["value"]["kind"] == "er_ratio":
            assert values["ee_or_er"] == ee["value"], "an er pins as its own ratio"
            assert not any("er_ratio" in entry for entry in unusable)
        else:
            assert isinstance(values["ee_or_er"], (int, float))


def test_matching_keeps_the_two_kinds_apart():
    from types import SimpleNamespace

    from tools.audit_candidate_binding import _match_count

    er_gold = {"ee_or_er": {"kind": "er_ratio", "major": 65.0, "minor": 35.0}}
    ee_only = SimpleNamespace(ee_percent=30.0, er_major=None, er_minor=None)
    right_er = SimpleNamespace(ee_percent=None, er_major=65.0, er_minor=35.0)
    wrong_er = SimpleNamespace(ee_percent=None, er_major=70.0, er_minor=30.0)

    assert _match_count(ee_only, er_gold) == 0, "a derived ee must not satisfy an er pin"
    assert _match_count(right_er, er_gold) == 1
    assert _match_count(wrong_er, er_gold) == 0

    ee_gold = {"ee_or_er": 30.0}
    assert _match_count(right_er, ee_gold) == 0, "a ratio must not satisfy an ee pin"
    assert _match_count(ee_only, ee_gold) == 1


def test_pin_fields_are_a_closed_set():
    for record in GOLD:
        values, _ = _pin_values(record)
        assert set(values) <= set(PIN_FIELDS)
