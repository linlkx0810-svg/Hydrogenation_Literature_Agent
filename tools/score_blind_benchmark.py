"""Score reaction×field adjudication for Raw LLM and Verifier systems."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _safe(a, b):
    return a / b if b else None


def score(rows):
    output = {}
    stages = defaultdict(list)
    for row in rows:
        stages[(row.get("system_stage") or "unspecified").strip()].append(row)

    for stage, stage_rows in stages.items():
        evaluable = [
            row for row in stage_rows
            if row.get("value_result") != "not_applicable"
        ]
        correct = [
            row for row in evaluable
            if row.get("value_result") == "correct"
        ]
        incorrect = [
            row for row in evaluable
            if row.get("value_result") == "incorrect"
        ]
        abstain_reasonable = [
            row for row in evaluable
            if row.get("value_result") == "abstain_reasonable"
        ]
        abstain_unnecessary = [
            row for row in evaluable
            if row.get("value_result") == "abstain_unnecessary"
        ]
        answered = correct + incorrect
        evidence_evaluable = [
            row for row in answered
            if row.get("evidence_result") != "not_applicable"
        ]
        evidence_supported = [
            row for row in evidence_evaluable
            if row.get("evidence_result") == "supported"
        ]
        evidence_unsupported = [
            row for row in evidence_evaluable
            if row.get("evidence_result") == "unsupported"
        ]
        gold_unresolvable = [
            row for row in evaluable
            if (row.get("gold_resolvability") or "").lower()
            in {"unresolvable", "ambiguous", "missing", "conflict"}
        ]
        errors = Counter(
            row.get("error_type")
            for row in evaluable
            if row.get("error_type")
        )

        fields = {}
        for field in sorted({row.get("field", "") for row in evaluable}):
            field_rows = [
                row for row in evaluable
                if row.get("field", "") == field
            ]
            field_correct = sum(
                row.get("value_result") == "correct"
                for row in field_rows
            )
            field_answered = sum(
                row.get("value_result") in {"correct", "incorrect"}
                for row in field_rows
            )
            fields[field] = {
                "n": len(field_rows),
                "end_to_end_correct_rate": _safe(
                    field_correct, len(field_rows)
                ),
                "selective_accuracy": _safe(
                    field_correct, field_answered
                ),
                "coverage": _safe(
                    field_answered, len(field_rows)
                ),
            }

        output[stage] = {
            "n_evaluable": len(evaluable),
            "correct": len(correct),
            "incorrect": len(incorrect),
            "abstain_reasonable": len(abstain_reasonable),
            "abstain_unnecessary": len(abstain_unnecessary),
            "end_to_end_correct_rate": _safe(
                len(correct), len(evaluable)
            ),
            "selective_accuracy": _safe(
                len(correct), len(answered)
            ),
            "coverage": _safe(
                len(answered), len(evaluable)
            ),
            "evidence_support_rate": _safe(
                len(evidence_supported), len(evidence_evaluable)
            ),
            "unsupported_answer_rate": _safe(
                len(evidence_unsupported), len(evidence_evaluable)
            ),
            "reasonable_abstention_precision": _safe(
                len(abstain_reasonable),
                len(abstain_reasonable) + len(abstain_unnecessary),
            ),
            "reasonable_abstention_recall": _safe(
                len(abstain_reasonable), len(gold_unresolvable)
            ),
            "error_type_counts": dict(errors),
            "field_breakdown": fields,
        }

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", required=True)
    parser.add_argument("--out", default="blind_metrics.json")
    args = parser.parse_args()

    result = score(_rows(args.adjudication))
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
