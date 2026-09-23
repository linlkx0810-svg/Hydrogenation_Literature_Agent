"""Custodian preflight invariants. Must never reference blind identities."""
import csv
import hashlib
import json
import re
from pathlib import Path

from tools.check_benchmark_overlap import _doi

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
PREFLIGHT = json.loads((BENCH / "pbv2_current_baseline_preflight.json").read_text(encoding="utf-8"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(name):
    with open(BENCH / name, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_blacklist_is_unique_and_complete():
    rows = _rows("known_contamination_manifest.csv")
    dois = [_doi(r["doi"]) for r in rows]
    pids = [(r["paper_id"] or "").strip().upper() for r in rows]
    assert len(rows) == PREFLIGHT["known_contamination_rows"]
    assert len(set(dois)) == len(dois) == PREFLIGHT["known_contamination_unique_normalized_doi"]
    assert all(dois)
    present = [p for p in pids if p]
    assert len(set(present)) == len(present)


def test_preflight_pins_current_manifest_hashes():
    assert PREFLIGHT["known_contamination_manifest_sha256"] == _sha(BENCH / "known_contamination_manifest.csv")
    assert PREFLIGHT["development_manifest_sha256"] == _sha(BENCH / "development_manifest.csv")
    assert PREFLIGHT["development_manifest_rows"] == len(_rows("development_manifest.csv"))
    assert PREFLIGHT["blind_identity_manifest_hash_verified"] is True


def test_preflight_pins_the_current_baseline_commit_not_the_old_freeze():
    assert PREFLIGHT["agent_repository_commit"] == "cb48b2d439b272b8c1740b0d1de197a01e3bc98f"
    assert PREFLIGHT["agent_repository_commit"] != PREFLIGHT["old_freeze_commit_not_reused"]


def test_gate_value_and_counts_are_consistent():
    assert PREFLIGHT["formal_gate"] in {"PASS", "FAIL_CONTAMINATION", "BLOCKED_UNCERTAIN"}
    per_case = PREFLIGHT["per_case"]
    assert len(per_case) == PREFLIGHT["blind_identity_count"]
    tally = {k: sum(1 for c in per_case if c["classification"] == k)
             for k in ("CLEAN", "CONTAMINATED", "UNCERTAIN")}
    assert tally["CONTAMINATED"] == PREFLIGHT["historical_development_exposure_count"]
    assert tally["UNCERTAIN"] == PREFLIGHT["uncertain_exposure_count"]
    assert tally["CLEAN"] == PREFLIGHT["clean_count"]
    assert sum(c["development_manifest_doi_overlap"] for c in per_case) == PREFLIGHT["development_overlap_count"]
    assert sum(c["known_contamination_doi_overlap"] for c in per_case) == PREFLIGHT["known_contamination_overlap_count"]
    if PREFLIGHT["formal_gate"] == "PASS":
        assert tally == {"CLEAN": PREFLIGHT["blind_identity_count"], "CONTAMINATED": 0, "UNCERTAIN": 0}
    else:
        assert tally["CONTAMINATED"] or tally["UNCERTAIN"]


def test_no_evaluation_freeze_v2_unless_gate_passes():
    exists = (ROOT / "benchmarks/prospective_blind_v2/evaluation_freeze_v2.json").exists()
    assert exists == (PREFLIGHT["formal_gate"] == "PASS" and PREFLIGHT["evaluation_freeze_v2_created"])


def test_preflight_does_not_leak_blind_identities():
    text = (BENCH / "pbv2_current_baseline_preflight.json").read_text(encoding="utf-8")
    md = (BENCH / "pbv2_current_baseline_preflight.md").read_text(encoding="utf-8")
    known = {_doi(r["doi"]) for r in _rows("known_contamination_manifest.csv")}
    for blob in (text, md):
        for found in re.findall(r"10\.\d{4,9}/[^\s\"',)]+", blob):
            assert _doi(found) in known, "report must not carry non-blacklisted DOIs"
    assert "blind_case" in text and all(
        c["blind_case"].startswith("PBV2-") for c in PREFLIGHT["per_case"])


def test_blind_result_artifacts_are_absent():
    for name in ("blind_predictions.csv", "blind_gold.csv", "blind_scores.csv"):
        assert not (BENCH / name).exists()
    assert PREFLIGHT["blind_gold_opened"] is False
    assert PREFLIGHT["blind_predictions_generated"] is False
    assert PREFLIGHT["blind_scoring_performed"] is False
