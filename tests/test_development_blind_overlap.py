from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "check_development_blind_overlap.py"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def test_gate_passes_when_metadata_manifests_do_not_overlap(tmp_path: Path) -> None:
    development = tmp_path / "development.csv"
    heldout = tmp_path / "heldout.csv"
    _write_csv(
        development,
        [{"combined_record_id": "FE-H2-AH-0001", "doi": "10.1000/dev"}],
    )
    _write_csv(
        heldout,
        [{"paper_id": "CO-H2-AH-0001", "DOI": "https://doi.org/10.1000/blind"}],
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--development", str(development), "--heldout", str(heldout), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert '"gate": "PASS"' in proc.stdout
    assert '"overlap_detected": false' in proc.stdout


def test_gate_fails_on_normalized_doi_overlap(tmp_path: Path) -> None:
    development = tmp_path / "development.csv"
    heldout = tmp_path / "heldout.csv"
    _write_csv(
        development,
        [{"combined_record_id": "NI-H2-AH-0007", "doi": "10.1021/JACS.6B00519"}],
    )
    _write_csv(
        heldout,
        [{"paper_id": "OTHER-ID", "DOI": "https://doi.org/10.1021/jacs.6b00519"}],
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--development", str(development), "--heldout", str(heldout), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert '"gate": "FAIL"' in proc.stdout
    assert "10.1021/jacs.6b00519" in proc.stdout


def test_gate_fails_on_case_insensitive_record_id_overlap(tmp_path: Path) -> None:
    development = tmp_path / "development.csv"
    heldout = tmp_path / "heldout.jsonl"
    _write_csv(
        development,
        [{"combined_record_id": "FE-H2-AH-0017", "doi": "10.1000/no-overlap"}],
    )
    heldout.write_text('{"corpus_id":"fe-h2-ah-0017","doi":"10.1000/other"}\n', encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--development", str(development), "--heldout", str(heldout), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "FE-H2-AH-0017" in proc.stdout
