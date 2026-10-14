"""Build the text corpus the candidate-binding audit reads, and attest it.

The binding audit reads one `.txt` per source artifact. That corpus used to be
produced ad hoc outside the repository, so `candidate_binding_v1.csv` could not
be regenerated: rerunning the audit against a differently extracted corpus
silently moved cases between binding statuses. This tool makes the corpus a
derived artifact with a stated input, a pinned extractor and a hash per file.

The paper PDFs are not in the repository and are not redistributed here, so the
corpus itself is never committed. What is committed is the manifest: the sha256
of every text artifact plus the extractor version that produced it. Anyone
holding the PDFs can rebuild a byte-identical corpus and verify it against the
manifest; `audit_candidate_binding.py --corpus-manifest` refuses to run against
a corpus that does not match.

Layout expected under --pdf-root:

    main_articles/<paper_id>__*.pdf
    supporting_information/<paper_id>__*__SI.pdf

Output under --out-dir:

    <paper_id>.txt          (main article)
    <paper_id>_SI.txt       (supporting information, when a PDF exists)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CORPUS_VERSION = "binding-corpus-v1"
MANIFEST_PATH = PROJECT_ROOT / "benchmark" / "development_gold" / "binding_corpus_manifest.json"


class CorpusError(RuntimeError):
    """Raised when the corpus cannot be built or does not match its manifest."""


def _pdf_text(path: Path) -> str:
    """Extract text exactly the way the rest of the project does."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _find(pdf_root: Path, paper_id: str) -> tuple[Path | None, Path | None]:
    main = sorted((pdf_root / "main_articles").glob(f"{paper_id}__*.pdf"))
    si = sorted((pdf_root / "supporting_information").glob(f"{paper_id}__*.pdf"))
    return (main[0] if main else None, si[0] if si else None)


def _write(text: str, out: Path) -> str:
    """Write LF-normalized text and return its sha256."""
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    out.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def build(paper_ids: list[str], pdf_root: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    import pypdf

    artifacts: dict[str, dict[str, str]] = {}
    missing = []
    for paper_id in paper_ids:
        main_pdf, si_pdf = _find(pdf_root, paper_id)
        if main_pdf is None:
            missing.append(paper_id)
            continue
        entry = {"MAIN": _write(_pdf_text(main_pdf), out_dir / f"{paper_id}.txt")}
        if si_pdf is not None:
            entry["SI"] = _write(_pdf_text(si_pdf), out_dir / f"{paper_id}_SI.txt")
        artifacts[paper_id] = entry

    if missing:
        raise CorpusError(f"no main-article PDF for: {', '.join(missing)}")

    return {
        "corpus_version": CORPUS_VERSION,
        "extractor": "pypdf.PdfReader.extract_text joined by newline",
        "pypdf_version": pypdf.__version__,
        "normalization": "CRLF and CR collapsed to LF; UTF-8",
        "papers": len(artifacts),
        "artifacts": artifacts,
    }


def verify(manifest: dict, corpus_dir: Path) -> list[str]:
    """Return every mismatch between a manifest and a corpus on disk."""
    problems = []
    for paper_id, roles in manifest["artifacts"].items():
        for role, expected in roles.items():
            name = f"{paper_id}.txt" if role == "MAIN" else f"{paper_id}_{role}.txt"
            path = corpus_dir / name
            if not path.exists():
                problems.append(f"{name}: missing from the corpus")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                problems.append(f"{name}: sha256 {actual[:12]} does not match manifest {expected[:12]}")
    return problems


def _paper_ids(gold_path: Path) -> list[str]:
    return [
        json.loads(line)["paper_id"]
        for line in gold_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-root", required=True, help="directory holding main_articles/ and supporting_information/")
    parser.add_argument("--out-dir", required=True, help="where the .txt corpus is written")
    parser.add_argument(
        "--gold",
        default=str(PROJECT_ROOT / "benchmark/development_gold/development_gold_field_schema_v1.jsonl"),
    )
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check an existing corpus against the committed manifest instead of rebuilding",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    corpus_dir = Path(args.out_dir)

    if args.verify:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        problems = verify(manifest, corpus_dir)
        print(json.dumps({"corpus_version": manifest["corpus_version"],
                          "verified": not problems, "problems": problems}, indent=2))
        return 1 if problems else 0

    manifest = build(_paper_ids(Path(args.gold)), Path(args.pdf_root), corpus_dir)
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"corpus_version": manifest["corpus_version"],
                      "papers": manifest["papers"],
                      "pypdf_version": manifest["pypdf_version"],
                      "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
