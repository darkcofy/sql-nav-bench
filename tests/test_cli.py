"""Tests for CLI commands."""

from pathlib import Path

from click.testing import CliRunner

from sql_nav_bench.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestTasksCommand:
    def test_tasks_no_tasks_directory(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "No tasks" in result.output

    def test_tasks_with_fixture(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            task_dir = Path("tasks") / "test-repo"
            task_dir.mkdir(parents=True)
            (task_dir / "A1_test.yml").write_text(
                (FIXTURES / "valid_task.yml").read_text()
            )
            result = runner.invoke(main, ["tasks"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "test_A1_01" in result.output


class TestValidateCommand:
    def test_validate_no_tasks(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["validate"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "No tasks" in result.output

    def test_validate_valid_task(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            task_dir = Path("tasks") / "test-repo"
            task_dir.mkdir(parents=True)
            (task_dir / "A1_test.yml").write_text(
                (FIXTURES / "valid_task.yml").read_text()
            )
            result = runner.invoke(main, ["validate"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "OK" in result.output
            assert "0 errors" in result.output


class TestScoreCommand:
    def test_score_no_results(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("empty_results").mkdir()
            result = runner.invoke(
                main, ["score", "--results", "empty_results"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "No result" in result.output


class TestCompareCommand:
    def test_compare_with_results(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            for d in ["run_a", "run_b"]:
                Path(d).mkdir()
            result = runner.invoke(
                main, ["compare", "--a", "run_a", "--b", "run_b"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
