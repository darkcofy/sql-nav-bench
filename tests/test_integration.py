"""End-to-end integration tests."""

from pathlib import Path

from click.testing import CliRunner

from sql_nav_bench.cli import main
from sql_nav_bench.loader import load_results, load_task
from sql_nav_bench.report import generate_comparison
from sql_nav_bench.scorer import score_set_match

FIXTURES = Path(__file__).parent / "fixtures"


class TestEndToEnd:
    def test_score_baseline_vs_sqlprism(self):
        task = load_task(FIXTURES / "valid_task.yml")
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        assert len(baseline) == 1
        assert len(sqlprism) == 1

        bs = score_set_match(baseline[0].answer["entities"], task.gold)
        assert bs.recall < 1.0

        ss = score_set_match(sqlprism[0].answer["entities"], task.gold)
        assert ss.recall == 1.0
        assert ss.f1 > bs.f1

    def test_token_comparison(self):
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        assert baseline[0].metrics.tokens_total > sqlprism[0].metrics.tokens_total
        assert baseline[0].metrics.tool_calls > sqlprism[0].metrics.tool_calls

    def test_comparison_table(self):
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        table = generate_comparison(baseline, sqlprism, "baseline", "sqlprism")
        assert "baseline" in table
        assert "sqlprism" in table
        assert "reduction" in table.lower()

    def test_cli_compare(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "compare",
                "--a", str(FIXTURES / "results_baseline"),
                "--b", str(FIXTURES / "results_sqlprism"),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "baseline" in result.output
        assert "sqlprism" in result.output
