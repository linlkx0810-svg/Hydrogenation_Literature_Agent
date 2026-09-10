"""Development-only benchmark for extraction and evidence verification.

This benchmark is intentionally separate from frozen blind evaluation. It can
compare the deterministic rule baseline, replayed LLM extraction, and the subset
retained after verifier-v1 using one common eight-field schema.

The bundled fixture is synthetic and exists only to validate the evaluation
contract. Its scores are engineering diagnostics, not scientific performance
claims.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from modules.blind_integrity import assert_safe_input_path
from modules.llm_extractor import FIELD_NAMES, ReplayJSONProvider, extract_reaction_chunk
from modules.reaction_candidate_extraction import extract_reaction_candidates
from modules.verifier import ReplayVerifierProvider, verify_candidate

BENCHMARK_VERSION = "development-benchmark-v1"
BENCHMARK_KIND = "synthetic-contract-development"


def _normalise(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, float):
        return round(value, 4)
    return value


def _empty_prediction() -> dict[str, Any]:
    return {field: None for field in FIELD_NAMES}


def _scientific_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    return {field: record.get(field) for field in FIELD_NAMES}


def validate_development_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one development benchmark row.

    Every row represents one already-selected local evidence chunk with one
    target record. The fixture may contain replayed model/verifier responses but
    must be explicitly marked as development data.
    """

    required = {
        "case_id",
        "scenario",
        "split",
        "text",
        "gold",
        "llm_response",
        "verifier_responses",
    }
    missing = required - set(row)
    if missing:
        raise ValueError(
            "Development benchmark row missing keys: " + ", ".join(sorted(missing))
        )
    if row["split"] != "development":
        raise ValueError("Development benchmark rows must use split='development'")
    if not isinstance(row["text"], str) or not row["text"].strip():
        raise ValueError("Development benchmark text must be non-empty")
    if not isinstance(row["gold"], Mapping):
        raise ValueError("gold must be an object")
    if not isinstance(row["llm_response"], Mapping):
        raise ValueError("llm_response must be an object")
    if not isinstance(row["verifier_responses"], Mapping):
        raise ValueError("verifier_responses must be an object")

    for name in ("gold", "llm_response"):
        keys = set(row[name])
        expected = set(FIELD_NAMES)
        if keys != expected:
            raise ValueError(
                f"{name} must contain exactly the eight scientific fields; "
                f"missing={sorted(expected - keys)}, extra={sorted(keys - expected)}"
            )
    if set(row["verifier_responses"]) != set(FIELD_NAMES):
        raise ValueError("verifier_responses must contain exactly the eight fields")

    return dict(row)


