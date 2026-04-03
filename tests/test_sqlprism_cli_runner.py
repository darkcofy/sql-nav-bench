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
    def test_tool_breakdown_counts(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="model_a\n", stderr=""
        )
        runner = SqlprismCLIRunner()
        task = _make_task("find_references", "Where is `stg_orders` used?")
        _, breakdown = runner.run_task(task, Path("/tmp/repo"))
        assert "query_references" in breakdown
        assert breakdown["query_references"] == 1
