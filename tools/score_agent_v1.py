"""Score Raw, verifier-checked subset, unchecked accounting and final stream.

Contracts: `benchmark/SCORING_CONTRACT_V1.md` and
`benchmark/VERIFIER_COVERAGE_V1.json`.

Inputs are joined on `candidate_id`, never on list position:

- frozen raw predictions (read through `modules.artifact_chain`, fail closed)
- verified predictions from `tools/run_chain.py`
- a gold file: one JSON object per line with `candidate_id` and `fields`

Gold field values may be a plain value, or an object carrying a state:
`{"value": null, "state": "not_reported"}` with state in
`answered | not_reported | not_applicable`.

The report deliberately contains no single "verified accuracy": raw extractor
performance, the verifier-checked subset and the final stream a consumer
receives are three different denominators and are reported separately.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.artifact_chain import FrozenArtifactError, load_frozen_raw  # noqa: E402
from modules.field_verifiers import (  # noqa: E402
    COVERAGE_CONTRACT,
    NOT_CHECKED,
    NOT_VERIFIABLE,
)
from modules.raw_llm_extractor_v2 import FIELD_NAMES  # noqa: E402

SCORER_VERSION = "agent-v1-scorer-v2"
CONTRACT = "scoring-contract-v1"
ABSTENTION_STATES = {"not_reported", "unresolved", "ambiguous", "not_applicable"}
NUMERIC_TOLERANCE = 1e-4


def _read_jsonl(path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _gold_entry(raw) -> tuple[object, str]:
    if isinstance(raw, dict) and "state" in raw:
        return raw.get("value"), raw["state"]
    return raw, "answered" if raw is not None else "not_reported"


def _equal(prediction, gold) -> bool:
    if isinstance(prediction, dict) and isinstance(gold, dict):
        return prediction.get("kind") == gold.get("kind") and _equal(
            prediction.get("value"), gold.get("value")
        )
    if isinstance(prediction, (int, float)) and isinstance(gold, (int, float)):
        return math.isclose(float(prediction), float(gold), rel_tol=0.0, abs_tol=NUMERIC_TOLERANCE)
    if isinstance(prediction, str) and isinstance(gold, str):
        return prediction.strip().lower() == gold.strip().lower()
    return prediction == gold


def _safe(a, b):
    return a / b if b else None


def _outcome(prediction, abstention_reason, gold_value, gold_state):
    """Classify one chunk x field pair per the scoring contract."""
    if gold_state == "not_applicable":
        return "not_applicable"
    if prediction is not None:
        if gold_state == "answered":
            return "correct" if _equal(prediction, gold_value) else "incorrect"
        return "hallucinated"
    if abstention_reason in {"unresolved", "ambiguous"}:
        return abstention_reason
    if abstention_reason in ABSTENTION_STATES:
        return "abstain_unnecessary" if gold_state == "answered" else "abstain_reasonable"
    return "miss" if gold_state == "answered" else "abstain_reasonable"


def _gold_present(counts: Counter) -> int:
    return counts["correct"] + counts["incorrect"] + counts["miss"] + counts["abstain_unnecessary"]


def _metrics(counts: Counter) -> dict:
    correct = counts["correct"]
    incorrect = counts["incorrect"]
    hallucinated = counts["hallucinated"]
    answered = correct + incorrect + hallucinated
    gold_present = _gold_present(counts)
    gold_absent = hallucinated + counts["abstain_reasonable"]
    evaluable = gold_present + gold_absent
    return {
        "n_pairs": evaluable,
        "n_gold_present": gold_present,
        "n_gold_absent": gold_absent,
        "correct": correct,
        "incorrect": incorrect,
        "hallucinated": hallucinated,
        "miss": counts["miss"],
        "unresolved": counts["unresolved"],
        "ambiguous": counts["ambiguous"],
        "abstain_reasonable": counts["abstain_reasonable"],
        "abstain_unnecessary": counts["abstain_unnecessary"],
        "not_applicable_excluded": counts["not_applicable"],
        "coverage": _safe(answered, evaluable),
        "selective_accuracy": _safe(correct, correct + incorrect),
        "end_to_end_accuracy": _safe(correct, gold_present),
        "hallucination_rate_on_absent_fields": _safe(hallucinated, gold_absent),
        "miss_rate": _safe(counts["miss"], gold_present),
        "unresolved_rate": _safe(counts["unresolved"] + counts["ambiguous"], evaluable),
        "abstention_quality": _safe(
            counts["abstain_reasonable"],
            counts["abstain_reasonable"] + counts["abstain_unnecessary"],
        ),
    }


def score(raw_records, verified_rows, gold_rows) -> dict:
    """Four separate accounts, never mixed.

    A. raw extractor metrics over all 12 fields
    B. verifier-checked subset
    C. unchecked and unverifiable accounting
    D. final stream, i.e. what a consumer actually receives
    """
    gold_by_id = {row["candidate_id"]: row["fields"] for row in gold_rows}
    verified_by_id = {row["candidate_id"]: row for row in verified_rows}

    raw_counts, checked_counts, final_counts = Counter(), Counter(), Counter()
    raw_by_field = defaultdict(Counter)
    final_by_field = defaultdict(Counter)
    coverage = Counter()
    unchecked = Counter()
    unverifiable = Counter()
    supported = unsupported = checked_units = 0
    withheld_wrong = withheld_right = raw_wrong = raw_right = 0
    unverified_pass_through = 0
    scored_ids, missing_gold = [], []

    for record in raw_records:
        cid = record["candidate_id"]
        if cid not in gold_by_id:
            missing_gold.append(cid)
            continue
        scored_ids.append(cid)
        gold_fields = gold_by_id[cid]
        verification = verified_by_id.get(cid) or {}
        rows = {row["field"]: row for row in verification.get("fields", [])}

        for name in FIELD_NAMES:
            if name not in gold_fields:
                continue
            gold_value, gold_state = _gold_entry(gold_fields[name])
            raw_value = record["values"].get(name)
            reason = record.get("abstention_reasons", {}).get(name)
            row = rows.get(name, {})
            status = row.get("verification_status") or row.get("status")
            action = row.get("final_action", "retain")
            checked = bool(row.get("checked_by_verifier"))

            raw_outcome = _outcome(raw_value, reason, gold_value, gold_state)
            raw_counts[raw_outcome] += 1
            raw_by_field[name][raw_outcome] += 1

            if gold_state != "not_applicable":
                coverage["evaluable_units"] += 1
                if checked:
                    coverage["checked_units"] += 1

            if checked:
                checked_units += 1
                if status == "supported":
                    supported += 1
                elif status == "unsupported":
                    unsupported += 1
                checked_counts[raw_outcome] += 1
                if raw_value is not None and gold_state == "answered":
                    blocked = action == "suppress"
                    if raw_outcome == "correct":
                        raw_right += 1
                        withheld_right += 1 if blocked else 0
                    elif raw_outcome == "incorrect":
                        raw_wrong += 1
                        withheld_wrong += 1 if blocked else 0

            if status == NOT_CHECKED:
                unchecked[name] += 1
            elif status == NOT_VERIFIABLE and raw_value is not None:
                unverifiable[name] += 1

            if action == "suppress":
                final_value = None
                final_reason = status if status in ABSTENTION_STATES else "unresolved"
            else:
                final_value, final_reason = raw_value, reason
                if raw_value is not None and (
                    not checked or status in {NOT_CHECKED, NOT_VERIFIABLE}
                ):
                    unverified_pass_through += 1
            final_outcome = _outcome(final_value, final_reason, gold_value, gold_state)
            final_counts[final_outcome] += 1
            final_by_field[name][final_outcome] += 1

    evaluable = coverage["evaluable_units"]
    checked_total = coverage["checked_units"]
    final_answered = (
        final_counts["correct"] + final_counts["incorrect"] + final_counts["hallucinated"]
    )

    return {
        "scorer_version": SCORER_VERSION,
        "scoring_contract": CONTRACT,
        "verifier_coverage_contract": COVERAGE_CONTRACT["contract_version"],
        "verifier_version": COVERAGE_CONTRACT["verifier_version"],
        "evaluation_unit": "reaction_candidate_chunk x field",
        "join_key": "candidate_id",
        "n_chunks_scored": len(scored_ids),
        "n_chunks_without_gold": len(missing_gold),
        "chunks_without_gold": sorted(missing_gold),
        "a_raw_extractor": {
            "scope": "all 12 fields of FIELD_SCHEMA_V1; this is extractor performance",
            "raw_end_to_end_accuracy": _safe(raw_counts["correct"], _gold_present(raw_counts)),
            **_metrics(raw_counts),
        },
        "b_verifier_checked_subset": {
            "scope": "only candidate x field units with checked_by_verifier = true",
            "verifier_eligible_units": evaluable,
            "verifier_checked_units": checked_total,
            "verifier_coverage_rate": _safe(checked_total, evaluable),
            "evidence_support_rate": _safe(supported, checked_units),
            "unsupported_answer_rate": _safe(unsupported, checked_units),
            "wrong_value_block_rate": _safe(withheld_wrong, raw_wrong),
            "correct_value_retention": _safe(raw_right - withheld_right, raw_right),
            "n_raw_incorrect_in_subset": raw_wrong,
            "n_raw_correct_in_subset": raw_right,
            "verifier_checked_subset_selective_accuracy": _safe(
                checked_counts["correct"],
                checked_counts["correct"] + checked_counts["incorrect"],
            ),
        },
        "c_unchecked_and_unverifiable": {
            "scope": "units the verifier did not or could not adjudicate; excluded from every verifier denominator",
            "not_checked_v1_count": sum(unchecked.values()),
            "not_verifiable_v1_count": sum(unverifiable.values()),
            "not_checked_v1_by_field": dict(unchecked),
            "not_verifiable_v1_by_field": dict(unverifiable),
            "rule": "not checked is not unsupported; not verifiable is not incorrect",
        },
        "d_final_stream": {
            "scope": "what a consumer receives after verifier actions, including unverified pass-through",
            "final_coverage": _safe(final_answered, evaluable),
            "final_correct": final_counts["correct"],
            "final_incorrect": final_counts["incorrect"],
            "final_selective_accuracy": _safe(
                final_counts["correct"], final_counts["correct"] + final_counts["incorrect"]
            ),
            "final_stream_end_to_end_accuracy": _safe(
                final_counts["correct"], _gold_present(final_counts)
            ),
            "unverified_pass_through_units": unverified_pass_through,
            "unverified_pass_through_label": "UNVERIFIED_PASS_THROUGH",
            "suppressed_units": final_counts["unresolved"] + final_counts["ambiguous"],
            **_metrics(final_counts),
        },
        "field_breakdown": {
            name: {
                "raw": _metrics(raw_by_field[name]),
                "final_stream": _metrics(final_by_field[name]),
            }
            for name in FIELD_NAMES
            if raw_by_field[name]
        },
        "interpretation_rules": [
            "Verifier benefit is the pair (wrong_value_block_rate, correct_value_retention); a higher selective accuracy obtained by answering less is not an improvement.",
            "d_final_stream includes values the verifier never checked; they are counted as UNVERIFIED_PASS_THROUGH and must not be described as verified.",
            "This report contains no single 'verified accuracy' on purpose: A, B and D have different denominators.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--verified", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--out", default="score_report.json")
    args = parser.parse_args()

    try:
        raw_records, _ = load_frozen_raw(Path(args.raw), Path(args.freeze))
    except FrozenArtifactError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, indent=2))
        return 2

    report = score(raw_records, _read_jsonl(args.verified), _read_jsonl(args.gold))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
