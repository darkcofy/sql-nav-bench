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
    def test_reindex_includes_model_itself(self, mock_run: MagicMock):
        """Reindex detects the modified file + its consumers, so the model must appear."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="order_items\norders\n", stderr=""
        )
        runner = SqlprismCLIRunner()
        task = _make_task(
            "reindex",
            "After adding column 'amount' to stg_orders, what does reindex detect?",
            "reindex",
        )
        entities, _ = runner.run_task(task, Path("/tmp/repo"))
        assert entities[0] == "stg_orders"
        assert "order_items" in entities
        assert "orders" in entities

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_column_impact_uses_column_usage(self, mock_run: MagicMock):
        """Removing-column questions route to column-usage, not lineage."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"columns": [{"used_by": ["revenue_a", "revenue_b"]}]}',
            stderr="",
        )
        runner = SqlprismCLIRunner()
        task = _make_task(
            "trace_column_lineage",
            "If I remove the 'price' column from sushi.items, which downstream models break?",
            "impact",
        )
        entities, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "query_column_usage" in breakdown
        assert "query_lineage" not in breakdown
        assert "revenue_a" in entities

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_direct_only_uses_max_depth_1(self, mock_run: MagicMock):
        """Questions mentioning 'direct' should pass --max-depth 1."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        runner = SqlprismCLIRunner()
        task = _make_task(
            "trace_dependencies",
            "What are all the direct upstream dependencies of sushi.waiters?",
            "lineage",
        )
        runner.run_task(task, Path("/tmp/repo"))
        calls = [c.args[0] for c in mock_run.call_args_list if "query" in c.args[0] and "trace" in c.args[0]]
        assert any("1" in c and c[c.index("--max-depth") + 1] == "1" for c in calls)

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_column_lineage_strips_column_name(self, mock_run: MagicMock):
        """The target column name shouldn't leak into the entity set."""
        lineage_response = '{"chains": [{"hops": [{"table": "customer_id", "expression": ""}, {"table": "stg_customers", "expression": ""}]}]}'
        mock_run.return_value = MagicMock(returncode=0, stdout=lineage_response, stderr="")
        runner = SqlprismCLIRunner()
        task = _make_task(
            "trace_column_lineage",
            "Trace the lineage of column customer_id in customers.",
            "lineage",
        )
        entities, _ = runner.run_task(task, Path("/tmp/repo"))
        assert "customer_id" not in entities
        assert "stg_customers" in entities

    @patch("sql_nav_bench.runners.sqlprism_cli.subprocess.run")
    def test_column_usage_usage_schema(self, mock_run: MagicMock):
        """sqlprism's {usage: [{node_name, node_kind, file}]} schema is parsed;
        CTE rows resolve to the enclosing file stem."""
        usage_response = (
            '{"usage": ['
            '{"node_name": "order_total", "node_kind": "cte", '
            ' "file": "memory/sushi/customer_revenue_by_day.sql"},'
            '{"node_name": "waiter_revenue_by_day", "node_kind": "query", '
            ' "file": "memory/sushi/waiter_revenue_by_day.sql"}'
            ']}'
        )
        runner = SqlprismCLIRunner()
        entities = runner._parse_entities(usage_response)
        assert "customer_revenue_by_day" in entities
        assert "waiter_revenue_by_day" in entities
        assert "order_total" not in entities

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
