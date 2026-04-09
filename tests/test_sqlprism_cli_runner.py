"""Tests for SqlprismCLI runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sql_nav_bench.models import Category, Difficulty, Gold, ScoringConfig, ScoringMethod, Task
from sql_nav_bench.runners.sqlprism_cli import SqlprismCLIRunner


def _make_task(tool_hint: str, question: str, category: str = "reference") -> Task:
    return Task(
        id="test_01",
        repo="test",
        category=Category(category),
        difficulty=Difficulty.EASY,
        question=question,
        tool_hint=tool_hint,
        gold=Gold(required=["model_a"]),
        scoring=ScoringConfig(method=ScoringMethod.SET_MATCH),
    )


class TestSqlprismCLIRunner:
    def test_name(self):
        runner = SqlprismCLIRunner()
        assert runner.name == "sqlprism-cli"

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_setup_calls_reindex(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner = SqlprismCLIRunner()
        runner.setup("test-repo", Path("/tmp/repo"))
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "reindex" in cmd

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_find_references(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="model_a\nmodel_b\nmodel_c\n",
            stderr="",
        )
        runner = SqlprismCLIRunner()
        task = _make_task("find_references", "Where is `stg_orders` used?")
        entities, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "model_a" in entities
        assert len(entities) == 3

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_trace_dependencies(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="upstream_a\nupstream_b\n",
            stderr="",
        )
        runner = SqlprismCLIRunner()
        task = _make_task("trace_dependencies", "What feeds `orders`?", "lineage")
        entities, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "upstream_a" in entities

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_trace_column_lineage_with_column(self, mock_run: MagicMock):
        """trace_column_lineage tasks use query lineage and extract model names from expressions."""
        lineage_response = '{"chains": [{"output_node": "customer_revenue_by_day", "output_column": "revenue", "chain_index": 0, "hops": [{"index": 0, "column": "revenue", "table": "WITH", "expression": "SUM(\\"ot\\".total) AS \\"revenue\\""}, {"index": 1, "column": "total", "table": "ot", "expression": "SUM(\\"oi\\".quantity * \\"i\\".price) AS \\"total\\""}, {"index": 2, "column": "price", "table": "\\"i\\"", "expression": "\\"memory\\".\\"sushi\\".\\"items\\" AS \\"i\\""}], "file": "models/customer_revenue_by_day.sql", "repo": "sushi"}, {"output_node": "customer_revenue_by_day", "output_column": "revenue", "chain_index": 1, "hops": [{"index": 0, "column": "revenue", "table": "WITH", "expression": "SUM(\\"ot\\".total) AS \\"revenue\\""}, {"index": 1, "column": "total", "table": "ot", "expression": "SUM(\\"oi\\".quantity * \\"i\\".price) AS \\"total\\""}, {"index": 2, "column": "quantity", "table": "\\"oi\\"", "expression": "\\"memory\\".\\"sushi\\".\\"order_items\\" AS \\"oi\\""}], "file": "models/customer_revenue_by_day.sql", "repo": "sushi"}], "total_count": 2}'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=lineage_response,
            stderr="",
        )
        runner = SqlprismCLIRunner()
        task = _make_task(
            "trace_column_lineage",
            "Trace the lineage of the 'revenue' column in customer_revenue_by_day.",
            "lineage",
        )
        entities, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "items" in entities
        assert "order_items" in entities
        # CTE aliases should NOT appear
        assert "ot" not in entities
        assert "WITH" not in entities
        assert "query_lineage" in breakdown
        assert "query_column_usage" not in breakdown

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_trace_column_lineage_without_column(self, mock_run: MagicMock):
        """trace_column_lineage tasks without a column still use query lineage."""
        lineage_response = '{"chains": [{"output_node": "top_waiters", "output_column": "total_orders", "chain_index": 0, "hops": [{"index": 0, "column": "waiter_id", "table": "orders", "expression": ""}], "file": "models/top_waiters.sql", "repo": "sushi"}], "total_count": 1}'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=lineage_response,
            stderr="",
        )
        runner = SqlprismCLIRunner()
        task = _make_task(
            "trace_column_lineage",
            "What upstream models feed top_waiters?",
            "lineage",
        )
        entities, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "orders" in entities
        assert "query_lineage" in breakdown

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_parse_entities_chains_deduplicates(self, mock_run: MagicMock):
        """Chains with duplicate hop tables should deduplicate."""
        lineage_response = '{"chains": [{"hops": [{"table": "orders", "expression": ""}, {"table": "items", "expression": ""}]}, {"hops": [{"table": "orders", "expression": ""}, {"table": "customers", "expression": ""}]}], "total_count": 2}'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=lineage_response,
            stderr="",
        )
        runner = SqlprismCLIRunner()
        entities = runner._parse_entities(lineage_response)
        assert entities.count("orders") == 1
        assert "items" in entities
        assert "customers" in entities

    def test_extract_source_from_hop_qualified_name(self):
        """Extract model name from qualified AS expression."""
        runner = SqlprismCLIRunner()
        hop = {"table": '"i"', "expression": '"memory"."sushi"."items" AS "i"'}
        assert runner._extract_source_from_hop(hop) == "items"

    def test_extract_source_from_hop_fallback_to_table(self):
        """Fall back to table name when no AS expression."""
        runner = SqlprismCLIRunner()
        hop = {"table": "orders", "expression": ""}
        assert runner._extract_source_from_hop(hop) == "orders"

    def test_extract_source_from_hop_skips_with(self):
        """Skip CTE markers like WITH."""
        runner = SqlprismCLIRunner()
        hop = {"table": "WITH", "expression": "SUM(x) AS total"}
        assert runner._extract_source_from_hop(hop) == ""

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_tool_breakdown_counts(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="model_a\n", stderr=""
        )
        runner = SqlprismCLIRunner()
        task = _make_task("find_references", "Where is `stg_orders` used?")
        _, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "query_references" in breakdown
        assert breakdown["query_references"] == 1
