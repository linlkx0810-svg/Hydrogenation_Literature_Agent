"""Score Raw and Verified predictions under `benchmark/SCORING_CONTRACT_V1.md`.

Inputs are joined on `candidate_id`, never on list position:

- frozen raw predictions (read through `modules.artifact_chain`, fail closed)
- verified predictions from `tools/run_chain.py`
- a gold file: one JSON object per line with `candidate_id` and `fields`

Gold field values may be a plain value, or an object carrying a state:
`{"value": null, "state": "not_reported"}` with state in
`answered | not_reported | not_applicable`.

The scorer writes `score_report.json`. It never writes to the raw artifact.
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
from modules.raw_llm_extractor_v2 import FIELD_NAMES  # noqa: E402

SCORER_VERSION = "agent-v1-scorer-v1"
CONTRACT = "scoring-contract-v1"
ABSTENTION_STATES = {"not_reported", "unresolved", "ambiguous", "not_applicable"}
WITHHELD_STATUSES = {"unsupported", "unresolved", "ambiguous"}
NUMERIC_TOLERANCE = 1e-4


def _read_jsonl(path: Path) -> list[dict]:
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
        return (
            prediction.get("kind") == gold.get("kind")
            and _equal(prediction.get("value"), gold.get("value"))
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


def _metrics(counts: Counter) -> dict:
    correct = counts["correct"]
    incorrect = counts["incorrect"]
    hallucinated = counts["hallucinated"]
    answered = correct + incorrect + hallucinated
    gold_present = correct + incorrect + counts["miss"] + counts["abstain_unnecessary"]
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
    gold_by_id = {row["candidate_id"]: row["fields"] for row in gold_rows}
    verified_by_id = {row["candidate_id"]: row for row in verified_rows}

    raw_counts, ver_counts = Counter(), Counter()
    raw_by_field = defaultdict(Counter)
    ver_by_field = defaultdict(Counter)
    withheld_wrong = withheld_right = raw_wrong = raw_right = 0
    supported = verified_fields = unsupported = 0
    scored_ids, missing_gold = [], []

    for record in raw_records:
        cid = record["candidate_id"]
        if cid not in gold_by_id:
            missing_gold.append(cid)
            continue
        scored_ids.append(cid)
        gold_fields = gold_by_id[cid]
        verification = verified_by_id.get(cid)
        statuses = {}
        if verification:
            for field in verification["fields"]:
                statuses[field["field"]] = field["status"]
                if not field.get("checked_by_verifier", True):
                    continue
                verified_fields += 1
                if field["status"] == "supported":
                    supported += 1
                elif field["status"] == "unsupported":
                    unsupported += 1

        for name in FIELD_NAMES:
            if name not in gold_fields:
                continue
            gold_value, gold_state = _gold_entry(gold_fields[name])
            raw_value = record["values"].get(name)
            reason = record.get("abstention_reasons", {}).get(name)

            raw_outcome = _outcome(raw_value, reason, gold_value, gold_state)
            raw_counts[raw_outcome] += 1
            raw_by_field[name][raw_outcome] += 1

            status = statuses.get(name)
            withheld = status in WITHHELD_STATUSES
            if raw_value is not None and gold_state == "answered":
                if raw_outcome == "correct":
                    raw_right += 1
                    withheld_right += 1 if withheld else 0
                elif raw_outcome == "incorrect":
                    raw_wrong += 1
                    withheld_wrong += 1 if withheld else 0

            if withheld:
                ver_value, ver_reason = None, (status if status in ABSTENTION_STATES else "unresolved")
            else:
                ver_value, ver_reason = raw_value, reason
            ver_outcome = _outcome(ver_value, ver_reason, gold_value, gold_state)
            ver_counts[ver_outcome] += 1
            ver_by_field[name][ver_outcome] += 1

    report = {
        "scorer_version": SCORER_VERSION,
        "scoring_contract": CONTRACT,
        "evaluation_unit": "reaction_candidate_chunk x field",
        "join_key": "candidate_id",
        "n_chunks_scored": len(scored_ids),
        "n_chunks_without_gold": len(missing_gold),
        "chunks_without_gold": sorted(missing_gold),
        "raw": _metrics(raw_counts),
        "verified": _metrics(ver_counts),
        "verifier": {
            "n_fields_checked": verified_fields,
            "fields_not_checked_by_verifier_v1": sorted(
                {
                    field["field"]
                    for row in verified_rows
                    for field in row["fields"]
                    if not field.get("checked_by_verifier", True)
                }
            ),
            "evidence_support_rate": _safe(supported, verified_fields),
            "unsupported_answer_rate": _safe(unsupported, verified_fields),
            "wrong_value_block_rate": _safe(withheld_wrong, raw_wrong),
            "correct_value_retention": _safe(raw_right - withheld_right, raw_right),
            "n_raw_incorrect": raw_wrong,
            "n_raw_correct": raw_right,
        },
        "field_breakdown": {
            name: {"raw": _metrics(raw_by_field[name]), "verified": _metrics(ver_by_field[name])}
            for name in FIELD_NAMES
            if raw_by_field[name]
        },
        "interpretation_rule": (
            "Verifier benefit is the pair (wrong_value_block_rate, correct_value_retention). "
            "A higher selective accuracy obtained by answering less is not an improvement."
        ),
    }
    return report


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
