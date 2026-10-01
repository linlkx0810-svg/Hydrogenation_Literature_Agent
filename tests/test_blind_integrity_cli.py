import argparse

import pytest

from agent import command_extract_text
from modules.blind_integrity import BlindIntegrityError
from tools.run_benchmark import load_jsonl


def test_benchmark_loader_refuses_blind_gold_without_evaluation_mode(tmp_path):
    blind_dir = tmp_path / "blind_gold"
    blind_dir.mkdir()
    dataset = blind_dir / "benchmark.jsonl"
    dataset.write_text('{"text":"example","expected":[]}\n', encoding="utf-8")

    with pytest.raises(BlindIntegrityError):
        load_jsonl(dataset)


def test_benchmark_loader_allows_blind_gold_in_explicit_evaluation_mode(tmp_path):
    blind_dir = tmp_path / "blind_gold"
    blind_dir.mkdir()
    dataset = blind_dir / "benchmark.jsonl"
    dataset.write_text('{"text":"example","expected":[]}\n', encoding="utf-8")

    rows = load_jsonl(dataset, evaluation_mode=True)
    assert rows == [{"text": "example", "expected": []}]


def test_normal_extract_command_refuses_reviewer_only_input(tmp_path):
    reviewer_dir = tmp_path / "reviewer_only"
    reviewer_dir.mkdir()
    source = reviewer_dir / "case.txt"
    source.write_text("97% ee", encoding="utf-8")
    args = argparse.Namespace(input=str(source), output=None, context=0)

    with pytest.raises(BlindIntegrityError):
        command_extract_text(args)


def test_normal_extract_command_refuses_sensitive_output(tmp_path):
    source = tmp_path / "case.txt"
    source.write_text("97% ee", encoding="utf-8")
    output = tmp_path / "reviewer_only" / "predictions.json"
    output.parent.mkdir()
    args = argparse.Namespace(input=str(source), output=str(output), context=0)

    with pytest.raises(BlindIntegrityError):
        command_extract_text(args)
