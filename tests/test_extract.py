"""Tests for entity extraction from task questions."""

from sql_nav_bench.models import Category, Difficulty, Gold, ScoringConfig, ScoringMethod, Task
from sql_nav_bench.runners.extract import extract_entities


def _make_task(question: str, tool_hint: str, category: str = "reference") -> Task:
    return Task(
        id="test_01",
        repo="test",
        category=Category(category),
        difficulty=Difficulty.EASY,
        question=question,
        tool_hint=tool_hint,
        gold=Gold(required=[]),
        scoring=ScoringConfig(method=ScoringMethod.SET_MATCH),
    )


class TestExtractEntities:
    def test_simple_model_reference(self):
        task = _make_task("Where is stg_orders used?", "find_references")
        result = extract_entities(task)
        assert result["model"] == "stg_orders"

    def test_column_and_model(self):
        task = _make_task(
            "If I remove the column customer_id from stg_orders, what breaks?",
            "trace_column_lineage",
            "impact",
        )
        result = extract_entities(task)
        assert result["model"] == "stg_orders"
        assert result["column"] == "customer_id"

    def test_backtick_extraction(self):
        task = _make_task(
            "What upstream sources feed the `orders` model?",
            "trace_dependencies",
            "lineage",
        )
        result = extract_entities(task)
        assert result["model"] == "orders"

    def test_project_extraction(self):
        task = _make_task(
            "What downstream projects consume models from the platform project?",
            "find_references",
            "mesh",
        )
        result = extract_entities(task)
        assert result["model"] == "platform"
