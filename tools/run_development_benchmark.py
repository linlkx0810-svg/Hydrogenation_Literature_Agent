"""Run the development-only extraction + verification benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.development_benchmark import evaluate_development, load_development_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare rule baseline, replayed LLM extraction, and verifier-retained "
            "fields on a development-only benchmark."
        )
    )
    parser.add_argument(
        "--dataset",
        default="examples/development_benchmark_v1.jsonl",
        help="Development JSONL dataset. Blind/reviewer-only paths are refused.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    results = evaluate_development(load_development_rows(Path(args.dataset)))
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    print("Hydrogenation Literature Agent - development benchmark")
    print("WARNING: synthetic/replayed engineering benchmark; not scientific performance")
    print(f"Examples: {results['examples']}")
    print()
    for name, metrics in results["systems"].items():
        print(name)
        print(f"  precision:              {metrics['precision']:.1%}")
        print(f"  recall:                 {metrics['recall']:.1%}")
        print(f"  F1:                     {metrics['f1']:.1%}")
        print(f"  attempted gold coverage:{metrics['attempted_gold_coverage']:>7.1%}")
        print(f"  answer rate:            {metrics['answer_rate']:>7.1%}")
        print(f"  hallucinations absent:  {metrics['hallucinations_on_absent']}")
        print(f"  abstentions present:    {metrics['abstentions_on_present']}")
        print()

    effect = results["verifier_effect"]
    print("verifier-v1 effect on replayed LLM fields")
    print(f"  precision delta:        {effect['precision_delta']:+.1%}")
    print(f"  recall delta:           {effect['recall_delta']:+.1%}")
    print(f"  wrong-value block rate: {effect['wrong_value_block_rate']:.1%}")
    print(f"  correct-value retention:{effect['correct_value_retention']:>7.1%}")


if __name__ == "__main__":
    main()
