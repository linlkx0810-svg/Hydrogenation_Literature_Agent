#!/usr/bin/env python3
"""Fail closed when a real development set overlaps a held-out metadata manifest.

This tool intentionally consumes metadata only. Do not supply reviewer-only gold,
sealed predictions, adjudicated answers, or source evidence to this command.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

ID_KEYS = ("combined_record_id", "paper_id", "corpus_id", "record_id")
DOI_KEYS = ("doi", "DOI")


def _norm_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _norm_doi(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    return text or None


def _read_records(path: Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix in {".jsonl", ".ndjson"}:
        records: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError(f"{path}:{line_no}: expected JSON object")
                records.append(obj)
        return records
    if suffix == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return [x for x in obj if isinstance(x, dict)]
        if isinstance(obj, dict):
            for key in ("papers", "records", "items", "manifest"):
                value = obj.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
            return [obj]
        raise ValueError(f"{path}: unsupported JSON structure")
    raise ValueError(f"Unsupported manifest format: {path}; use CSV, JSON, or JSONL")


def _first(record: dict[str, object], keys: Iterable[str]) -> object | None:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _index(records: list[dict[str, object]]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    dois: set[str] = set()
    for record in records:
        rid = _norm_id(_first(record, ID_KEYS))
        doi = _norm_doi(_first(record, DOI_KEYS))
        if rid:
            ids.add(rid)
        if doi:
            dois.add(doi)
    return ids, dois


def check_overlap(dev_path: Path, blind_paths: list[Path]) -> dict[str, object]:
    dev_records = _read_records(dev_path)
    dev_ids, dev_dois = _index(dev_records)
    if not dev_ids and not dev_dois:
        raise ValueError("Development manifest contains no recognizable paper IDs or DOIs")

    overlaps: list[dict[str, object]] = []
    blind_summary: list[dict[str, object]] = []
    for blind_path in blind_paths:
        blind_records = _read_records(blind_path)
        blind_ids, blind_dois = _index(blind_records)
        if not blind_ids and not blind_dois:
            raise ValueError(
                f"Held-out manifest {blind_path} contains no recognizable paper IDs or DOIs"
            )
        matched_ids = sorted(dev_ids & blind_ids)
        matched_dois = sorted(dev_dois & blind_dois)
        blind_summary.append(
            {
                "path": str(blind_path),
                "records": len(blind_records),
                "recognized_ids": len(blind_ids),
                "recognized_dois": len(blind_dois),
            }
        )
        if matched_ids or matched_dois:
            overlaps.append(
                {
                    "path": str(blind_path),
                    "matched_ids": matched_ids,
                    "matched_dois": matched_dois,
                }
            )

    return {
        "development_manifest": str(dev_path),
        "development_records": len(dev_records),
        "heldout_manifests_checked": blind_summary,
        "overlap_detected": bool(overlaps),
        "overlaps": overlaps,
        "gate": "FAIL" if overlaps else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a NON-BLIND development manifest against metadata-only held-out manifests."
    )
    parser.add_argument("--development", required=True, type=Path)
    parser.add_argument(
        "--heldout",
        required=True,
        nargs="+",
        type=Path,
        help="Metadata-only held-out/blind manifest(s). Never pass gold or sealed predictions.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    result = check_overlap(args.development, args.heldout)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Development records: {result['development_records']}")
        print(f"Held-out manifests checked: {len(result['heldout_manifests_checked'])}")
        print(f"Gate: {result['gate']}")
        for overlap in result["overlaps"]:
            print(f"Overlap in {overlap['path']}")
            if overlap["matched_ids"]:
                print("  IDs: " + ", ".join(overlap["matched_ids"]))
            if overlap["matched_dois"]:
                print("  DOIs: " + ", ".join(overlap["matched_dois"]))

    return 1 if result["overlap_detected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
