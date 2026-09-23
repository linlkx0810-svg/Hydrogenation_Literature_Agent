"""Unified CLI for the Hydrogenation Literature Agent.

The CLI intentionally exposes deterministic, auditable operations that can run
without API keys. Retrieval and PDF stages remain available through the existing
pipeline scripts; this entry point gives reviewers a fast way to exercise the
reaction-level agent and benchmark it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from modules.extraction_verifier import verify_candidates
from modules.prediction_normalizer import normalize_record
from modules.raw_llm_extractor_v2 import (
    EXTRACTION_VERSION as RAW_EXTRACTION_VERSION,
    PROMPT_VERSION as RAW_PROMPT_VERSION,
    SCHEMA_VERSION as RAW_SCHEMA_VERSION,
    ReplayJSONProvider,
    build_request,
    extract_reaction_chunk,
)
from modules.reaction_candidate_extraction import candidates_to_dicts, extract_reaction_candidates
from tools.run_benchmark import evaluate, load_jsonl
from tools.run_trust_benchmark import evaluate as evaluate_trust


def command_extract_text(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
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
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {len(candidates)} candidate(s) to {args.output}")
    else:
        print(rendered)
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    results = evaluate(load_jsonl(Path(args.dataset)))
    print(json.dumps(results, indent=2))
    return 0


def command_verify_text(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    candidates = extract_reaction_candidates(
        text, context_sentences=args.context
    )
    normalizations = {
        candidate.candidate_id: normalize_record(
            {
                "candidate_id": candidate.candidate_id,
                "source_artifact_id": str(input_path),
                "values": {"ligand": candidate.ligand},
                "abstention_reasons": {},
            },
            text,
        )
        for candidate in candidates
    }
    verifications = verify_candidates(candidates, text, normalizations)
    payload = {
        "agent": "Hydrogenation Literature Agent",
        "extractor": "rule-baseline-v1",
        "normalizer": "prediction-normalizer-v1",
        "verifier": "evidence-verifier-v1",
        "source": str(input_path),
        "candidate_count": len(candidates),
        "decision_counts": {
            status: sum(
                verification.overall_status == status
                for verification in verifications
            )
            for status in ("accept", "review", "reject")
        },
        "records": [
            {
                "candidate": candidate.to_dict(),
                "verification": verification.to_dict(),
            }
            for candidate, verification in zip(candidates, verifications)
        ],
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(
            f"Wrote {len(candidates)} verified candidate(s) "
            f"to {args.output}"
        )
    else:
        print(rendered)
    return 0


def _load_replay(path: Path) -> dict:
    """Load saved provider responses keyed by candidate id."""
    replay = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        replay[row["candidate_id"]] = row["response"]
    return replay


def command_extract_raw(args: argparse.Namespace) -> int:
    """Run source -> evidence builder -> Raw LLM extractor (llm-extractor-v2).

    Without --replay or --provider the command is a dry run: it writes the exact
    request envelopes that would be sent, and produces no prediction. This keeps
    CI and offline review able to exercise the chain without a model.
    """
    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    candidates = extract_reaction_candidates(text, context_sentences=args.context)
    source_id = args.source_id or input_path.name

    if args.replay:
        replay = _load_replay(Path(args.replay))
        records = []
        for candidate in candidates:
            if candidate.candidate_id not in replay:
                print(f"no replay response for {candidate.candidate_id}", file=sys.stderr)
                return 2
            provider = ReplayJSONProvider(
                replay[candidate.candidate_id], model_name=args.model
            )
            record = extract_reaction_chunk(
                candidate.evidence_text,
                provider,
                candidate_id=candidate.candidate_id,
                source_artifact_id=source_id,
                evidence_start=candidate.evidence_start,
                evidence_end=candidate.evidence_end,
            )
            records.append(record.to_dict())
        rendered = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        if args.output:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
            print(f"Wrote {len(records)} raw prediction(s) to {args.output}")
        else:
            print(rendered)
        return 0

    envelopes = [
        {
            "candidate_id": candidate.candidate_id,
            "source_artifact_id": source_id,
            "evidence_start": candidate.evidence_start,
            "evidence_end": candidate.evidence_end,
            "extraction_version": RAW_EXTRACTION_VERSION,
            "prompt_version": RAW_PROMPT_VERSION,
            "schema_version": RAW_SCHEMA_VERSION,
            "request": {
                "system_prompt": build_request(candidate.evidence_text).system_prompt,
                "user_prompt": build_request(candidate.evidence_text).user_prompt,
                "response_schema": build_request(candidate.evidence_text).response_schema,
            },
        }
        for candidate in candidates
    ]
    payload = {
        "mode": "dry-run-requests-only",
        "note": "No model was called and no prediction was produced.",
        "source": str(input_path),
        "candidate_count": len(candidates),
        "envelopes": envelopes,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {len(envelopes)} request envelope(s) to {args.output}")
    else:
        print(rendered)
    return 0


def command_trust_benchmark(args: argparse.Namespace) -> int:
    results = evaluate_trust(load_jsonl(Path(args.dataset)))
    print(json.dumps(results, indent=2))
    return 0


def command_run_chain(args: argparse.Namespace) -> int:
    from tools.run_chain import run as run_chain_stage
    from modules.artifact_chain import FrozenArtifactError

    try:
        report = run_chain_stage(
            Path(args.raw), Path(args.freeze), Path(args.source), Path(args.out_dir)
        )
    except FrozenArtifactError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2))
    return 0


def command_score(args: argparse.Namespace) -> int:
    from tools.score_agent_v1 import _read_jsonl, score
    from modules.artifact_chain import FrozenArtifactError, load_frozen_raw

    try:
        records, _ = load_frozen_raw(Path(args.raw), Path(args.freeze))
    except FrozenArtifactError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, indent=2))
        return 2
    report = score(records, _read_jsonl(Path(args.verified)), _read_jsonl(Path(args.gold)))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote score report to {args.output}")
    else:
        print(json.dumps(report, indent=2))
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

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the deterministic field-level extraction benchmark.",
    )
    benchmark_parser.add_argument(
        "--dataset", default="examples/benchmark_synthetic.jsonl",
        help="JSONL benchmark dataset",
    )
    benchmark_parser.set_defaults(func=command_benchmark)

    verify_parser = subparsers.add_parser(
        "verify-text",
        help="Extract candidates and independently verify bound evidence.",
    )
    verify_parser.add_argument("--input", required=True, help="UTF-8 text file")
    verify_parser.add_argument("--output", help="Optional JSON output path")
    verify_parser.add_argument(
        "--context", type=int, default=2,
        help="Number of neighboring sentences to include around result anchors",
    )
    verify_parser.set_defaults(func=command_verify_text)

    trust_parser = subparsers.add_parser(
        "trust-benchmark",
        help="Compare raw extraction with verifier-gated extraction.",
    )
    trust_parser.add_argument(
        "--dataset", default="examples/benchmark_synthetic.jsonl",
        help="JSONL benchmark dataset",
    )
    trust_parser.set_defaults(func=command_trust_benchmark)

    raw_parser = subparsers.add_parser(
        "extract-raw",
        help="Build evidence chunks and run the Raw LLM extractor (llm-extractor-v2).",
    )
    raw_parser.add_argument("--input", required=True, help="UTF-8 text file")
    raw_parser.add_argument("--output", help="Optional output path")
    raw_parser.add_argument(
        "--context", type=int, default=2,
        help="Number of neighboring sentences to include around result anchors",
    )
    raw_parser.add_argument("--source-id", help="Source artifact identifier for provenance")
    raw_parser.add_argument(
        "--replay",
        help="JSONL of saved provider responses ({candidate_id, response}); offline replay",
    )
    raw_parser.add_argument(
        "--model", default="replay-json",
        help="Model name recorded in the raw prediction records",
    )
    raw_parser.set_defaults(func=command_extract_raw)

    chain_parser = subparsers.add_parser(
        "run-chain",
        help="Frozen raw prediction -> normalization -> evidence verifier.",
    )
    chain_parser.add_argument("--raw", required=True, help="frozen raw prediction JSONL")
    chain_parser.add_argument("--freeze", required=True, help="raw freeze manifest JSON")
    chain_parser.add_argument("--source", required=True, help="source text used for extraction")
    chain_parser.add_argument("--out-dir", required=True, help="directory for chain artifacts")
    chain_parser.set_defaults(func=command_run_chain)

    score_parser = subparsers.add_parser(
        "score",
        help="Score Raw and Verified predictions under SCORING_CONTRACT_V1.",
    )
    score_parser.add_argument("--raw", required=True)
    score_parser.add_argument("--freeze", required=True)
    score_parser.add_argument("--verified", required=True)
    score_parser.add_argument("--gold", required=True)
    score_parser.add_argument("--output", help="Optional score report path")
    score_parser.set_defaults(func=command_score)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
