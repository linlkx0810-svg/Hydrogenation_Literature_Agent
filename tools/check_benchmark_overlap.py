"""Leakage gate for development vs blind benchmark manifests."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _doi(value):
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value.rstrip(".")


def _pid(value):
    return (value or "").strip().upper()


def _sha(path):
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def check(dev, blind):
    development = _rows(dev)
    held_out = _rows(blind)

    dev_doi = {_doi(row.get("doi")) for row in development if _doi(row.get("doi"))}
    blind_doi = {_doi(row.get("doi")) for row in held_out if _doi(row.get("doi"))}
    dev_pid = {_pid(row.get("paper_id")) for row in development if _pid(row.get("paper_id"))}
    blind_pid = {_pid(row.get("paper_id")) for row in held_out if _pid(row.get("paper_id"))}

    doi_overlap = sorted(dev_doi & blind_doi)
    paper_id_overlap = sorted(dev_pid & blind_pid)

    return {
        "status": "PASS" if not doi_overlap and not paper_id_overlap else "FAIL",
        "development_rows": len(development),
        "blind_rows": len(held_out),
        "doi_overlap_count": len(doi_overlap),
        "paper_id_overlap_count": len(paper_id_overlap),
        "doi_overlap": doi_overlap,
        "paper_id_overlap": paper_id_overlap,
        "development_manifest_sha256": _sha(dev),
        "blind_manifest_sha256": _sha(blind),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", required=True)
    parser.add_argument("--blind", required=True)
    parser.add_argument("--out", default="overlap_report.json")
    args = parser.parse_args()

    result = check(args.dev, args.blind)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
