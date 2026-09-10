"""Unified CLI for the Hydrogenation Literature Agent.

The CLI intentionally exposes deterministic, auditable operations that can run
without API keys. Retrieval and PDF stages remain available through the existing
pipeline scripts; this entry point gives reviewers a fast way to exercise the
reaction-level agent and benchmark it.

Reviewer-only and blind-gold inputs are blocked during ordinary development.
Benchmark evaluation against such material requires explicit evaluation mode.

`llm-extract-replay` validates the `llm-extractor-v1` contract using a saved JSON
provider response. `verify-replay` validates field-level verifier behavior using
saved strict judgements. These are deterministic replay tools, not network model
clients.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.blind_integrity import assert_safe_input_path, assert_safe_output_path
from modules.llm_extractor import ReplayJSONProvider, extract_reaction_chunk
from modules.reaction_candidate_extraction import candidates_to_dicts, extract_reaction_candidates
from modules.verifier import ReplayVerifierProvider, verify_candidate
from tools.run_benchmark import evaluate, load_jsonl


def command_extract_text(args: argparse.Namespace) -> int:
    input_path = assert_safe_input_path(Path(args.input), evaluation_mode=False)
    text = input_path.read_text(encoding="utf-8")
    candidates = extract_reaction_candidates(text, context_sentences=args.context)
    payload = {
        "agent": "Hydrogenation Literature Agent",
        "extractor": "rule-baseline-v1",
        "source": str(input_path),
        "candidate_count": len(candidates),
        "candidates": candidates_to_dicts(candidates),
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        output_path = assert_safe_output_path(Path(args.output), purpose="model")
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {len(candidates)} candidate(s) to {output_path}")
    else:
        print(rendered)
    return 0


def command_llm_extract_replay(args: argparse.Namespace) -> int:
    evidence_path = assert_safe_input_path(Path(args.input), evaluation_mode=False)
    response_path = assert_safe_input_path(Path(args.response), evaluation_mode=False)
    evidence = evidence_path.read_text(encoding="utf-8")
    response = json.loads(response_path.read_text(encoding="utf-8"))

    provider = ReplayJSONProvider(response=response, model_name=args.model_name)
    result = extract_reaction_chunk(
        evidence,
        provider,
        candidate_id=args.candidate_id,
        evidence_start=args.evidence_start,
        source_locator={"source": str(evidence_path)},
    )
    payload = {
        "agent": "Hydrogenation Literature Agent",
        "extractor": "llm-extractor-v1",
        "source": str(evidence_path),
        "provider_mode": "replay",
        "candidate": result.to_dict(),
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        output_path = assert_safe_output_path(Path(args.output), purpose="model")
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote LLM candidate to {output_path}")
    else:
        print(rendered)
    return 0


def command_verify_replay(args: argparse.Namespace) -> int:
    candidate_path = assert_safe_input_path(Path(args.candidate), evaluation_mode=False)
    responses_path = assert_safe_input_path(Path(args.responses), evaluation_mode=False)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    responses = json.loads(responses_path.read_text(encoding="utf-8"))

    provider = ReplayVerifierProvider(
        responses=responses,
        model_name=args.model_name,
    )
    result = verify_candidate(candidate, provider=provider)
    payload = {
        "agent": "Hydrogenation Literature Agent",
        "verifier": "verifier-v1",
        "provider_mode": "replay",
        "candidate_source": str(candidate_path),
        "verification": result.to_dict(),
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        output_path = assert_safe_output_path(Path(args.output), purpose="model")
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote verification result to {output_path}")
    else:
        print(rendered)
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    results = evaluate(
        load_jsonl(Path(args.dataset), evaluation_mode=args.evaluation_mode)
    )
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
    extract_parser.set_defaults(func=command_extract_text)

    replay_parser = subparsers.add_parser(
        "llm-extract-replay",
        help=(
            "Validate llm-extractor-v1 using one evidence chunk and a saved strict "
            "JSON provider response. No network model call is made."
        ),
    )
    replay_parser.add_argument(
        "--input", required=True,
        help="UTF-8 file containing one already-selected evidence chunk",
    )
    replay_parser.add_argument(
        "--response", required=True,
        help="JSON file containing exactly the eight LLM extraction fields",
    )
    replay_parser.add_argument(
        "--model-name", default="replay-json",
        help="Model/provider name recorded in extraction metadata",
    )
    replay_parser.add_argument(
        "--candidate-id", default="rxn-llm-0001",
        help="Caller-controlled candidate identifier",
    )
    replay_parser.add_argument(
        "--evidence-start", type=int, default=0,
        help="Optional source character offset for the beginning of the chunk",
    )
    replay_parser.add_argument("--output", help="Optional JSON output path")
    replay_parser.set_defaults(func=command_llm_extract_replay)

    verify_parser = subparsers.add_parser(
        "verify-replay",
        help=(
            "Validate verifier-v1 on a saved candidate and saved strict field "
            "judgements. No network model call is made."
        ),
    )
    verify_parser.add_argument(
        "--candidate", required=True,
        help="JSON candidate containing scientific fields and evidence_text",
    )
    verify_parser.add_argument(
        "--responses", required=True,
        help="JSON mapping each scientific field to status/reason_code",
    )
    verify_parser.add_argument(
        "--model-name", default="replay-verifier",
        help="Verifier model/provider name recorded in metadata",
    )
    verify_parser.add_argument("--output", help="Optional JSON output path")
    verify_parser.set_defaults(func=command_verify_replay)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the deterministic field-level extraction benchmark.",
    )
    benchmark_parser.add_argument(
        "--dataset", default="examples/benchmark_synthetic.jsonl",
        help="JSONL benchmark dataset",
    )
    benchmark_parser.add_argument(
        "--evaluation-mode",
        action="store_true",
        help=(
            "Explicitly authorise evaluation against reviewer-only/blind-gold "
            "inputs. Never use this flag for extractor or prompt development."
        ),
    )
    benchmark_parser.set_defaults(func=command_benchmark)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
