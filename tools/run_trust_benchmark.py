"""Engineering contract check: deterministic rule baseline vs the evidence verifier.

This tool does NOT evaluate the Raw LLM extractor. The system it labels
`rule_baseline` is the deterministic regex extractor of
`modules.reaction_candidate_extraction` (`rule-baseline-v1`). The formal Raw LLM
stage is `llm-extractor-v2`, scored by `tools/score_agent_v1.py`.

Historical reports from this tool used the label `raw` for the same
deterministic baseline. Those files are left untouched; the label was wrong and
is corrected here, not rewritten there.

The verifier is allowed to abstain. Both end-to-end correctness and selective
accuracy are reported so that higher precision obtained by refusing unsupported
fields is not mistaken for better extraction.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.extraction_verifier import verify_candidate
from modules.reaction_candidate_extraction import extract_reaction_candidates

FIELDS = (
    "ee_percent",
    "yield_percent",
    "h2_pressure_bar",
    "temperature_c",
    "reaction_time_h",
    "solvent",
    "ligand",
    "substrate_class",
)


def _norm(value):
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, float):
        return round(value, 4)
    return value


def _safe(a, b):
    return a / b if b else None


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate(rows):
    rule_baseline = Counter()
    verified = Counter()
    by_field = {field: Counter() for field in FIELDS}
    overall = Counter()
    count_correct = 0

    for row in rows:
        predicted = extract_reaction_candidates(
            row["text"], row.get("context_sentences", 0)
        )
        expected = row.get("expected", [])
        if len(predicted) == len(expected):
            count_correct += 1

        for index, exp in enumerate(expected):
            pred = predicted[index] if index < len(predicted) else None
            verification_map = {}
            if pred is not None:
                verification = verify_candidate(pred, row["text"])
                overall[verification.overall_status] += 1
                verification_map = {
                    result.field: result
                    for result in verification.fields
                }

            for field in FIELDS:
                if field not in exp:
                    continue
                rule_baseline["total"] += 1
                by_field[field]["total"] += 1

                if pred is None:
                    rule_baseline["incorrect"] += 1
                    verified["abstain"] += 1
                    by_field[field]["rule_baseline_incorrect"] += 1
                    by_field[field]["abstain"] += 1
                    continue

                predicted_value = getattr(pred, field, None)
                baseline_ok = _norm(predicted_value) == _norm(exp[field])
                rule_baseline["correct" if baseline_ok else "incorrect"] += 1
                by_field[field][
                    "rule_baseline_correct" if baseline_ok else "rule_baseline_incorrect"
                ] += 1

                decision = verification_map.get(field)
                if decision is None or decision.status != "supported":
                    verified["abstain"] += 1
                    by_field[field]["abstain"] += 1
                else:
                    ok = _norm(predicted_value) == _norm(exp[field])
                    verified["correct" if ok else "incorrect"] += 1
                    by_field[field][
                        "verified_correct" if ok else "verified_incorrect"
                    ] += 1

    total = rule_baseline["total"]
    answered = verified["correct"] + verified["incorrect"]
    result = {
        "examples": len(rows),
        "candidate_count_accuracy": _safe(count_correct, len(rows)),
        "system_under_test": "rule-baseline-v1 (deterministic regex extractor), NOT the Raw LLM",
        "rule_baseline": {
            "correct": rule_baseline["correct"],
            "incorrect": rule_baseline["incorrect"],
            "total": total,
            "end_to_end_correct_rate": _safe(rule_baseline["correct"], total),
            "coverage": 1.0 if total else None,
            "selective_accuracy": _safe(rule_baseline["correct"], total),
        },
        "rule_baseline_verified": {
            "correct": verified["correct"],
            "incorrect": verified["incorrect"],
            "abstain": verified["abstain"],
            "total": total,
            "end_to_end_correct_rate": _safe(
                verified["correct"], total
            ),
            "coverage": _safe(answered, total),
            "selective_accuracy": _safe(
                verified["correct"], answered
            ),
            "candidate_decisions": dict(overall),
        },
        "field_breakdown": {},
    }

    for field, counts in by_field.items():
        if not counts["total"]:
            continue
        answered_field = (
            counts["verified_correct"] + counts["verified_incorrect"]
        )
        result["field_breakdown"][field] = {
            "n": counts["total"],
            "rule_baseline_accuracy": _safe(
                counts["rule_baseline_correct"], counts["total"]
            ),
            "rule_baseline_verified_end_to_end_correct_rate": _safe(
                counts["verified_correct"], counts["total"]
            ),
            "rule_baseline_verified_coverage": _safe(
                answered_field, counts["total"]
            ),
            "rule_baseline_verified_selective_accuracy": _safe(
                counts["verified_correct"], answered_field
            ),
            "abstain": counts["abstain"],
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default="examples/benchmark_synthetic.jsonl",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = evaluate(load_jsonl(Path(args.dataset)))
    if args.json:
        print(json.dumps(results, indent=2))
        return

    print("Hydrogenation Literature Agent - rule-baseline trust benchmark")
    print("System under test: rule-baseline-v1 (deterministic), not the Raw LLM")
    print(f"Examples: {results['examples']}")
    print(
        "Rule-baseline accuracy: "
        f"{results['rule_baseline']['end_to_end_correct_rate']:.1%}"
    )
    print(
        "Rule-baseline + verifier end-to-end: "
        f"{results['rule_baseline_verified']['end_to_end_correct_rate']:.1%}"
    )
    print(
        "Verifier coverage: "
        f"{results['rule_baseline_verified']['coverage']:.1%}"
    )
    print(
        "Verifier selective accuracy: "
        f"{results['rule_baseline_verified']['selective_accuracy']:.1%}"
    )


if __name__ == "__main__":
    main()
