"""Unified CLI for the Hydrogenation Literature Agent.

The CLI intentionally exposes deterministic, auditable operations that can run
without API keys. Retrieval and PDF stages remain available through the existing
pipeline scripts; this entry point gives reviewers a fast way to exercise the
reaction-level agent and benchmark it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.extraction_backends import get_backend
from modules.reaction_candidate_extraction import candidates_to_dicts
from tools.run_benchmark import evaluate, load_jsonl


def command_extract_text(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    backend = get_backend(args.backend)
    candidates = backend.extract(text, context_sentences=args.context)
    payload = {
        "agent": "Hydrogenation Literature Agent",
        "extractor": backend.name,
        "source": str(input_path),
        "candidate_count": len(candidates),
        "candidates": candidates_to_dicts(candidates),
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {len(candidates)} candidate(s) to {args.output}")
    else:
        print(rendered)
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    results = evaluate(load_jsonl(Path(args.dataset)))
    print(json.dumps(results, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hla-agent",
        description="Auditable literature-mining agent for H2 asymmetric hydrogenation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract-text",
        help="Extract provenance-aware reaction candidates from plain text.",
    )
    extract_parser.add_argument("--input", required=True, help="UTF-8 text file")
    extract_parser.add_argument("--output", help="Optional JSON output path")
    extract_parser.add_argument(
        "--context", type=int, default=2,
        help="Number of neighboring sentences to include around result anchors",
    )
    extract_parser.add_argument(
        "--backend", default="rule", choices=["rule"],
        help="Extraction backend. The deterministic rule backend is the current built-in baseline.",
    )
    extract_parser.set_defaults(func=command_extract_text)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the deterministic field-level extraction benchmark.",
    )
    benchmark_parser.add_argument(
        "--dataset", default="examples/benchmark_synthetic.jsonl",
        help="JSONL benchmark dataset",
    )
    benchmark_parser.set_defaults(func=command_benchmark)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
