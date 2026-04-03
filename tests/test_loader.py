"""Tests for YAML loader."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from sql_nav_bench.loader import load_manifest, load_result, load_task, load_tasks

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadTask:
    def test_load_valid_task(self):
        task = load_task(FIXTURES / "valid_task.yml")
        assert task.id == "test_A1_01"
        assert task.repo == "test-repo"
        assert "model_b" in task.gold.required

    def test_load_invalid_task_raises(self):
        with pytest.raises(ValidationError):
            load_task(FIXTURES / "invalid_task.yml")

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_task(FIXTURES / "does_not_exist.yml")


class TestLoadResult:
    def test_load_valid_result(self):
        result = load_result(FIXTURES / "valid_result.yml")
        assert result.task_id == "test_A1_01"
        assert result.metrics.tokens_total == 1500

    def test_load_invalid_result_raises(self):
        with pytest.raises(ValidationError):
            load_result(FIXTURES / "invalid_task.yml")


class TestLoadTasks:
    def test_load_tasks_from_directory(self, tmp_path: Path):
        task_dir = tmp_path / "tasks" / "test-repo"
        task_dir.mkdir(parents=True)
        (task_dir / "A1_test.yml").write_text(
            (FIXTURES / "valid_task.yml").read_text()
        )
        tasks = load_tasks(task_dir)
        assert len(tasks) == 1
        assert tasks[0].id == "test_A1_01"

    def test_load_tasks_empty_directory(self, tmp_path: Path):
        tasks = load_tasks(tmp_path)
        assert tasks == []


class TestLoadManifest:
    def test_load_repos_manifest(self):
        manifest = load_manifest(Path("repos.yml"))
        assert "jaffle-mesh" in manifest.repos
        assert "mozilla-bigquery" in manifest.repos
        assert len(manifest.repos) == 4
