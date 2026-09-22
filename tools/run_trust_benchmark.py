"""Compare raw extraction with the evidence verifier on a common benchmark.

The verifier is allowed to abstain. Report both end-to-end correctness and
selective accuracy so that higher precision obtained by refusing unsupported
fields is not mistaken for better overall extraction.
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
    raw = Counter()
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
                raw["total"] += 1
                by_field[field]["total"] += 1

                if pred is None:
                    raw["incorrect"] += 1
                    verified["abstain"] += 1
                    by_field[field]["raw_incorrect"] += 1
                    by_field[field]["abstain"] += 1
                    continue

                predicted_value = getattr(pred, field, None)
                raw_ok = _norm(predicted_value) == _norm(exp[field])
                raw["correct" if raw_ok else "incorrect"] += 1
                by_field[field][
                    "raw_correct" if raw_ok else "raw_incorrect"
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

    total = raw["total"]
    answered = verified["correct"] + verified["incorrect"]
    result = {
        "examples": len(rows),
        "candidate_count_accuracy": _safe(count_correct, len(rows)),
        "raw": {
            "correct": raw["correct"],
            "incorrect": raw["incorrect"],
            "total": total,
            "end_to_end_correct_rate": _safe(raw["correct"], total),
            "coverage": 1.0 if total else None,
            "selective_accuracy": _safe(raw["correct"], total),
        },
        "verifier": {
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
            "raw_accuracy": _safe(
                counts["raw_correct"], counts["total"]
            ),
            "verifier_end_to_end_correct_rate": _safe(
                counts["verified_correct"], counts["total"]
            ),
            "verifier_coverage": _safe(
                answered_field, counts["total"]
            ),
            "verifier_selective_accuracy": _safe(
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

    print("Hydrogenation Literature Agent - trust benchmark")
    print(f"Examples: {results['examples']}")
    print(
        "Raw accuracy: "
        f"{results['raw']['end_to_end_correct_rate']:.1%}"
    )
    print(
        "Verifier end-to-end: "
        f"{results['verifier']['end_to_end_correct_rate']:.1%}"
    )
    print(
        "Verifier coverage: "
        f"{results['verifier']['coverage']:.1%}"
    )
    print(
        "Verifier selective accuracy: "
        f"{results['verifier']['selective_accuracy']:.1%}"
    )


if __name__ == "__main__":
    main()
