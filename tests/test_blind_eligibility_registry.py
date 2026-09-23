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
    cohort = PREFLIGHT["cohort"]
    assert cohort["remaining_deficit"] == PREFLIGHT["target_cohort_size"] - cohort["clean_locked"]
    assert cohort["duplicates"] == 0
    assert cohort["prospective_tier1"] + cohort["retrospective_but_unseen"] == cohort["clean_locked"]
    for key in ("gate_a_development_overlap_count", "gate_b_eligibility_registry_overlap_count",
                "gate_c_historical_exposure_count", "duplicate_gate_count"):
        assert PREFLIGHT[key] == 0
    assert PREFLIGHT["source_package_ready"] + PREFLIGHT["source_not_ready"] == cohort["clean_locked"]
    passing = cohort["clean_locked"] == PREFLIGHT["target_cohort_size"]
    assert (PREFLIGHT["identity_gate"] == "PASS") == passing
    if not passing:
        assert PREFLIGHT["gate_attestation_created"] is False
        assert PREFLIGHT["identity_manifest_frozen"] is False


def test_scope_adjudication_counts_are_consistent():
    scope = PREFLIGHT.get("scope_adjudication")
    if not scope:
        pytest.skip("no scope adjudication round recorded")
    assert scope["in_scope"] + scope["out_of_scope"] + scope["scope_uncertain"] == scope["pending_reviewed"]
    assert scope["abstract_metadata_available"] + scope["abstract_metadata_missing"] == scope["pending_reviewed"]
    assert sum(scope["reason_codes"].values()) == scope["pending_reviewed"]
    assert scope["abstracts_stored"] is False
    assert scope["target_fields_extracted"] is False
    gates = PREFLIGHT["gates_for_newly_in_scope"]
    assert gates["clean_after_gates"] <= scope["in_scope"]
    assert PREFLIGHT["cohort"]["clean_locked"] <= PREFLIGHT["target_cohort_size"]


def test_no_agent_execution_or_gold_artifacts():
    for key in ("gold_generated", "predictions_generated", "agent_run", "resolver_run",
                "scoring_run", "blind_gold_opened", "blind_chemistry_inspected",
                "developer_scientific_logic_changed"):
        assert PREFLIGHT[key] is False
    for name in ("pbv3_gold.csv", "pbv3_predictions.csv", "pbv3_scores.csv"):
        assert not (BENCH / name).exists()


def test_private_manifest_hashes_are_pinned_and_current():
    manifest = os.environ.get("BLIND_IDENTITY_MANIFEST_PBV3")
    if not manifest or not Path(manifest).exists():
        pytest.skip("custodian-private PBV3 manifest not available here")
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    assert digest == PREFLIGHT["custodian_private_identity_manifest_sha256"]
    rows = _rows(manifest)
    assert len(rows) == PREFLIGHT["cohort"]["clean_locked"]
    assert len({r["doi"] for r in rows}) == len(rows)
    assert len({r["cohort_slot"] for r in rows}) == len(rows)
    assert all(r["status"] == "CLEAN" for r in rows)
    excluded = {normalize(r["doi"]) for r in _rows(REGISTRY)}
    dev = {normalize(r["doi"]) for r in _rows(BENCH / "development_manifest.csv")}
    for r in rows:
        assert not (aliases(r["doi"]) & excluded)
        assert not (aliases(r["doi"]) & dev)


def test_public_artifacts_carry_no_unlisted_doi():
    excluded = {normalize(r["doi"]) for r in _rows(REGISTRY)}
    for name in ("pbv3_current_baseline_preflight.json", "pbv3_current_baseline_preflight.md",
                 "pbv3_recruitment_funnel_report.md", "pbv3_literature_cutoff_attestation.md",
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


def _normalized_title(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def test_no_blind_identity_is_tracked_in_the_repository():
    manifests = [os.environ.get(name) for name in
                 ("BLIND_IDENTITY_MANIFEST", "BLIND_IDENTITY_MANIFEST_PBV3")]
    manifests = [m for m in manifests if m and Path(m).exists()]
    if not manifests:
        pytest.skip("custodian-private blind manifest not available here")
    # A paper listed in the exclusion registry is no longer blind: it was removed
    # from the cohort and is published as contamination on purpose.
    published = {normalize(r["doi"]) for r in _rows(REGISTRY)}
    published_titles = {_normalized_title(r["title"]) for r in _rows(REGISTRY) if r["title"].strip()}
    blind, titles, paper_ids = set(), set(), set()
    for manifest in manifests:
        for row in _rows(manifest):
            if any(a in published for a in aliases(row.get("doi") or row.get("DOI") or "")):
                continue
            if _normalized_title(row.get("title", "")) in published_titles:
                continue
            for key in ("doi", "DOI"):
                if row.get(key):
                    blind |= aliases(row[key])
            for key in ("title", "paper_identity"):
                if row.get(key) and len(_normalized_title(row[key])) > 40:
                    titles.add(_normalized_title(row[key]))
            for key in ("blind_paper_id", "legacy_blind_id", "paper_id"):
                if row.get(key):
                    paper_ids.add(row[key].strip().lower())
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
        squashed = re.sub(r"[^a-z0-9]", "", text)
        for title in titles:
            assert title not in squashed, f"blind title leaked into {rel}"
        for pid in paper_ids:
            assert pid not in text, f"blind paper_id leaked into {rel}"