def load_development_rows(path: str | Path) -> list[dict[str, Any]]:
    safe = assert_safe_input_path(Path(path), evaluation_mode=False)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(safe.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed development JSONL at line {line_number}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Development row {line_number} must be an object")
        rows.append(validate_development_row(parsed))
    return rows


def score_predictions(
    gold_records: Iterable[Mapping[str, Any]],
    predictions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Score non-null scientific predictions without rewarding null inflation.

    A null prediction against an absent/null gold field earns no correctness
    credit. Headline precision and recall therefore describe recovered scientific
    values rather than agreement on missingness.
    """

    gold_list = list(gold_records)
    pred_list = list(predictions)
    if len(gold_list) != len(pred_list):
        raise ValueError("gold_records and predictions must have the same length")

    total_fields = len(gold_list) * len(FIELD_NAMES)
    gold_present = 0
    predicted_non_null = 0
    attempted_gold = 0
    correct_non_null = 0
    incorrect_non_null = 0
    hallucinations_on_absent = 0
    abstentions_on_present = 0

    field_counts: dict[str, dict[str, int]] = {
        field: {
            "gold_present": 0,
            "predicted_non_null": 0,
            "correct_non_null": 0,
            "incorrect_non_null": 0,
            "hallucinations_on_absent": 0,
            "abstentions_on_present": 0,
        }
        for field in FIELD_NAMES
    }

    for gold, pred in zip(gold_list, pred_list):
        for field in FIELD_NAMES:
            g = gold.get(field)
            p = pred.get(field)
            g_present = g is not None
            p_present = p is not None
            fc = field_counts[field]

            if g_present:
                gold_present += 1
                fc["gold_present"] += 1
            if p_present:
                predicted_non_null += 1
                fc["predicted_non_null"] += 1

            if g_present and p_present:
                attempted_gold += 1
                if _normalise(g) == _normalise(p):
                    correct_non_null += 1
                    fc["correct_non_null"] += 1
                else:
                    incorrect_non_null += 1
                    fc["incorrect_non_null"] += 1
            elif g_present and not p_present:
                abstentions_on_present += 1
                fc["abstentions_on_present"] += 1
            elif not g_present and p_present:
                incorrect_non_null += 1
                hallucinations_on_absent += 1
                fc["incorrect_non_null"] += 1
                fc["hallucinations_on_absent"] += 1

    precision = correct_non_null / predicted_non_null if predicted_non_null else 0.0
    recall = correct_non_null / gold_present if gold_present else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    per_field: dict[str, Any] = {}
    for field, counts in field_counts.items():
        fpred = counts["predicted_non_null"]
        fgold = counts["gold_present"]
        fcorrect = counts["correct_non_null"]
        fprecision = fcorrect / fpred if fpred else 0.0
        frecall = fcorrect / fgold if fgold else 0.0
        ff1 = (
            2 * fprecision * frecall / (fprecision + frecall)
            if (fprecision + frecall)
            else 0.0
        )
        per_field[field] = {
            **counts,
            "precision": fprecision,
            "recall": frecall,
            "f1": ff1,
        }

    return {
        "records": len(gold_list),
        "total_scored_fields": total_fields,
        "gold_present": gold_present,
        "predicted_non_null": predicted_non_null,
        "correct_non_null": correct_non_null,
        "incorrect_non_null": incorrect_non_null,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "answer_rate": predicted_non_null / total_fields if total_fields else 0.0,
        "attempted_gold_coverage": attempted_gold / gold_present if gold_present else 0.0,
        "hallucinations_on_absent": hallucinations_on_absent,
        "abstentions_on_present": abstentions_on_present,
        "per_field": per_field,
    }


def _rule_prediction(row: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    candidates = extract_reaction_candidates(
        row["text"], int(row.get("context_sentences", 0))
    )
    if not candidates:
        return _empty_prediction(), 0
    return _scientific_fields(candidates[0].to_dict()), len(candidates)


def _llm_replay_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    provider = ReplayJSONProvider(
        response=row["llm_response"],
        model_name="development-replay-extractor",
    )
    result = extract_reaction_chunk(
        evidence_text=row["text"],
        provider=provider,
        candidate_id=str(row["case_id"]),
    )
    return _scientific_fields(result.to_dict())


def _verified_prediction(
    row: Mapping[str, Any],
    llm_prediction: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = {
        "candidate_id": row["case_id"],
        "evidence_text": row["text"],
        **_scientific_fields(llm_prediction),
    }
    provider = ReplayVerifierProvider(
        responses=row["verifier_responses"],
        model_name="development-replay-verifier",
    )
    result = verify_candidate(candidate, provider=provider)
    result_dict = result.to_dict()
    kept = _empty_prediction()
    for field in FIELD_NAMES:
        judgement = result_dict["fields"][field]
        if judgement["status"] == "accepted" and llm_prediction.get(field) is not None:
            kept[field] = llm_prediction.get(field)
    return kept, result_dict


def _verifier_effect(
    rows: list[Mapping[str, Any]],
    llm_predictions: list[Mapping[str, Any]],
    verification_results: list[Mapping[str, Any]],
    pre_score: Mapping[str, Any],
    post_score: Mapping[str, Any],
) -> dict[str, Any]:
    wrong_non_null = 0
    wrong_blocked = 0
    correct_non_null = 0
    correct_retained = 0
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for row, pred, verification in zip(rows, llm_predictions, verification_results):
        gold = row["gold"]
        fields = verification["fields"]
        for field in FIELD_NAMES:
            p = pred.get(field)
            g = gold.get(field)
            judgement = fields[field]
            status_counts[judgement["status"]] += 1
            reason_counts[judgement["reason_code"]] += 1
            if p is None:
                continue
            correct = g is not None and _normalise(p) == _normalise(g)
            if correct:
                correct_non_null += 1
                if judgement["status"] == "accepted":
                    correct_retained += 1
            else:
                wrong_non_null += 1
                if judgement["status"] != "accepted":
                    wrong_blocked += 1

    return {
        "precision_before": pre_score["precision"],
        "precision_after": post_score["precision"],
        "precision_delta": post_score["precision"] - pre_score["precision"],
        "recall_before": pre_score["recall"],
        "recall_after": post_score["recall"],
        "recall_delta": post_score["recall"] - pre_score["recall"],
        "wrong_non_null_predictions": wrong_non_null,
        "wrong_value_block_rate": wrong_blocked / wrong_non_null if wrong_non_null else 0.0,
        "correct_non_null_predictions": correct_non_null,
        "correct_value_retention": (
            correct_retained / correct_non_null if correct_non_null else 0.0
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
    }


def evaluate_development(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    validated = [validate_development_row(row) for row in rows]
    gold = [row["gold"] for row in validated]

    rule_predictions: list[dict[str, Any]] = []
    rule_candidate_counts: list[int] = []
    llm_predictions: list[dict[str, Any]] = []
    verified_predictions: list[dict[str, Any]] = []
    verification_results: list[dict[str, Any]] = []

    for row in validated:
        rule_pred, candidate_count = _rule_prediction(row)
        rule_predictions.append(rule_pred)
        rule_candidate_counts.append(candidate_count)

        llm_pred = _llm_replay_prediction(row)
        llm_predictions.append(llm_pred)

        verified_pred, verification = _verified_prediction(row, llm_pred)
        verified_predictions.append(verified_pred)
        verification_results.append(verification)

    rule_score = score_predictions(gold, rule_predictions)
    llm_score = score_predictions(gold, llm_predictions)
    verified_score = score_predictions(gold, verified_predictions)

    scenarios: dict[str, Any] = {}
    for scenario in sorted({str(row["scenario"]) for row in validated}):
        indices = [i for i, row in enumerate(validated) if row["scenario"] == scenario]
        sgold = [gold[i] for i in indices]
        scenarios[scenario] = {
            "cases": len(indices),
            "rule-baseline-v1": score_predictions(sgold, [rule_predictions[i] for i in indices]),
            "llm-extractor-v1-replay": score_predictions(sgold, [llm_predictions[i] for i in indices]),
            "llm-plus-verifier-v1-replay": score_predictions(
                sgold, [verified_predictions[i] for i in indices]
            ),
        }

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "benchmark_kind": BENCHMARK_KIND,
        "scientific_performance_claim": False,
        "examples": len(validated),
        "fields": list(FIELD_NAMES),
        "systems": {
            "rule-baseline-v1": {
                **rule_score,
                "candidate_count_distribution": dict(sorted(Counter(rule_candidate_counts).items())),
            },
            "llm-extractor-v1-replay": llm_score,
            "llm-plus-verifier-v1-replay": verified_score,
        },
        "verifier_effect": _verifier_effect(
            validated,
            llm_predictions,
            verification_results,
            llm_score,
            verified_score,
        ),
        "scenario_results": scenarios,
        "warning": (
            "Synthetic/replayed development benchmark only. Do not report these "
            "scores as real literature or real LLM performance."
        ),
    }
