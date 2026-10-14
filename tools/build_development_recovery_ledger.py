"""Rebuild the development-recovery ledger and contamination manifests.

Identity-only: this script reads paper IDs, DOIs, titles, metals and
historical-role labels from local project records. It never reads Gold
values, predictions, evidence text or reaction answers.

Usage:
    python tools/build_development_recovery_ledger.py \
        --project-root "D:/Documents/Fe_Ni_H2_Asymmetric_Hydrogenation_Combined" \
        --dev-manifest-v1 path/to/manifest_v1.csv

``--dev-manifest-v1`` is ``benchmarks/real_development/manifest_v1.csv``
exported from git commit ``be2952d`` (branch
``origin/codex/p0-real-development-set-v1``).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "benchmark"

DEV_SRC = (
    "git:origin/codex/p0-real-development-set-v1@be2952d:"
    "benchmarks/real_development/manifest_v1.csv"
    " + source_review_progress_v1.csv + gold_freeze_attestation_v1.json"
    " (private Gold v1 frozen 2026-09-10; 12 cases)"
)
SPLIT_SRC = "local:reports/extraction_logs/Gold_Benchmark_Split_Manifest_v0.1.csv"
STAGE5C_SRC = "local:data/stage5b_reaction_level_schema/fe_ni_h2_ah_pilot_extraction_set.csv"
BLIND_V1_SRC = (
    "local:reports/extraction_logs/agent_mvp_v4.1/external_3d_blind_reserve_one_shot_eval/"
    "sources/reserve_source_snapshot_manifest.csv + post_blind_steps_1_6/governance/"
    "BLIND_V1_EXPOSED_CASES.json + BLIND_V1_GOVERNANCE_RECORD.md"
)
EXCL_SRC = "local:reports/normalization_prospective_blind_v2/historical_doi_exclusions_v4.csv"
MEMB_SRC = "local:data/production_corpus/v1.1/memberships.csv"
CORPUS64_SRC = (
    "local:data/stage5a_frozen_fe_ni_combined_64paper_corpus/"
    "fe_ni_h2_ah_combined_64_literature_table.csv"
)

# Pilot IDs recovered from local pilot workbook/report names, e.g.
# PILOT01__FE-H2-AH-0011, PILOT07-FE-H2-AH-0017, Pilot08_FE_H2_AH_0020.
PILOTS = {
    "FE-H2-AH-0011": "PILOT01",
    "FE-H2-AH-0019": "PILOT02",
    "FE-H2-AH-0025": "PILOT03",
    "FE-H2-AH-0013": "PILOT04",
    "FE-H2-AH-0012": "PILOT05",
    "FE-H2-AH-0021": "PILOT06",
    "FE-H2-AH-0017": "PILOT07",
    "FE-H2-AH-0020": "PILOT08",
}
STAGE5C = {
    "FE-H2-AH-0005", "FE-H2-AH-0016", "FE-H2-AH-0022",
    "NI-H2-AH-0031", "NI-H2-AH-0032", "NI-H2-AH-0033",
}
REPLACED = {
    "NI-H2-AH-0033": "DEV-006 initial selection; replaced by NI-H2-AH-0027 on 2026-09-10 "
                     "before Gold v1 freeze (same-entry outcome evidence source-blocked; "
                     "selection_change_log_v1.md)",
    "NI-H2-AH-0026": "DEV-012 initial selection; replaced by NI-H2-AH-0029 on 2026-09-10 "
                     "before Gold v1 freeze (article/SI file not re-locatable; "
                     "selection_change_log_v1.md); seed curation record exists",
}
TEST_P = {"10.1016/j.tet.2013.06.016", "10.1038/s41467-018-07462-w", "10.1055/s-0030-1259725"}

LEDGER_FIELDS = [
    "record_id", "paper_id", "doi", "metal", "title", "historical_source",
    "historical_role", "development_membership", "contamination_status",
    "confidence", "evidence_note",
]


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def ndoi(value):
    value = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.rstrip(".")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--dev-manifest-v1", required=True)
    args = parser.parse_args()
    root = Path(args.project_root)

    ident = {}  # doi -> {paper_id, metal, title}

    def remember(doi, pid="", metal="", title=""):
        rec = ident.setdefault(doi, {"paper_id": "", "metal": "", "title": ""})
        rec["paper_id"] = rec["paper_id"] or pid
        rec["metal"] = rec["metal"] or metal
        rec["title"] = rec["title"] or title

    for r in rows(root / "data/stage5a_frozen_fe_ni_combined_64paper_corpus/"
                         "fe_ni_h2_ah_combined_64_literature_table.csv"):
        remember(ndoi(r["DOI"]), r["combined_record_id"], r["source_metal"], r["title"])
    corpus64 = {ndoi(r["DOI"]) for r in rows(
        root / "data/stage5a_frozen_fe_ni_combined_64paper_corpus/"
               "fe_ni_h2_ah_combined_64_literature_table.csv")}
    memberships = rows(root / "data/production_corpus/v1.1/memberships.csv")
    for r in memberships:
        remember(ndoi(r["DOI"]), r["paper_id"], r["metal"], r["paper title"])
    reserve = rows(BENCH / "sealed_external_reserve_manifest.csv")
    for r in reserve:
        remember(ndoi(r["doi"]), "", r["metal"], r["title"])
    excl_path = root / "reports/normalization_prospective_blind_v2/historical_doi_exclusions_v4.csv"
    exclusions = {ndoi(r["doi"]): r["exclusion_sources"] for r in rows(excl_path)}

    dev = rows(args.dev_manifest_v1)
    assert len(dev) == 12, len(dev)
    ledger, seen = [], set()

    def add(doi, role, membership, confidence, source, note, pid=None):
        info = ident.get(doi, {"paper_id": "", "metal": "", "title": ""})
        ledger.append({
            "record_id": f"REC-{len(ledger) + 1:04d}",
            "paper_id": pid if pid is not None else info["paper_id"],
            "doi": doi,
            "metal": info["metal"] or "UNKNOWN",
            "title": info["title"],
            "historical_source": source,
            "historical_role": role,
            "development_membership": membership,
            "contamination_status": "CONTAMINATED",
            "confidence": confidence,
            "evidence_note": note,
        })
        seen.add(doi)

    # A. Formal 12-paper development set (post-replacement, Gold v1 frozen).
    dev_rows = []
    for r in dev:
        doi, pid = ndoi(r["doi"]), r["combined_record_id"]
        remember(doi, pid, r["metal"], r["title"])
        roles = [f"real_development_set_v1 {r['dev_id']} (NON_BLIND_DEVELOPMENT; private Gold v1)"]
        if pid in STAGE5C:
            roles.append("Stage5C pilot extraction")
        if pid in PILOTS:
            roles.append(f"{PILOTS[pid]} reaction-level pilot / Gold v0.1-v1.0 benchmark block")
        add(doi, "; ".join(roles), "CONFIRMED_MEMBER", "CONFIRMED", DEV_SRC,
            f"cohort={r['cohort']}; {r['rationale']}", pid=pid)
        dev_rows.append({
            "paper_id": pid, "doi": doi, "metal": r["metal"], "title": r["title"],
            "main_source_path": "", "si_source_path": "",
            "notes": f"{r['dev_id']}; cohort={r['cohort']}; source_basis={r['source_basis']}; "
                     f"recovered from {DEV_SRC}",
        })

    # B. Replaced initial members (touched during dev selection/curation).
    for pid, note in REPLACED.items():
        doi = next(d for d, v in ident.items() if v["paper_id"] == pid)
        role = "real_development_set_v1 initial selection (replaced before Gold freeze)"
        if pid in STAGE5C:
            role += "; Stage5C pilot extraction"
        add(doi, role, "NOT_ESTABLISHED", "CONFIRMED",
            "git:origin/codex/p0-real-development-set-v1@83e458f..be2952d:"
            "benchmarks/real_development/manifest_v1.csv + selection_change_log_v1.md"
            " + seed_curation_status_v1.csv", note)

    # C. Pilot01-08 not already covered.
    for pid, pilot in PILOTS.items():
        doi = next(d for d, v in ident.items() if v["paper_id"] == pid)
        if doi in seen:
            continue
        if pilot == "PILOT08":
            role = "PILOT08 reaction-level pilot; freeze-contract regression fixture"
            src = ("local:reports/normalization-v2-curation-20260908/regression/"
                   "freeze_contract_fixtures/Pilot08_FE_H2_AH_0020_*")
            note = "Used as regression fixture for freeze-workflow/normalization pipeline."
        else:
            split = {"PILOT02": "STRICT_HELD_OUT_TEST", "PILOT05": "STRICT_HELD_OUT_TEST"}.get(
                pilot, "DEVELOPMENT_DEBUG")
            role = f"{pilot} reaction-level pilot; Gold Benchmark v0.1 split={split}; Frozen Gold v1.0 block"
            src = SPLIT_SRC + " + Frozen_Gold_Benchmark_v1.0_20260807.csv"
            note = ("Human-extracted pilot with Gold; evaluated by earlier Agent versions. "
                    "Held-out split in Gold v0.1 was consumed by prior Agent evaluation.")
        add(doi, role, "NOT_ESTABLISHED", "CONFIRMED", src, note)

    # D. The four 'sealed external reserve' papers = consumed Blind-v1 (3DXR-001..004).
    for r in reserve:
        doi = ndoi(r["doi"])
        add(doi,
            "Blind-v1 external 3D reserve (3DXR); Agent v4.1 one-shot evaluated 2026-08-12; "
            "Gold labels + scoring created; post-hoc ligand failure analysis 2026-08-17; "
            "EXPOSED_AFTER_BLIND_V1",
            "NOT_ESTABLISHED", "CONFIRMED", BLIND_V1_SRC,
            "Identity verified from reserve_source_snapshot_manifest.csv only; Gold, predictions "
            "and failure-analysis contents were NOT opened in this run.", pid="")

    # E. Test P blind papers (consumed; post-hoc error analysis exists).
    for doi in sorted(TEST_P):
        add(doi, "Test P final blind (Agent v4.1); Gold + post-hoc error analysis; "
                 "reused in p0 regression replays",
            "NOT_ESTABLISHED", "CONFIRMED",
            "local:reports/extraction_logs/agent_mvp_v4.1/test_p_final_blind_evaluation/ + " + EXCL_SRC,
            exclusions.get(doi, "")[:300])

    # F. Every other DOI in the historical exclusion list (prior Agent runs / Gold / regressions).
    for doi in sorted(exclusions):
        if doi in seen:
            continue
        first = exclusions[doi].split(";")[:2]
        add(doi, "prior Agent run / Gold / regression / normalization input (see exclusion_sources)",
            "NOT_ESTABLISHED", "CONFIRMED", EXCL_SRC,
            "exclusion_sources begins: " + "; ".join(first))

    # G. Production corpus + 64-paper corpus DOIs not yet covered.
    for r in memberships:
        doi = ndoi(r["DOI"])
        if doi and doi not in seen:
            add(doi, f"production corpus v1.1 member; prior role={r['prior role in Agent development/testing']}",
                "NOT_ESTABLISHED", "CONFIRMED", MEMB_SRC, r["production-use status"])
    for doi in sorted(corpus64 - seen):
        add(doi, "Fe/Ni 64-paper source-verified corpus (data repair / source verification)",
            "NOT_ESTABLISHED", "CONFIRMED", CORPUS64_SRC,
            "docs/real_development_set_v1.md: 64-set papers are inappropriate for future blind claims")

    with open(BENCH / "development_recovery_ledger.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        w.writerows(ledger)

    with open(BENCH / "development_manifest.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["paper_id", "doi", "metal", "title",
                                          "main_source_path", "si_source_path", "notes"])
        w.writeheader()
        w.writerows(dev_rows)

    # Known contamination: keep existing rows verbatim, append new CONTAMINATED rows.
    kc_path = BENCH / "known_contamination_manifest.csv"
    existing = rows(kc_path)
    have = {ndoi(r["doi"]) for r in existing}
    for rec in ledger:
        if rec["contamination_status"] == "CONTAMINATED" and rec["doi"] not in have:
            existing.append({
                "paper_id": rec["paper_id"], "doi": rec["doi"], "metal": rec["metal"],
                "title": rec["title"],
                "contamination_reason": f"{rec['historical_role']} [{rec['record_id']}]",
            })
            have.add(rec["doi"])
    with open(kc_path, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["paper_id", "doi", "metal", "title", "contamination_reason"])
        w.writeheader()
        w.writerows(existing)

    print(f"ledger rows={len(ledger)} dev={len(dev_rows)} known_contamination={len(existing)}")
    print(f"exclusions_v4 sha256={sha(excl_path)}")
    print(f"dev manifest_v1 sha256={sha(args.dev_manifest_v1)}")


if __name__ == "__main__":
    main()
