"""Tests for report generation."""

from sql_nav_bench.models import Metrics, Result
from sql_nav_bench.report import generate_comparison, generate_summary


def _make_result(task_id: str, tools: str, tokens: int, tool_calls: int, entities: list[str]) -> Result:
    return Result(
        task_id=task_id,
        agent="test-agent",
        tools=tools,
        timestamp="2026-04-03T10:00:00Z",
        answer={"entities": entities, "explanation": "test", "confidence": "high"},
        metrics=Metrics(
            tool_calls=tool_calls,
            search_calls=tool_calls - 1 if tools == "baseline" else 0,
            files_opened=tool_calls,
            tokens_input=tokens // 2,
            tokens_output=tokens // 2,
            tokens_total=tokens,
            wall_time_seconds=float(tool_calls),
            tool_breakdown={},
        ),
    )


class TestGenerateComparison:
    def test_comparison_table_structure(self):
        run_a = [_make_result("t1", "baseline", 47200, 22, ["a"])]
        run_b = [_make_result("t1", "sqlprism", 2840, 3, ["a", "b"])]
        table = generate_comparison(run_a, run_b, "baseline", "sqlprism")
        assert "baseline" in table
        assert "sqlprism" in table
        assert "Tokens" in table

    def test_comparison_shows_both_runs(self):
        run_a = [_make_result("t1", "baseline", 10000, 10, ["a"])]
        run_b = [_make_result("t1", "sqlprism", 1000, 2, ["a"])]
        table = generate_comparison(run_a, run_b, "baseline", "sqlprism")
        assert "10000" in table or "10,000" in table
        assert "1000" in table or "1,000" in table


class TestGenerateSummary:
    def test_summary_json_structure(self):
        results = [_make_result("t1", "sqlprism", 2840, 3, ["a", "b"])]
        summary = generate_summary(results)
        assert len(summary) == 1
        assert summary[0]["task_id"] == "t1"
        assert "metrics" in summary[0]
