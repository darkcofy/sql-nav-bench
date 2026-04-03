"""Tests for the run CLI command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from sql_nav_bench.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestRunCommand:
    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "runner" in result.output

    def test_run_baseline_with_fixture_tasks(self, tmp_path: Path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # Create task
            task_dir = Path("tasks") / "test-repo"
            task_dir.mkdir(parents=True)
            (task_dir / "A1_test.yml").write_text(
                (FIXTURES / "valid_task.yml").read_text()
            )

            # Create minimal repo
            repo_dir = Path("repos") / "test-repo"
            repo_dir.mkdir(parents=True)
            models = repo_dir / "models"
            models.mkdir()
            (models / "model_a.sql").write_text("SELECT * FROM raw.table")
            (models / "model_b.sql").write_text(
                "SELECT * FROM {{ ref('model_a') }}"
            )
            (models / "model_c.sql").write_text(
                "SELECT * FROM {{ ref('model_a') }}"
            )

            result = runner.invoke(
                main,
                ["run", "--runner", "baseline", "--repo", "test-repo"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Check results were saved
            results_dir = Path("results") / "baseline"
            assert results_dir.exists()
            result_files = list(results_dir.glob("*.yml"))
            assert len(result_files) == 1

            # Verify result YAML is valid
            with open(result_files[0]) as f:
                data = yaml.safe_load(f)
            assert data["task_id"] == "test_A1_01"
            assert data["tools"] == "baseline"
            assert "metrics" in data
