"""Runner ABC and registry."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from sql_nav_bench.models import Metrics, Result, Task


class Runner(ABC):
    """Abstract base class for benchmark runners."""

    name: str

    @abstractmethod
    def setup(self, repo_name: str, repo_path: Path) -> None:
        """One-time setup (e.g., index the repo)."""

    @abstractmethod
    def run_task(self, task: Task, repo_path: Path) -> tuple[list[str], dict[str, int]]:
        """Execute a task. Return (found_entities, tool_breakdown)."""

    def execute_task(self, task: Task, repo_path: Path) -> Result:
        """Run a task with timing, return a Result."""
        start = time.monotonic()
        entities, breakdown = self.run_task(task, repo_path)
        elapsed = time.monotonic() - start

        total_calls = sum(breakdown.values())
        search_calls = total_calls if self.name == "baseline" else 0

        return Result(
            task_id=task.id,
            agent=f"deterministic-{self.name}",
            tools=self.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            answer={
                "entities": entities,
                "explanation": f"Executed via {self.name} runner",
                "confidence": "high",
            },
            metrics=Metrics(
                tool_calls=total_calls,
                search_calls=search_calls,
                files_opened=breakdown.get("file_read", 0) + breakdown.get("cat", 0),
                tokens_input=0,
                tokens_output=0,
                tokens_total=0,
                wall_time_seconds=round(elapsed, 3),
                tool_breakdown=breakdown,
            ),
        )


def get_runner(name: str) -> Runner:
    """Get a runner by name."""
    from sql_nav_bench.runners.baseline import BaselineRunner
    from sql_nav_bench.runners.sqlprism_cli import SqlprismCLIRunner

    registry: dict[str, type[Runner]] = {
        "sqlprism-cli": SqlprismCLIRunner,
        "baseline": BaselineRunner,
    }
    if name not in registry:
        raise ValueError(f"Unknown runner: {name}. Available: {list(registry.keys())}")
    return registry[name]()
