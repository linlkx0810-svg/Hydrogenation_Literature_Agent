"""The enantioselectivity contract: an er stays an er, end to end.

The Gold used to store `65:35 er` as `{kind: ee_percent, value: 30.0}` while the
extractor was instructed never to convert an er, the normalizer passed the field
through untouched, and the scorer required the kinds to match. A faithful
extraction therefore scored `incorrect` on exactly the field this benchmark
exists to measure. These tests pin each link of that chain.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.build_development_gold import GoldBuildError, _typed_value
from tools.score_agent_v1 import _equal, _outcome

ROOT = Path(__file__).resolve().parents[1]
GOLD = [
    json.loads(line)
    for line in (ROOT / "benchmark/development_gold/development_gold_field_schema_v1.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
SCHEMA = json.loads((ROOT / "benchmark/FIELD_SCHEMA_V1.json").read_text(encoding="utf-8"))
UNIT_BEARING = {"h2_pressure", "temperature", "reaction_time", "yield", "ee_or_er"}


def _field(case_id, name):
    return next(r for r in GOLD if r["gold_case_id"] == case_id)["fields"][name]


def test_the_two_reported_ratios_are_stored_as_ratios():
    """DEV-001 reads `65:35 e.r.` and DEV-003 `91:9` in their sources."""
    for case_id, major, minor in (("DEV-001", 65.0, 35.0), ("DEV-003", 91.0, 9.0)):
        ee = _field(case_id, "ee_or_er")
        assert ee["state"] == "answered"
        assert ee["value"] == {"kind": "er_ratio", "major": major, "minor": minor}
        assert ee["unit"] == "ratio_er"
        assert str(int(major)) in ee["reported_value"]


def test_no_gold_ee_equals_the_derived_difference_of_a_reported_ratio():
    """major - minor is exactly how the old conversion produced its ee."""
    for record in GOLD:
        ee = record["fields"]["ee_or_er"]
        reported = ee.get("reported_value") or ""
        if ee["state"] != "answered" or ":" not in reported:
            continue
        assert ee["value"]["kind"] == "er_ratio", (
            f"{record['gold_case_id']}: a reported ratio was stored as an ee"
        )


def test_scorer_never_matches_an_er_against_an_ee():
    er = {"kind": "er_ratio", "major": 65.0, "minor": 35.0}
    assert _equal(er, {"kind": "ee_percent", "value": 30.0}) is False
    assert _equal({"kind": "ee_percent", "value": 30.0}, er) is False


def test_scorer_distinguishes_two_different_ratios():
    """The old comparator read `value` on both sides, saw None, and said equal."""
    a = {"kind": "er_ratio", "major": 70.0, "minor": 30.0}
    b = {"kind": "er_ratio", "major": 99.0, "minor": 1.0}
    assert _equal(a, b) is False
    assert _outcome(a, None, b, "answered") == "incorrect"
    assert _equal(a, dict(a)) is True
    assert _outcome(a, None, dict(a), "answered") == "correct"


def test_a_ratio_without_its_terms_is_not_equal_to_anything():
    bare = {"kind": "er_ratio"}
    assert _equal(bare, {"kind": "er_ratio", "major": 70.0, "minor": 30.0}) is False
    assert _equal(bare, dict(bare)) is False


def test_builder_requires_both_terms_of_a_ratio():
    assert _typed_value({"value": "91:9", "value_kind": "er_ratio"}) == {
        "kind": "er_ratio", "major": 91.0, "minor": 9.0
    }
    with pytest.raises(GoldBuildError, match="major:minor"):
        _typed_value({"value": "82", "value_kind": "er_ratio"})


def test_every_answered_measurement_names_its_unit():
    """Without a unit, 50 bar and 50 atm are the same Gold value."""
    for record in GOLD:
        for name in UNIT_BEARING:
            field = record["fields"].get(name, {})
            if field.get("state") == "answered":
                assert field.get("unit"), f"{record['gold_case_id']}.{name} has no unit"


def test_schema_no_longer_permits_an_er_to_ee_conversion():
    ee = next(f for f in SCHEMA["fields"] if f["name"] == "ee_or_er")
    text = ee["canonicalization"].lower()
    assert "never converted" in text
    assert "converted to ee only when" not in text
    amendment = next(a for a in SCHEMA["schema_amendments"] if a["amendment"] == 2)
    assert amendment["field_set_changed"] is False


def test_the_extractor_prompt_and_the_schema_now_agree():
    prompt = (ROOT / "modules/raw_llm_extractor_v2.py").read_text(encoding="utf-8")
    assert "never convert er to ee yourself" in prompt
    ee = next(f for f in SCHEMA["fields"] if f["name"] == "ee_or_er")
    assert "never converted" in ee["canonicalization"]


def test_the_gold_still_rebuilds_from_its_inputs(tmp_path):
    """The corrected adjudications must still replay deterministically."""
    stage1 = tmp_path / "stage1.jsonl"
    pre = tmp_path / "pre.jsonl"
    out = tmp_path / "gold.jsonl"
    env = {"PYTHONPATH": str(ROOT)}
    run = lambda args: subprocess.run(
        [sys.executable, *args], cwd=ROOT, check=True, capture_output=True, env={**__import__("os").environ, **env}
    )
    run(["tools/build_development_gold_stage1.py", "--out", str(stage1)])
    run(["tools/build_development_gold.py", "--stage1", str(stage1), "--out", str(pre),
         "--status", str(tmp_path / "status.json")])
    run(["tools/apply_human_gold_reviews.py", "--gold", str(pre), "--reviews",
         "benchmark/development_gold/human_review_batch_01.csv", "--out", str(out)])
    committed = (ROOT / "benchmark/development_gold/development_gold_field_schema_v1.jsonl").read_bytes()
    assert out.read_bytes() == committed
