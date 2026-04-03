"""Baseline runner — stub."""

from __future__ import annotations

from pathlib import Path

from sql_nav_bench.models import Task
from sql_nav_bench.runners import Runner


class BaselineRunner(Runner):
    name = "baseline"

    def setup(self, repo_name: str, repo_path: Path) -> None:
        pass

    def run_task(self, task: Task, repo_path: Path) -> tuple[list[str], dict[str, int]]:
        return [], {}
