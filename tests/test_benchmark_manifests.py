"""Invariants for committed benchmark identity manifests (leakage tooling only)."""
import csv
from pathlib import Path

from tools.check_benchmark_overlap import _doi, check

BENCH = Path(__file__).resolve().parents[1] / "benchmark"


def _rows(name):
    with open(BENCH / name, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_development_manifest_has_twelve_unique_confirmed_members():
    dev = _rows("development_manifest.csv")
    assert len(dev) == 12
    assert len({_doi(r["doi"]) for r in dev}) == 12
    assert len({r["paper_id"] for r in dev}) == 12
    ledger = _rows("development_recovery_ledger.csv")
    confirmed = {_doi(r["doi"]) for r in ledger if r["development_membership"] == "CONFIRMED_MEMBER"}
    assert confirmed == {_doi(r["doi"]) for r in dev}


def test_ledger_uses_allowed_enums():
    for r in _rows("development_recovery_ledger.csv"):
        assert r["development_membership"] in {"CONFIRMED_MEMBER", "PROBABLE_MEMBER", "NOT_ESTABLISHED"}
        assert r["contamination_status"] in {"CONTAMINATED", "CLEAN", "UNKNOWN"}
        assert r["confidence"] in {"CONFIRMED", "PROBABLE", "UNRESOLVED"}
        assert r["historical_source"]


def test_every_contaminated_ledger_doi_is_in_known_contamination():
    known = {_doi(r["doi"]) for r in _rows("known_contamination_manifest.csv")}
    for r in _rows("development_recovery_ledger.csv"):
        if r["contamination_status"] == "CONTAMINATED":
            assert _doi(r["doi"]) in known


def test_sealed_reserve_gate_fails_on_known_contamination():
    result = check(
        BENCH / "development_manifest.csv",
        BENCH / "sealed_external_reserve_manifest.csv",
        [BENCH / "known_contamination_manifest.csv"],
    )
    assert result["doi_overlap_count"] == 0
    assert result["paper_id_overlap_count"] == 0
    assert result["known_contamination_doi_overlap_count"] == 4
    assert result["status"] == "FAIL"
