"""SqlprismCLI runner — calls sqlprism CLI commands via subprocess."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import yaml

from sql_nav_bench.models import Task
from sql_nav_bench.runners import Runner
from sql_nav_bench.runners.extract import extract_entities

# Path to sqlprism project — configurable via environment
SQLPRISM_PROJECT = Path.home() / "code" / "sqlprism"

# DuckDB profile for dbt compilation (no real connection needed)
_DBT_PROFILES = """\
default:
  outputs:
    dev:
      type: duckdb
      path: ":memory:"
      schema: bench
      threads: 1
  target: dev
"""


class SqlprismCLIRunner(Runner):
    name = "sqlprism-cli"

    def __init__(self, sqlprism_path: Path | None = None) -> None:
        self._sqlprism_path = sqlprism_path or SQLPRISM_PROJECT
        self._db_path: Path | None = None
        self._profiles_dir: Path | None = None

    def setup(self, repo_name: str, repo_path: Path) -> None:
        """Index the repo with sqlprism using the appropriate method."""
        self._db_path = Path(tempfile.mkdtemp()) / "bench.duckdb"

        # Determine repo type from repos.yml
        repo_type = self._get_repo_type(repo_name)

        # Find sub-projects (e.g., jaffle-mesh has platform/, finance/, marketing/)
        subdirs = [d for d in repo_path.iterdir() if d.is_dir() and list(d.rglob("*.sql"))]
        project_dirs = subdirs if subdirs else [repo_path]

        if repo_type == "dbt":
            self._setup_dbt_profiles()
            for project_dir in project_dirs:
                dbt_project = project_dir / "dbt_project.yml"
                if dbt_project.exists():
                    self._reindex_dbt(project_dir)
                else:
                    self._reindex_plain(project_dir)
        elif repo_type == "sqlmesh":
            for project_dir in project_dirs:
                self._reindex_sqlmesh(project_dir)
        else:
            # Plain SQL
            config = self._make_plain_config(project_dirs)
            self._run_sqlprism(["reindex", "--config", str(config)])

    def _get_repo_type(self, repo_name: str) -> str:
        """Get repo type from repos.yml manifest."""
        manifest_path = Path("repos.yml")
        if manifest_path.exists():
            with open(manifest_path) as f:
                data = yaml.safe_load(f)
            repos = data.get("repos", {})
            if repo_name in repos:
                return repos[repo_name].get("type", "sql")
        return "sql"

    def _setup_dbt_profiles(self) -> None:
        """Create a DuckDB profiles.yml for dbt compilation."""
        self._profiles_dir = Path(tempfile.mkdtemp())
        (self._profiles_dir / "profiles.yml").write_text(_DBT_PROFILES)

    def _reindex_dbt(self, project_dir: Path) -> None:
        """Index a dbt project using reindex-dbt."""
        name = project_dir.name
        project_abs = str(project_dir.resolve())
        # Override the dbt profile to use our DuckDB profile
        self._patch_dbt_profile(project_dir)

        # Install dbt packages first
        dbt_bin = str(self._sqlprism_path / ".venv" / "bin" / "dbt")
        import os
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        subprocess.run(
            [dbt_bin, "deps", "--profiles-dir", str(self._profiles_dir), "--profile", "default"],
            capture_output=True,
            text=True,
            cwd=project_abs,
            env=env,
        )

        args = [
            "reindex-dbt",
            "--name", name,
            "--project", project_abs,
            "--db", str(self._db_path),
            "--dbt-command", dbt_bin,
        ]
        if self._profiles_dir:
            args.extend(["--profiles-dir", str(self._profiles_dir)])
        self._run_sqlprism(args)

    def _patch_dbt_profile(self, project_dir: Path) -> None:
        """Temporarily set dbt_project.yml profile to 'default' for compilation."""
        dbt_project = project_dir / "dbt_project.yml"
        if dbt_project.exists():
            content = dbt_project.read_text()
            # Save original
            (project_dir / "dbt_project.yml.bak").write_text(content)
            # Replace profile line
            import re
            patched = re.sub(r'^profile:\s*"?\w+"?', 'profile: "default"', content, flags=re.MULTILINE)
            dbt_project.write_text(patched)

    def _reindex_sqlmesh(self, project_dir: Path) -> None:
        """Index a sqlmesh project."""
        name = project_dir.name
        self._run_sqlprism([
            "reindex-sqlmesh",
            "--name", name,
            "--project", str(project_dir),
            "--db", str(self._db_path),
        ])

    def _make_plain_config(self, project_dirs: list[Path]) -> Path:
        """Create a config for plain SQL repos."""
        repos_dict = {}
        for d in project_dirs:
            repos_dict[d.name] = {"path": str(d.resolve())}
        config = {
            "db_path": str(self._db_path),
            "repos": repos_dict,
            "dbt_repos": {},
            "sqlmesh_repos": {},
        }
        config_path = Path(tempfile.mkdtemp()) / "sqlprism.json"
        config_path.write_text(json.dumps(config))
        return config_path

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
        # Remove VIRTUAL_ENV to avoid uv conflicts between projects
        import os
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self._sqlprism_path),
            env=env,
        )
        if result.returncode != 0 and result.stderr:
            import sys
            print(f"  sqlprism error: {result.stderr[:200]}", file=sys.stderr)
        return result.stdout

    def _parse_entities(self, output: str) -> list[str]:
        """Parse entity names from sqlprism CLI output (JSON format)."""
        output = output.strip()
        if not output:
            return []

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Fallback: line-by-line for non-JSON output
            return [line.split()[0] for line in output.splitlines()
                    if line.strip() and not line.startswith(("-", "=", "#", "{"))]

        entities = []
        if isinstance(data, dict):
            # references: {"entity": ..., "outbound": [...], "inbound": [...]}
            for key in ("outbound", "inbound", "downstream", "upstream", "matches", "results", "chain"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            entities.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("target") or item.get("source") or ""
                            if name:
                                entities.append(name)
            # column-usage rows
            if "columns" in data and isinstance(data["columns"], list):
                for item in data["columns"]:
                    if isinstance(item, dict):
                        for ref in item.get("used_by", []):
                            if isinstance(ref, str):
                                entities.append(ref)
                            elif isinstance(ref, dict):
                                entities.append(ref.get("name", ""))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    entities.append(item.get("name") or item.get("target") or "")

        return [e for e in entities if e]

    def _query_references(self, name: str, breakdown: dict[str, int]) -> list[str]:
        # inbound = what references this entity (downstream consumers)
        output = self._run_sqlprism(["query", "references", name, "--direction", "inbound"])
        breakdown["query_references"] = breakdown.get("query_references", 0) + 1
        return self._parse_entities(output)

    def _query_trace(self, name: str, direction: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(["query", "trace", name, "--direction", direction, "--max-depth", "5"])
        breakdown["query_trace"] = breakdown.get("query_trace", 0) + 1
        return self._parse_entities(output)

    def _query_column_usage(self, table: str, column: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(["query", "column-usage", table, "--column", column])
        breakdown["query_column_usage"] = breakdown.get("query_column_usage", 0) + 1
        return self._parse_entities(output)

    def _query_lineage(self, model: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(["query", "lineage", "--output-node", model])
        breakdown["query_lineage"] = breakdown.get("query_lineage", 0) + 1
        return self._parse_entities(output)
