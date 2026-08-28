"""Run a small deterministic benchmark for the reaction candidate extractor.

The benchmark format is JSONL. Each row contains `text` and `expected`, where
`expected` is a list of reaction records. This runner reports field-level exact
match accuracy and candidate-count accuracy. It is intentionally lightweight so
it can run in CI without API keys or copyrighted source material.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def _normalise(value):
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, float):
        return round(value, 4)
    return value


def evaluate(rows: list[dict]) -> dict:
    field_correct = {field: 0 for field in FIELDS}
    field_total = {field: 0 for field in FIELDS}
    count_correct = 0

    for row in rows:
        predicted = [
            c.to_dict()
            for c in extract_reaction_candidates(
                row["text"], row.get("context_sentences", 0)
            )
        ]
        expected = row.get("expected", [])
        if len(predicted) == len(expected):
            count_correct += 1

        for exp, pred in zip(expected, predicted):
            for field in FIELDS:
                if field not in exp:
                    continue
                field_total[field] += 1
                if _normalise(exp[field]) == _normalise(pred.get(field)):
                    field_correct[field] += 1

    field_accuracy = {
        field: (field_correct[field] / field_total[field] if field_total[field] else None)
        for field in FIELDS
    }
    scored = [v for v in field_accuracy.values() if v is not None]
    return {
        "examples": len(rows),
        "candidate_count_accuracy": count_correct / len(rows) if rows else 0.0,
        "field_accuracy": field_accuracy,
        "macro_field_accuracy": sum(scored) / len(scored) if scored else 0.0,
    }


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="examples/benchmark_synthetic.jsonl")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    results = evaluate(load_jsonl(Path(args.dataset)))
    if args.json:
        print(json.dumps(results, indent=2))
        return

    print("Hydrogenation Literature Agent - extraction benchmark")
    print(f"Examples: {results['examples']}")
    print(f"Candidate-count accuracy: {results['candidate_count_accuracy']:.1%}")
    print(f"Macro field accuracy: {results['macro_field_accuracy']:.1%}")
    for field, score in results["field_accuracy"].items():
        if score is not None:
            print(f"  {field:22s} {score:.1%}")


if __name__ == "__main__":
    main()
