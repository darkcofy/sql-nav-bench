"""Tests for pydantic data models."""

import pytest
from pydantic import ValidationError

from sql_nav_bench.models import (
    Category,
    Difficulty,
    Gold,
    Metrics,
    Result,
    ScoringConfig,
    ScoringMethod,
    Task,
)


class TestTaskModel:
    def test_valid_task(self):
        task = Task(
            id="jaffle-mesh_B1_01",
            repo="jaffle-mesh",
            category=Category.IMPACT,
            difficulty=Difficulty.MEDIUM,
            question="If I remove customer_id from stg_orders, what breaks?",
            tool_hint="column_impact",
            gold=Gold(
                required=["int_orders", "fct_orders"],
                optional=["mart_customer_orders"],
                forbidden=["stg_customers"],
            ),
            scoring=ScoringConfig(method=ScoringMethod.SET_MATCH, partial_credit=True),
        )
        assert task.id == "jaffle-mesh_B1_01"
        assert task.category == Category.IMPACT
        assert len(task.gold.required) == 2

    def test_task_missing_required_fields(self):
        with pytest.raises(ValidationError):
            Task(id="bad", repo="x")

    def test_task_invalid_category(self):
        with pytest.raises(ValidationError):
            Task(
                id="t1",
                repo="r",
                category="invalid",
                difficulty=Difficulty.EASY,
                question="q",
                tool_hint="h",
                gold=Gold(required=["a"]),
                scoring=ScoringConfig(method=ScoringMethod.SET_MATCH),
            )


class TestGoldModel:
    def test_gold_defaults(self):
        gold = Gold(required=["model_a"])
        assert gold.optional == []
        assert gold.forbidden == []

    def test_gold_empty_required_allowed(self):
        gold = Gold(required=[])
        assert gold.required == []


class TestMetricsModel:
    def test_valid_metrics(self):
        m = Metrics(
            tool_calls=3,
            search_calls=0,
            files_opened=1,
            tokens_input=2140,
            tokens_output=700,
            tokens_total=2840,
            wall_time_seconds=4.2,
            tool_breakdown={"check_impact": 1, "trace_column_lineage": 1},
        )
        assert m.tokens_total == 2840

    def test_metrics_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(
                tool_calls=-1,
                search_calls=0,
                files_opened=0,
                tokens_input=0,
                tokens_output=0,
                tokens_total=0,
                wall_time_seconds=0,
                tool_breakdown={},
            )


class TestResultModel:
    def test_valid_result(self):
        result = Result(
            task_id="jaffle-mesh_B1_01",
            agent="claude-sonnet-4-6",
            tools="sqlprism",
            timestamp="2026-04-03T14:30:00Z",
            answer={"entities": ["int_orders"], "explanation": "direct ref", "confidence": "high"},
            metrics=Metrics(
                tool_calls=3,
                search_calls=0,
                files_opened=1,
                tokens_input=2140,
                tokens_output=700,
                tokens_total=2840,
                wall_time_seconds=4.2,
                tool_breakdown={"check_impact": 1},
            ),
        )
        assert result.task_id == "jaffle-mesh_B1_01"
