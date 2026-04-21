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

    def test_add_column_to_model(self):
        task = _make_task(
            "After adding a new column 'discount_amount' to stg_orders in the platform project, what should a reindex detect as changed?",
            "reindex",
        )
        result = extract_entities(task)
        assert result["column"] == "discount_amount"
        assert result["model"] == "stg_orders"

    def test_column_from_dotted_schema(self):
        task = _make_task(
            "If I remove the 'price' column from sushi.items, which downstream models break?",
            "trace_column_lineage",
            "impact",
        )
        result = extract_entities(task)
        assert result["column"] == "price"
        assert result["model"] == "items"

    def test_dotted_name_with_trailing_period(self):
        """Sentence-ending period must not leak into the captured model name."""
        task = _make_task(
            "Trace the lineage of the 'revenue' column in sushi.customer_revenue_by_day.",
            "trace_column_lineage",
            "lineage",
        )
        result = extract_entities(task)
        assert result["column"] == "revenue"
        assert result["model"] == "customer_revenue_by_day"

    def test_dotted_name_beats_snake_fallback(self):
        """bronze.a should win over the repo_1 snake_case fallback."""
        task = _make_task(
            "In the multi/ sub-project, if bronze.a in repo_1 is changed, "
            "what models across both repos are affected?",
            "check_impact",
            "mesh",
        )
        result = extract_entities(task)
        assert result["model"] == "a"
