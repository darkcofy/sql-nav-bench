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
            dbt_projects = list(repo_path.rglob("dbt_project.yml"))
            if dbt_projects:
                ordered = self._topo_sort_dbt_projects(dbt_projects)
                for project_dir in ordered:
                    self._inject_local_deps(project_dir, repo_path)
                    self._reindex_dbt(project_dir)
            else:
                import sys
                print(f"  No dbt_project.yml found in {repo_path}", file=sys.stderr)
        elif repo_type == "sqlmesh":
            # Find sqlmesh projects by locating config.py or config.yaml
            sqlmesh_configs = list(repo_path.rglob("config.py")) + list(repo_path.rglob("config.yaml"))
            sqlmesh_dirs = sorted({c.parent for c in sqlmesh_configs})
            indexed = 0
            for project_dir in sqlmesh_dirs:
                # Skip dbt sub-projects
                if (project_dir / "dbt_project.yml").exists():
                    continue
                import sys
                print(f"  Indexing sqlmesh project: {project_dir.name}", file=sys.stderr)
                self._reindex_sqlmesh(project_dir)
                indexed += 1
            if indexed == 0:
                import sys
                print(f"  No sqlmesh projects found in {repo_path}", file=sys.stderr)
        else:
            # Plain SQL
            dialect = self._get_repo_meta(repo_name).get("dialect")
            config = self._make_plain_config(project_dirs, dialect=dialect)
            self._run_sqlprism(["reindex", "--config", str(config)])

    def _get_repo_type(self, repo_name: str) -> str:
        """Get repo type from repos.yml manifest."""
        return self._get_repo_meta(repo_name).get("type", "sql")

    def _get_repo_meta(self, repo_name: str) -> dict:
        """Get full repo metadata from repos.yml manifest."""
        manifest_path = Path("repos.yml")
        if manifest_path.exists():
            with open(manifest_path) as f:
                data = yaml.safe_load(f)
            repos = data.get("repos", {})
            if repo_name in repos:
                return repos[repo_name]
        return {}

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

    def _topo_sort_dbt_projects(self, dbt_project_files: list[Path]) -> list[Path]:
        """Sort dbt projects by dependency order using dependencies.yml."""
        # Map project name → project dir
        name_to_dir: dict[str, Path] = {}
        dir_to_deps: dict[Path, list[str]] = {}

        for proj_file in dbt_project_files:
            project_dir = proj_file.parent
            content = proj_file.read_text()
            # Extract project name
            name = None
            for line in content.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip("'\"")
                    break
            if name:
                name_to_dir[name] = project_dir

            # Read dependencies
            deps_file = project_dir / "dependencies.yml"
            dep_names: list[str] = []
            if deps_file.exists():
                deps_data = yaml.safe_load(deps_file.read_text()) or {}
                for proj in deps_data.get("projects", []):
                    if isinstance(proj, dict) and "name" in proj:
                        dep_names.append(proj["name"])
            dir_to_deps[project_dir] = dep_names

        # Topological sort (Kahn's algorithm)
        all_dirs = list(dir_to_deps.keys())
        in_degree: dict[Path, int] = {d: 0 for d in all_dirs}
        for d, deps in dir_to_deps.items():
            for dep_name in deps:
                if dep_name in name_to_dir:
                    in_degree[d] += 1

        queue = [d for d in all_dirs if in_degree[d] == 0]
        result: list[Path] = []
        while queue:
            d = queue.pop(0)
            result.append(d)
            # Find project name for d
            d_name = next((n for n, p in name_to_dir.items() if p == d), None)
            if d_name:
                for other, deps in dir_to_deps.items():
                    if d_name in deps:
                        in_degree[other] -= 1
                        if in_degree[other] == 0:
                            queue.append(other)

        # Add any remaining (circular deps — shouldn't happen)
        for d in all_dirs:
            if d not in result:
                result.append(d)

        return result

    def _inject_local_deps(self, project_dir: Path, repo_root: Path) -> None:
        """Add upstream dbt projects as local packages for cross-project refs."""
        deps_file = project_dir / "dependencies.yml"
        if not deps_file.exists():
            return

        deps_data = yaml.safe_load(deps_file.read_text()) or {}
        dep_names = [p["name"] for p in deps_data.get("projects", [])
                     if isinstance(p, dict) and "name" in p]
        if not dep_names:
            return

        # Find upstream project dirs by matching dbt_project.yml names
        local_packages: list[dict] = []
        for proj_file in repo_root.rglob("dbt_project.yml"):
            if proj_file.parent == project_dir:
                continue
            content = proj_file.read_text()
            for line in content.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip("'\"")
                    if name in dep_names:
                        import os
                        rel_path = os.path.relpath(proj_file.parent, project_dir)
                        local_packages.append({"local": rel_path})
                    break

        if not local_packages:
            return

        # Read existing packages.yml and append local deps
        packages_file = project_dir / "packages.yml"
        if packages_file.exists():
            pkg_data = yaml.safe_load(packages_file.read_text()) or {}
        else:
            pkg_data = {}

        existing = pkg_data.get("packages", [])
        # Avoid duplicates
        existing_locals = {p.get("local") for p in existing if isinstance(p, dict) and "local" in p}
        for lp in local_packages:
            if lp["local"] not in existing_locals:
                existing.append(lp)
        pkg_data["packages"] = existing

        # Backup and write
        if packages_file.exists():
            (project_dir / "packages.yml.bak").write_text(packages_file.read_text())
        packages_file.write_text(yaml.dump(pkg_data, default_flow_style=False))

    def _reindex_sqlmesh(self, project_dir: Path) -> None:
        """Index a sqlmesh project."""
        name = project_dir.name
        sqlmesh_python = self._get_sqlmesh_python()
        args = [
            "reindex-sqlmesh",
            "--name", name,
            "--project", str(project_dir.resolve()),
            "--db", str(self._db_path),
            "--dialect", "duckdb",
        ]
        if sqlmesh_python:
            args.extend(["--sqlmesh-command", sqlmesh_python])
        self._run_sqlprism(args)

    def _get_sqlmesh_python(self) -> str | None:
        """Find a Python interpreter that has sqlmesh installed.

        sqlmesh conflicts with sqlglot[c] so it needs an isolated venv.
        Looks for /tmp/sqlmesh-venv/bin/python first, then falls back to None.
        """
        candidate = Path("/tmp/sqlmesh-venv/bin/python")
        if candidate.exists():
            return str(candidate)
        return None

    def _make_plain_config(self, project_dirs: list[Path], dialect: str | None = None) -> Path:
        """Create a config for plain SQL repos."""
        repos_dict = {}
        for d in project_dirs:
            entry: dict = {"path": str(d.resolve())}
            if dialect:
                entry["dialect"] = dialect
            repos_dict[d.name] = entry
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
            # Impact = who depends on me = inbound refs = upstream in sqlprism's edge model
            entities = self._query_trace(model, "upstream", breakdown)
        elif task.tool_hint == "trace_dependencies":
            # Dependencies = what do I depend on = outbound refs = downstream in sqlprism's edge model
            entities = self._query_trace(model, "downstream", breakdown)
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
        if result.returncode != 0:
            import sys
            output = result.stderr[:500] or result.stdout[:500]
            if output:
                print(f"  sqlprism error: {output}", file=sys.stderr)
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
            for key in ("outbound", "inbound", "downstream", "upstream", "matches", "results", "chain", "paths"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            entities.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("target") or item.get("source") or ""
                            if name:
                                # Derive dataset.table from file path if available
                                qualified = self._qualify_name(name, item.get("file"))
                                entities.append(qualified)
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

    @staticmethod
    def _qualify_name(name: str, file_path: str | None) -> str:
        """Derive dataset.table name from file path when possible.

        BigQuery repos use paths like `project/dataset/table/query.sql`.
        Returns `dataset.table` if detectable, otherwise just `name`.
        """
        if not file_path or "/" not in file_path:
            return name
        parts = file_path.rstrip("/").split("/")
        # Pattern: .../dataset/table_name/query.sql or .../dataset/table_name/view.sql
        if len(parts) >= 3:
            dataset = parts[-3]
            table_dir = parts[-2]
            # Only qualify if the table_dir matches the node name
            if table_dir == name:
                return f"{dataset}.{name}"
        return name

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
