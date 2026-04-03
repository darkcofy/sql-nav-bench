"""SqlprismCLI runner — calls sqlprism CLI commands via subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path

from sql_nav_bench.models import Task
from sql_nav_bench.runners import Runner
from sql_nav_bench.runners.extract import extract_entities


class SqlprismCLIRunner(Runner):
    name = "sqlprism-cli"

    def setup(self, repo_name: str, repo_path: Path) -> None:
        """Index the repo with sqlprism."""
        subprocess.run(
            ["uv", "run", "sqlprism", "reindex", "--path", str(repo_path)],
            capture_output=True,
            text=True,
            check=True,
        )

    def run_task(self, task: Task, repo_path: Path) -> tuple[list[str], dict[str, int]]:
        """Execute a task using sqlprism CLI commands."""
        info = extract_entities(task)
        model = info.get("model") or ""
        column = info.get("column")

        breakdown: dict[str, int] = {}

        if task.tool_hint == "find_references":
            entities = self._query_references(model, breakdown)
        elif task.tool_hint == "check_impact":
            entities = self._query_trace(model, "downstream", breakdown)
        elif task.tool_hint == "trace_dependencies":
            entities = self._query_trace(model, "upstream", breakdown)
        elif task.tool_hint == "trace_column_lineage":
            if column:
                entities = self._query_column_usage(model, column, breakdown)
            else:
                entities = self._query_lineage(model, breakdown)
        elif task.tool_hint == "reindex":
            entities = self._query_references(model, breakdown)
        else:
            entities = self._query_references(model, breakdown)

        return entities, breakdown

    def _run_sqlprism(self, args: list[str]) -> str:
        """Run a sqlprism command and return stdout."""
        result = subprocess.run(
            ["uv", "run", "sqlprism"] + args,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def _parse_entities(self, output: str) -> list[str]:
        """Parse entity names from sqlprism CLI output."""
        entities = []
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or line.startswith(("-", "=", "#", "No ")):
                continue
            parts = line.split()
            if parts:
                name = parts[0].strip("│|").strip()
                if name and not name.startswith(("-", "=")):
                    entities.append(name)
        return entities

    def _query_references(self, name: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(
            ["query", "references", name, "--direction", "outbound"]
        )
        breakdown["query_references"] = breakdown.get("query_references", 0) + 1
        return self._parse_entities(output)

    def _query_trace(self, name: str, direction: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(
            ["query", "trace", name, "--direction", direction, "--max-depth", "5"]
        )
        breakdown["query_trace"] = breakdown.get("query_trace", 0) + 1
        return self._parse_entities(output)

    def _query_column_usage(self, table: str, column: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(
            ["query", "column-usage", table, "--column", column]
        )
        breakdown["query_column_usage"] = breakdown.get("query_column_usage", 0) + 1
        return self._parse_entities(output)

    def _query_lineage(self, model: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(
            ["query", "lineage", "--output-node", model]
        )
        breakdown["query_lineage"] = breakdown.get("query_lineage", 0) + 1
        return self._parse_entities(output)
