"""Tests for scoring engine."""

import pytest

from sql_nav_bench.models import Gold, Metrics
from sql_nav_bench.scorer import score_efficiency, score_set_match


class TestSetMatchScoring:
    def test_perfect_match(self):
        gold = Gold(required=["a", "b"], optional=[], forbidden=["x"])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_partial_recall(self):
        gold = Gold(required=["a", "b", "c"], optional=[], forbidden=[])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == pytest.approx(2 / 3)

    def test_false_positive_reduces_precision(self):
        gold = Gold(required=["a"], optional=[], forbidden=["x"])
        found = ["a", "x"]
        result = score_set_match(found, gold)
        assert result.precision == 0.5
        assert result.recall == 1.0

    def test_optional_boosts_recall(self):
        gold = Gold(required=["a"], optional=["b"], forbidden=[])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_missing_optional_no_penalty(self):
        gold = Gold(required=["a"], optional=["b"], forbidden=[])
        found = ["a"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_empty_found_zero_recall(self):
        gold = Gold(required=["a", "b"], optional=[], forbidden=[])
        found: list[str] = []
        result = score_set_match(found, gold)
        assert result.recall == 0.0

    def test_empty_required_and_found(self):
        gold = Gold(required=[], optional=[], forbidden=[])
        found: list[str] = []
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_unknown_entity_not_forbidden(self):
        gold = Gold(required=["a"], optional=[], forbidden=[])
        found = ["a", "z"]
        result = score_set_match(found, gold)
        assert result.precision == 0.5
        assert result.recall == 1.0


class TestEfficiencyScoring:
    def test_single_run_scores_one(self):
        metrics = [
            Metrics(
                tool_calls=3, search_calls=0, files_opened=1,
                tokens_input=2000, tokens_output=800, tokens_total=2800,
                wall_time_seconds=4.0, tool_breakdown={},
            )
        ]
        scores = score_efficiency(metrics)
        assert len(scores) == 1
        assert scores[0] == 1.0

    def test_two_runs_best_worst(self):
        low = Metrics(
            tool_calls=3, search_calls=0, files_opened=1,
            tokens_input=2000, tokens_output=800, tokens_total=2800,
            wall_time_seconds=4.0, tool_breakdown={},
        )
        high = Metrics(
            tool_calls=22, search_calls=18, files_opened=14,
            tokens_input=40000, tokens_output=7200, tokens_total=47200,
            wall_time_seconds=45.0, tool_breakdown={},
        )
        scores = score_efficiency([low, high])
        assert scores[0] > scores[1]
        assert scores[0] == 1.0
        assert scores[1] == 0.0
