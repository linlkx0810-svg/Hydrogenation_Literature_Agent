import csv

from tools.check_benchmark_overlap import check


HEADERS = [
    "paper_id",
    "doi",
    "metal",
    "title",
    "main_source_path",
    "si_source_path",
    "notes",
]


def _write_manifest(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def test_overlap_gate_passes_for_clean_paper_blocks(tmp_path):
    dev = tmp_path / "dev.csv"
    blind = tmp_path / "blind.csv"
    contamination = tmp_path / "contamination.csv"

    _write_manifest(
        dev,
        [{"paper_id": "DEV-1", "doi": "10.1/dev", "metal": "Fe"}],
    )
    _write_manifest(
        blind,
        [{"paper_id": "BLIND-1", "doi": "10.1/blind", "metal": "Ni"}],
    )
    _write_manifest(
        contamination,
        [{"paper_id": "OLD-1", "doi": "10.1/old", "metal": "Fe"}],
    )

    result = check(dev, blind, [contamination])
    assert result["status"] == "PASS"
    assert result["doi_overlap_count"] == 0
    assert result["known_contamination_doi_overlap_count"] == 0


def test_overlap_gate_blocks_known_historical_contamination(tmp_path):
    dev = tmp_path / "dev.csv"
    blind = tmp_path / "blind.csv"
    contamination = tmp_path / "contamination.csv"

    _write_manifest(
        dev,
        [{"paper_id": "DEV-1", "doi": "10.1/dev", "metal": "Fe"}],
    )
    _write_manifest(
        blind,
        [{
            "paper_id": "FE-H2-AH-0016",
            "doi": "https://doi.org/10.1021/JACS.1C04773",
            "metal": "Fe",
        }],
    )
    _write_manifest(
        contamination,
        [{
            "paper_id": "FE-H2-AH-0016",
            "doi": "10.1021/jacs.1c04773",
            "metal": "Fe",
        }],
    )

    result = check(dev, blind, [contamination])
    assert result["status"] == "FAIL"
    assert result["known_contamination_doi_overlap"] == [
        "10.1021/jacs.1c04773"
    ]
    assert result["known_contamination_paper_id_overlap"] == [
        "FE-H2-AH-0016"
    ]
