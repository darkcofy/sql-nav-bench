"""SqlprismCLI runner — calls sqlprism CLI commands via subprocess."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from sql_nav_bench.models import Task
from sql_nav_bench.runners import Runner
from sql_nav_bench.runners.extract import extract_entities

# Path to sqlprism project — configurable via environment
SQLPRISM_PROJECT = Path.home() / "code" / "sqlprism"


class SqlprismCLIRunner(Runner):
    name = "sqlprism-cli"

    def __init__(self, sqlprism_path: Path | None = None) -> None:
        self._sqlprism_path = sqlprism_path or SQLPRISM_PROJECT
        self._db_path: Path | None = None
        self._config_path: Path | None = None

    def setup(self, repo_name: str, repo_path: Path) -> None:
        """Create a config and index the repo with sqlprism."""
        self._db_path = Path(tempfile.mkdtemp()) / "bench.duckdb"

        # Collect all subdirectories containing SQL files as separate repos
        repo_paths = []
        # Check if repo_path itself has SQL files
        sql_files = list(repo_path.rglob("*.sql"))
        if sql_files:
            # Check for subdirectories (e.g., jaffle-mesh has platform/, finance/, marketing/)
            subdirs = [d for d in repo_path.iterdir() if d.is_dir() and list(d.rglob("*.sql"))]
            if subdirs:
                for subdir in subdirs:
                    repo_paths.append(str(subdir.resolve()))
            else:
                repo_paths.append(str(repo_path.resolve()))

        repos_dict = {}
        for i, p in enumerate(repo_paths):
            name = Path(p).name
            repos_dict[name] = {"path": p}

        config = {
            "db_path": str(self._db_path),
            "repos": repos_dict,
            "dbt_repos": {},
            "sqlmesh_repos": {},
        }
        self._config_path = Path(tempfile.mkdtemp()) / "sqlprism.json"
        self._config_path.write_text(json.dumps(config))

        self._run_sqlprism(["reindex", "--config", str(self._config_path)])

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
        """Run a sqlprism command via uv in the sqlprism project directory."""
        cmd = ["uv", "run", "sqlprism"] + args
        if self._db_path and "--db" not in args and "--config" not in args:
            cmd.extend(["--db", str(self._db_path)])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self._sqlprism_path),
        )
        return result.stdout

    def _parse_entities(self, output: str) -> list[str]:
        """Parse entity names from sqlprism CLI output (JSON format)."""
        import json as json_lib

        output = output.strip()
        if not output:
            return []

        try:
            data = json_lib.loads(output)
        except json_lib.JSONDecodeError:
            # Fallback: line-by-line parsing for non-JSON output
            entities = []
            for line in output.splitlines():
                line = line.strip()
                if line and not line.startswith(("-", "=", "#", "No ", "{")):
                    entities.append(line.split()[0])
            return entities

        # Handle different JSON output shapes from sqlprism
        entities = []
        if isinstance(data, dict):
            # references: {"entity": ..., "outbound": [...], "inbound": [...]}
            for key in ("outbound", "inbound", "downstream", "upstream", "matches", "results"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            entities.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("target") or item.get("source") or ""
                            if name:
                                entities.append(name)
            # trace: {"chain": [...]}
            if "chain" in data and isinstance(data["chain"], list):
                for item in data["chain"]:
                    if isinstance(item, str):
                        entities.append(item)
                    elif isinstance(item, dict):
                        name = item.get("name") or item.get("target") or ""
                        if name:
                            entities.append(name)
            # column-usage: {"columns": [...]}
            if "columns" in data and isinstance(data["columns"], list):
                for item in data["columns"]:
                    if isinstance(item, dict):
                        # Extract table names where column is used
                        refs = item.get("used_by") or item.get("references") or []
                        for ref in refs:
                            if isinstance(ref, str):
                                entities.append(ref)
                            elif isinstance(ref, dict):
                                entities.append(ref.get("name", ""))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("target") or ""
                    if name:
                        entities.append(name)

        return [e for e in entities if e]

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
