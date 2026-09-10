import pytest

from modules.blind_integrity import (
    BlindIntegrityError,
    assert_safe_input_path,
    assert_safe_output_path,
    is_sensitive_path,
    validate_blind_manifest,
)


def test_normal_development_input_is_allowed():
    assert assert_safe_input_path("examples/benchmark_synthetic.jsonl")


def test_reviewer_only_input_is_rejected_outside_evaluation_mode():
    with pytest.raises(BlindIntegrityError):
        assert_safe_input_path("blind/reviewer_only/gold.jsonl")


def test_blind_gold_input_is_rejected_outside_evaluation_mode():
    with pytest.raises(BlindIntegrityError):
        assert_safe_input_path("benchmarks/blind_gold_v1.jsonl")


def test_sensitive_input_requires_explicit_evaluation_mode():
    path = assert_safe_input_path(
        "benchmarks/blind_gold_v1.jsonl", evaluation_mode=True
    )
    assert str(path).endswith("blind_gold_v1.jsonl")


def test_sensitive_path_detection_is_specific():
    assert is_sensitive_path("reviewer-only/adjudicated.csv")
    assert not is_sensitive_path("papers/gold-catalyst-review.txt")


def test_model_output_cannot_target_reviewer_path():
    with pytest.raises(BlindIntegrityError):
        assert_safe_output_path("outputs/reviewer_only/predictions.jsonl", purpose="model")


def test_adjudication_output_requires_separate_sensitive_path():
    with pytest.raises(BlindIntegrityError):
        assert_safe_output_path("outputs/results.csv", purpose="adjudication")
    assert assert_safe_output_path(
        "reviewer_only/final_ADJUDICATED.csv", purpose="adjudication"
    )


def test_manifest_accepts_identifiers_and_hashes_only():
    manifest = {
        "schema_version": "1.0",
        "split": "blind",
        "items": [
            {
                "item_id": "case-001",
                "doi": "10.0000/example",
                "source_sha256": "a" * 64,
            }
        ],
    }
    validated = validate_blind_manifest(manifest)
    assert validated["items"][0]["item_id"] == "case-001"


@pytest.mark.parametrize("leaking_key", ["gold", "expected", "label", "answer", "adjudication"])
def test_manifest_rejects_gold_or_answer_fields(leaking_key):
    manifest = {
        "schema_version": "1.0",
        "split": "blind",
        "items": [{"item_id": "case-001", leaking_key: "secret"}],
    }
    with pytest.raises(BlindIntegrityError):
        validate_blind_manifest(manifest)


def test_manifest_rejects_free_form_top_level_notes():
    with pytest.raises(BlindIntegrityError):
        validate_blind_manifest(
            {
                "schema_version": "1.0",
                "split": "blind",
                "items": [{"item_id": "case-001"}],
                "notes": "possible answer leakage",
            }
        )


def test_manifest_rejects_invalid_hash():
    with pytest.raises(BlindIntegrityError):
        validate_blind_manifest(
            {
                "schema_version": "1.0",
                "split": "blind",
                "items": [{"item_id": "case-001", "source_sha256": "not-a-hash"}],
            }
        )
