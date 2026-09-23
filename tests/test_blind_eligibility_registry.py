"""Unified exclusion registry and PBV3 identity-gate invariants.

These tests never reference a blind identity. The leak test reads the
custodian-private manifest only when it is present locally (env var
``BLIND_IDENTITY_MANIFEST``) and skips otherwise, so CI never sees it.
"""
import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tools.check_benchmark_overlap import check
from tools.doi_aliases import aliases, normalize

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
REGISTRY = BENCH / "blind_eligibility_exclusion_registry.csv"
PREFLIGHT = json.loads((BENCH / "pbv3_current_baseline_preflight.json").read_text(encoding="utf-8"))
ALLOWED_STATUS = {"EXCLUDE", "IDENTITY_ONLY_SAFE"}


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_registry_rows_are_unique_and_well_formed():
    rows = _rows(REGISTRY)
    dois = [normalize(r["doi"]) for r in rows]
    assert all(dois)
    assert len(set(dois)) == len(dois) == PREFLIGHT["unified_exclusion_registry_unique_doi"]
    for r in rows:
        assert r["exclusion_status"] in ALLOWED_STATUS
        assert r["confidence"] in {"CONFIRMED", "PROBABLE", "UNRESOLVED"}
        assert r["exclusion_reason"] and r["source_registry"]


def test_registry_hash_matches_preflight():
    digest = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    assert digest == PREFLIGHT["unified_exclusion_registry_sha256"]


def test_registry_supersedes_the_old_blacklist():
    excluded = {normalize(r["doi"]) for r in _rows(REGISTRY) if r["exclusion_status"] == "EXCLUDE"}
    for row in _rows(BENCH / "known_contamination_manifest.csv"):
        assert normalize(row["doi"]) in excluded
    for row in _rows(BENCH / "development_manifest.csv"):
        assert normalize(row["doi"]) in excluded


def test_publisher_aliases_are_closed_under_expansion():
    excluded = {normalize(r["doi"]) for r in _rows(REGISTRY) if r["exclusion_status"] == "EXCLUDE"}
    for doi in list(excluded):
        assert aliases(doi) <= excluded, f"alias of {doi} missing from the registry"
    assert aliases("10.1002/ange.202504159") == {
        "10.1002/ange.202504159", "10.1002/anie.202504159"}


def test_development_set_still_has_zero_overlap_with_the_registry_gate():
    result = check(BENCH / "development_manifest.csv",
                   BENCH / "sealed_external_reserve_manifest.csv", [])
    assert result["doi_overlap_count"] == 0
    assert result["paper_id_overlap_count"] == 0


def test_gate_status_and_counts_are_consistent():
    assert PREFLIGHT["identity_gate"] in {
        "PASS", "FAIL_CONTAMINATION", "BLOCKED_UNCERTAIN", "BLOCKED_INSUFFICIENT_CLEAN_CANDIDATES"}
    locked = PREFLIGHT["per_locked_slot"]
    assert len(locked) == PREFLIGHT["locked_clean_candidates"]
    assert PREFLIGHT["cohort_shortfall"] == PREFLIGHT["target_cohort_size"] - len(locked)
    assert all(s["status"] == "CLEAN_LOCK_CANDIDATE" for s in locked)
    for key in ("development_overlap_count", "historical_exposure_overlap_count",
                "current_baseline_exposure_count", "pr20_exposure_count", "duplicate_count"):
        assert PREFLIGHT[key] == 0
    if PREFLIGHT["identity_gate"] != "PASS":
        assert PREFLIGHT["gate_attestation_created"] is False
        assert PREFLIGHT["identity_manifest_frozen"] is False


def test_no_gate_attestation_before_the_gate_passes():
    attestation = ROOT / "benchmarks/prospective_blind_v3/gate_attestation_v1.json"
    assert attestation.exists() == (PREFLIGHT["identity_gate"] == "PASS")


def test_public_artifacts_carry_no_unlisted_doi():
    excluded = {normalize(r["doi"]) for r in _rows(REGISTRY)}
    for name in ("pbv3_current_baseline_preflight.json", "pbv3_current_baseline_preflight.md",
                 "blind_eligibility_registry_report.md", "pbv2_current_baseline_preflight.json",
                 "pbv2_current_baseline_preflight.md"):
        text = (BENCH / name).read_text(encoding="utf-8")
        for found in re.findall(r"10\.\d{4,9}/[^\s\"',)\]]+", text):
            if "*" in found:  # a documented DOI prefix pattern, not an identity
                continue
            token = normalize(found).rstrip("`.")
            assert token in excluded, f"{name} exposes an unlisted DOI"
    policy = (ROOT / "benchmarks/prospective_blind_v3/recruitment_policy_v1.md").read_text(encoding="utf-8")
    assert not re.findall(r"10\.\d{4,9}/", policy)


def test_no_blind_identity_is_tracked_in_the_repository():
    manifest = os.environ.get("BLIND_IDENTITY_MANIFEST")
    if not manifest or not Path(manifest).exists():
        pytest.skip("custodian-private blind manifest not available here")
    blind = set()
    for row in _rows(manifest):
        for key in ("doi", "DOI"):
            if row.get(key):
                blind |= {a for a in aliases(row[key])}
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                             capture_output=True, text=True).stdout.splitlines()
    for rel in tracked:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for doi in blind:
            assert doi not in text, f"blind identity leaked into {rel}"
