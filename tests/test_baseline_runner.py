"""Tests for baseline runner."""

from pathlib import Path

from sql_nav_bench.models import Category, Difficulty, Gold, ScoringConfig, ScoringMethod, Task
from sql_nav_bench.runners.baseline import BaselineRunner


def _make_task(tool_hint: str, question: str, category: str = "reference") -> Task:
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


def _create_dbt_repo(tmp_path: Path) -> Path:
    """Create a minimal dbt-like repo for testing."""
    models = tmp_path / "models"
    models.mkdir()

    (models / "stg_orders.sql").write_text(
        "SELECT order_id, customer_id, ordered_at FROM raw.orders"
    )
    (models / "stg_customers.sql").write_text(
        "SELECT customer_id, name FROM raw.customers"
    )
    (models / "orders.sql").write_text(
        "SELECT * FROM {{ ref('stg_orders') }}"
    )
    (models / "customers.sql").write_text(
        "SELECT c.customer_id, c.name, o.order_id "
        "FROM {{ ref('stg_customers') }} c "
        "JOIN {{ ref('orders') }} o ON c.customer_id = o.customer_id"
    )
    return tmp_path


class TestBaselineRunner:
    def test_name(self):
        runner = BaselineRunner()
        assert runner.name == "baseline"

    def test_find_references(self, tmp_path: Path):
        repo = _create_dbt_repo(tmp_path)
        runner = BaselineRunner()
        task = _make_task("find_references", "Where is `stg_orders` used?")
        entities, breakdown = runner.run_task(task, repo)
        assert "orders" in entities
        assert "stg_orders" not in entities

    def test_trace_upstream(self, tmp_path: Path):
        repo = _create_dbt_repo(tmp_path)
        runner = BaselineRunner()
        task = _make_task(
            "trace_dependencies",
            "What upstream sources feed the `customers` model?",
            "lineage",
        )
        entities, breakdown = runner.run_task(task, repo)
        assert "stg_customers" in entities

    def test_breakdown_counts(self, tmp_path: Path):
        repo = _create_dbt_repo(tmp_path)
        runner = BaselineRunner()
        task = _make_task("find_references", "Where is `stg_orders` used?")
        _, breakdown = runner.run_task(task, repo)
        assert "grep" in breakdown
        assert breakdown["grep"] >= 1
