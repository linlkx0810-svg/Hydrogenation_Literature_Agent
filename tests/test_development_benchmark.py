from pathlib import Path

import pytest

from modules.blind_integrity import BlindIntegrityError
from modules.development_benchmark import (
    BENCHMARK_KIND,
    evaluate_development,
    load_development_rows,
    score_predictions,
)
from modules.llm_extractor import FIELD_NAMES


FIXTURE = Path("examples/development_benchmark_v1.jsonl")


def test_synthetic_development_fixture_loads():
    rows = load_development_rows(FIXTURE)
    assert len(rows) == 9
    assert all(row["split"] == "development" for row in rows)
    assert all(set(row["gold"]) == set(FIELD_NAMES) for row in rows)
    assert all(set(row["llm_response"]) == set(FIELD_NAMES) for row in rows)


def test_null_null_does_not_inflate_headline_accuracy():
    empty = {field: None for field in FIELD_NAMES}
    metrics = score_predictions([empty], [empty])
    assert metrics["correct_non_null"] == 0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert metrics["answer_rate"] == 0.0


def test_benchmark_compares_three_system_views():
    report = evaluate_development(load_development_rows(FIXTURE))
    assert report["benchmark_kind"] == BENCHMARK_KIND
    assert report["scientific_performance_claim"] is False
    assert set(report["systems"]) == {
        "rule-baseline-v1",
        "llm-extractor-v1-replay",
        "llm-plus-verifier-v1-replay",
    }


def test_verifier_effect_measures_precision_recall_tradeoff():
    report = evaluate_development(load_development_rows(FIXTURE))
    effect = report["verifier_effect"]
    pre = report["systems"]["llm-extractor-v1-replay"]
    post = report["systems"]["llm-plus-verifier-v1-replay"]

    assert effect["wrong_non_null_predictions"] > 0
    assert effect["wrong_value_block_rate"] > 0
    assert effect["precision_after"] >= effect["precision_before"]
    assert post["predicted_non_null"] <= pre["predicted_non_null"]
    assert 0.0 <= effect["correct_value_retention"] <= 1.0
    assert effect["precision_delta"] == pytest.approx(post["precision"] - pre["precision"])
    assert effect["recall_delta"] == pytest.approx(post["recall"] - pre["recall"])


def test_adversarial_scenarios_are_reported_separately():
    report = evaluate_development(load_development_rows(FIXTURE))
    scenarios = set(report["scenario_results"])
    assert {
        "clean_complete",
        "multi_value_ambiguity",
        "source_conflict",
        "wrong_reaction_association",
        "wrong_entity_association",
        "unsupported_plausible_value",
        "unit_format_error",
        "verifier_conservative",
    }.issubset(scenarios)


def test_development_loader_refuses_blind_named_path(tmp_path):
    blind_dir = tmp_path / "blind_gold"
    blind_dir.mkdir()
    path = blind_dir / "development_benchmark.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(BlindIntegrityError):
        load_development_rows(path)
