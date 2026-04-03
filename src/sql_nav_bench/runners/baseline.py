"""Baseline runner — grep and file read strategies."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from sql_nav_bench.models import Task
from sql_nav_bench.runners import Runner
from sql_nav_bench.runners.extract import extract_entities


class BaselineRunner(Runner):
    name = "baseline"

    def setup(self, repo_name: str, repo_path: Path) -> None:
        """No-op for baseline."""

    def run_task(self, task: Task, repo_path: Path) -> tuple[list[str], dict[str, int]]:
        """Execute a task using grep and file reads."""
        info = extract_entities(task)
        model = info.get("model") or ""
        column = info.get("column")

        breakdown: dict[str, int] = {"grep": 0, "file_read": 0}

        if task.tool_hint in ("find_references", "reindex"):
            entities = self._grep_references(model, repo_path, breakdown)
        elif task.tool_hint == "check_impact":
            entities = self._grep_transitive_downstream(model, repo_path, breakdown)
        elif task.tool_hint == "trace_dependencies":
            entities = self._read_upstream(model, repo_path, breakdown)
        elif task.tool_hint == "trace_column_lineage":
            if column:
                entities = self._grep_column_downstream(model, column, repo_path, breakdown)
            else:
                entities = self._read_upstream(model, repo_path, breakdown)
        else:
            entities = self._grep_references(model, repo_path, breakdown)

        return entities, breakdown

    def _grep_for(self, pattern: str, repo_path: Path, breakdown: dict[str, int]) -> list[Path]:
        """Grep for a pattern across SQL files, return matching file paths."""
        result = subprocess.run(
            ["grep", "-rl", pattern, "--include=*.sql", str(repo_path)],
            capture_output=True,
            text=True,
        )
        breakdown["grep"] = breakdown.get("grep", 0) + 1
        paths = []
        for line in result.stdout.strip().splitlines():
            if line:
                paths.append(Path(line))
        return paths

    def _model_name_from_path(self, path: Path) -> str:
        """Extract model name from a SQL file path."""
        return path.stem

    def _grep_references(
        self, model: str, repo_path: Path, breakdown: dict[str, int]
    ) -> list[str]:
        """Find models that reference the target model."""
        matches = self._grep_for(model, repo_path, breakdown)
        entities = []
        for p in matches:
            name = self._model_name_from_path(p)
            if name != model:
                entities.append(name)
        return list(set(entities))

    def _grep_transitive_downstream(
        self, model: str, repo_path: Path, breakdown: dict[str, int], depth: int = 3
    ) -> list[str]:
        """Find transitive downstream consumers."""
        seen: set[str] = set()
        frontier = [model]

        for _ in range(depth):
            next_frontier = []
            for m in frontier:
                consumers = self._grep_references(m, repo_path, breakdown)
                for c in consumers:
                    if c not in seen and c != model:
                        seen.add(c)
                        next_frontier.append(c)
            frontier = next_frontier
            if not frontier:
                break

        return list(seen)

    def _read_file(self, path: Path, breakdown: dict[str, int]) -> str:
        """Read a file and count it."""
        breakdown["file_read"] = breakdown.get("file_read", 0) + 1
        return path.read_text()

    def _extract_refs_from_sql(self, content: str) -> list[str]:
        """Extract ref() and FROM/JOIN table names from SQL."""
        refs = []
        # dbt ref() patterns
        ref_matches = re.findall(r"ref\(['\"](\w+)['\"]\)", content)
        refs.extend(ref_matches)
        # Two-arg ref: ref('project', 'model')
        ref2_matches = re.findall(r"ref\(['\"][\w]+['\"],\s*['\"](\w+)['\"]\)", content)
        refs.extend(ref2_matches)
        # FROM/JOIN table references (simple)
        from_matches = re.findall(r"(?:FROM|JOIN)\s+(\w+(?:\.\w+)*)", content, re.IGNORECASE)
        for m in from_matches:
            parts = m.split(".")
            refs.append(parts[-1])
        return list(set(refs))

    def _find_model_file(self, model: str, repo_path: Path) -> Path | None:
        """Find the SQL file for a model name."""
        for path in repo_path.rglob(f"{model}.sql"):
            return path
        return None

    def _read_upstream(
        self, model: str, repo_path: Path, breakdown: dict[str, int], depth: int = 3
    ) -> list[str]:
        """Read model file and extract upstream refs, recursively."""
        seen: set[str] = set()
        frontier = [model]

        for _ in range(depth):
            next_frontier = []
            for m in frontier:
                path = self._find_model_file(m, repo_path)
                if not path:
                    continue
                content = self._read_file(path, breakdown)
                refs = self._extract_refs_from_sql(content)
                for r in refs:
                    if r not in seen and r != model:
                        seen.add(r)
                        next_frontier.append(r)
            frontier = next_frontier
            if not frontier:
                break

        return list(seen)

    def _grep_column_downstream(
        self, model: str, column: str, repo_path: Path, breakdown: dict[str, int]
    ) -> list[str]:
        """Find models downstream of a model that use a specific column."""
        consumers = self._grep_transitive_downstream(model, repo_path, breakdown)
        column_users = []
        for consumer in consumers:
            path = self._find_model_file(consumer, repo_path)
            if not path:
                continue
            content = self._read_file(path, breakdown)
            if column in content or "SELECT *" in content.upper():
                column_users.append(consumer)
        return column_users
