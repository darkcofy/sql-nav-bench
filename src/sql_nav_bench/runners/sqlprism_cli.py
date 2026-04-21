"""SqlprismCLI runner — calls sqlprism CLI commands via subprocess."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

from sql_nav_bench.models import Category, Task
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
        question = task.question.lower()
        # "direct" signals immediate neighbors only, unless the question also
        # mentions transitive/both (e.g., "directly or transitively").
        direct_only = (
            ("direct" in question or "directly" in question)
            and "transitive" not in question
            and "both" not in question
        )
        max_depth = 1 if direct_only else 5

        breakdown: dict[str, int] = {}

        # Mesh category with tool_hint=find_references = project-level question
        # (no specific model). mesh+check_impact tasks name a specific model
        # and fall through to the normal impact handler.
        if task.category == Category.MESH and task.tool_hint == "find_references":
            mesh_entities = self._handle_mesh_task(task, breakdown)
            if mesh_entities is not None:
                return mesh_entities, breakdown

        if task.tool_hint == "find_references":
            entities = self._query_references(model, breakdown)
        elif task.tool_hint == "check_impact":
            # Impact = who depends on me = inbound refs = upstream in sqlprism's edge model
            entities = self._query_trace(model, "upstream", breakdown, max_depth=max_depth)
        elif task.tool_hint == "trace_dependencies":
            # Dependencies = what do I depend on = outbound refs = downstream in sqlprism's edge model
            entities = self._query_trace(model, "downstream", breakdown, max_depth=max_depth)
        elif task.tool_hint == "trace_column_lineage":
            # "remove/drop column X from Y, what breaks/downstream?" is column impact,
            # not lineage — who consumes the column, not where it came from.
            if column and self._is_column_impact_question(question):
                entities = self._query_column_usage(model, column, breakdown)
            else:
                # Union column-specific hops (what produced this column's value)
                # with the model's structural upstream (join-only models that
                # gold treats as lineage contributors). Deduplicate.
                col_entities = self._query_lineage(model, breakdown, column=column)
                trace_entities = self._query_trace(model, "downstream", breakdown, max_depth=max_depth)
                entities = list(dict.fromkeys(col_entities + trace_entities))
                if column:
                    entities = [e for e in entities if e != column]
        elif task.tool_hint == "reindex":
            # Reindex detects file-level change of the modified model itself,
            # plus its direct consumers as potentially affected.
            consumers = self._query_references(model, breakdown)
            entities = [model] + [e for e in consumers if e != model] if model else consumers
        else:
            entities = self._query_references(model, breakdown)

        # mesh tasks that didn't use the project-level handler (e.g. mesh +
        # check_impact) may still want schema-qualified names if the repo
        # uses schema sub-directories. Qualify from each entity's defining file.
        if task.category == Category.MESH and entities:
            entities = self._qualify_entities_via_lookup(entities, breakdown)

        return entities, breakdown

    def _qualify_entities_via_lookup(self, entities: list[str], breakdown: dict[str, int]) -> list[str]:
        """Qualify each entity as schema.name when its defining file lives under
        a schema-like directory. Uses `query search` per unique name to find
        the defining file.
        """
        cache: dict[str, str] = {}
        resolved: list[str] = []
        for name in entities:
            if name in cache:
                resolved.append(cache[name])
                continue
            definers = self._defining_nodes_for_name(name, breakdown)
            qualified = name
            for d in definers:
                candidate = self._qualify_for_mesh(name, d.get("file") or "")
                if candidate != name:
                    qualified = candidate
                    break
            cache[name] = qualified
            resolved.append(qualified)
        return resolved

    @staticmethod
    def _is_column_impact_question(question: str) -> bool:
        """Detect questions about downstream column impact vs upstream lineage."""
        q = question.lower()
        removed = any(w in q for w in ("remove", "drop", "delete"))
        downstream = any(w in q for w in ("break", "downstream", "affect", "impact", "consume"))
        return removed and downstream

    def _get_indexed_repos(self) -> list[str]:
        """List non-empty repo names from `sqlprism status`."""
        output = self._run_sqlprism(["status"])
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        return [
            r["name"] for r in data.get("repos", [])
            if isinstance(r, dict) and r.get("name") and r.get("file_count", 0) > 0
        ]

    @staticmethod
    def _parse_mesh_projects(question: str, repos: list[str]) -> tuple[str | None, str | None]:
        """Determine (source, target) project names from a mesh question.

        Returns the first two repo names mentioned in the question, ordered by
        position. Single-repo questions (e.g. "what consumes from platform")
        return (source, None). Ignores repos appearing inside parenthetical
        "(not just from X)" clauses, which are negation hints.
        """
        q = question.lower()
        # Drop parenthetical negation clauses from matching
        q_clean = re.sub(r"\((?:not\s+just|excluding|except)[^)]*\)", "", q, flags=re.IGNORECASE)
        positions: list[tuple[int, str]] = []
        for repo in repos:
            idx = q_clean.find(repo.lower())
            if idx >= 0:
                positions.append((idx, repo))
        positions.sort()
        if not positions:
            return None, None
        if len(positions) == 1:
            return positions[0][1], None
        return positions[0][1], positions[1][1]

    def _list_repo_models(self, repo: str, breakdown: dict[str, int]) -> list[dict]:
        """Enumerate actual model-like nodes in a repo, deduplicated by name.

        sqlprism indexes dbt ref() targets as table nodes inside the referring
        repo (e.g. `orders` shows up in `marketing` because marketing refs it).
        Filter those out by requiring that the node name matches its file stem,
        which is true only for the model that *defines* that name.
        """
        output = self._run_sqlprism(["query", "search", "", "--repo", repo, "--limit", "500"])
        breakdown["query_search"] = breakdown.get("query_search", 0) + 1
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        seen: set[str] = set()
        models: list[dict] = []
        for m in data.get("matches", []):
            if not isinstance(m, dict):
                continue
            name = m.get("name")
            if not name or m.get("kind") == "cte":
                continue
            file = m.get("file", "") or ""
            if ".yml/" in file:
                continue
            if file and Path(file).stem != name:
                continue
            if name in seen:
                continue
            seen.add(name)
            models.append({"name": name, "file": file})
        return models

    def _query_references_edges(self, name: str, direction: str, breakdown: dict[str, int], repo: str | None = None) -> list[dict]:
        """Return raw reference edges with {name, repo, file, ...} fields."""
        args = ["query", "references", name, "--direction", direction]
        if repo:
            args.extend(["--repo", repo])
        output = self._run_sqlprism(args)
        breakdown["query_references"] = breakdown.get("query_references", 0) + 1
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        key = "inbound" if direction == "inbound" else "outbound"
        return [r for r in data.get(key, []) if isinstance(r, dict)]

    def _defining_nodes_for_name(self, name: str, breakdown: dict[str, int]) -> list[dict]:
        """Return all repos where `name` is defined (file stem matches).

        A model name can be defined in multiple repos (different projects with
        colliding names); return every match so callers can decide which one
        is relevant.
        """
        output = self._run_sqlprism(["query", "search", name, "--limit", "20"])
        breakdown["query_search"] = breakdown.get("query_search", 0) + 1
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        definers: list[dict] = []
        for m in data.get("matches", []):
            if not isinstance(m, dict):
                continue
            if m.get("name") != name or m.get("kind") == "cte":
                continue
            file = m.get("file") or ""
            if ".yml/" in file:
                continue
            if file and Path(file).stem == name:
                definers.append({"repo": m.get("repo"), "file": file})
        return definers

    @staticmethod
    def _qualify_for_mesh(name: str, file_path: str) -> str:
        """Qualify a model as schema.name when the parent dir looks like a schema.

        dbt layer dirs (models/staging/marts/...) are skipped; sqlmesh schema
        dirs (bronze/silver/sushi/...) become the qualifier.
        """
        if not file_path:
            return name
        parent = Path(file_path).parent.name
        skip = {"models", "staging", "marts", "sources", "snapshots", "analyses", "macros", "seeds"}
        if parent and parent.lower() not in skip:
            return f"{parent}.{name}"
        return name

    def _handle_mesh_task(self, task: Task, breakdown: dict[str, int]) -> list[str] | None:
        """Cross-project/cross-repo query handler. Returns None to fall through
        to the default handler when the question doesn't parse as a mesh query.
        """
        repos = self._get_indexed_repos()
        if not repos:
            return None
        source, target = self._parse_mesh_projects(task.question, repos)
        if not source:
            return None
        models = self._list_repo_models(source, breakdown)
        # Cache defining-node lookups across all refs to cut query_search calls.
        define_cache: dict[str, list[dict]] = {}

        def define_repos(ref_name: str) -> set[str]:
            if ref_name not in define_cache:
                define_cache[ref_name] = self._defining_nodes_for_name(ref_name, breakdown)
            return {n["repo"] for n in define_cache[ref_name] if n.get("repo")}

        if target is None:
            # "which projects consume models from <source>?" → consumer repos.
            # Inbound edges' `repo` field points to the source-side node, so
            # we resolve the consumer's defining repo from the edge's name.
            consumers: set[str] = set()
            for m in models:
                for ref in self._query_references_edges(m["name"], "inbound", breakdown, repo=source):
                    consumer_repo = ref.get("repo")
                    if consumer_repo and consumer_repo != source:
                        consumers.add(consumer_repo)
                        continue
                    for origin in define_repos(ref.get("name", "")):
                        if origin != source:
                            consumers.add(origin)
            return sorted(consumers)

        # "which models in <source> depend on models from <target>?"
        qualify = any(
            Path(m["file"]).parent.name.lower() not in {
                "", "models", "staging", "marts", "sources", "snapshots",
            }
            for m in models if m["file"]
        )
        results: list[str] = []
        for m in models:
            edges = self._query_references_edges(m["name"], "outbound", breakdown, repo=source)
            target_names = {e["name"] for e in edges if e.get("name")}
            if any(target in define_repos(tname) for tname in target_names):
                results.append(self._qualify_for_mesh(m["name"], m["file"]) if qualify else m["name"])
        return results

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
            # column lineage chains: {"chains": [{"hops": [{"table": ..., "expression": ...}]}]}
            # Leaf hops (last in chain) contain source model refs in expressions
            # like: "memory"."sushi"."items" AS "i"
            if "chains" in data and isinstance(data["chains"], list):
                seen_tables: set[str] = set()
                for chain in data["chains"]:
                    if not isinstance(chain, dict):
                        continue
                    hops = chain.get("hops", [])
                    for hop in hops:
                        table = self._extract_source_from_hop(hop)
                        if table and table not in seen_tables:
                            seen_tables.add(table)
                            entities.append(table)
            # column-usage rows
            if "columns" in data and isinstance(data["columns"], list):
                for item in data["columns"]:
                    if isinstance(item, dict):
                        for ref in item.get("used_by", []):
                            if isinstance(ref, str):
                                entities.append(ref)
                            elif isinstance(ref, dict):
                                entities.append(ref.get("name", ""))
            # column-usage sqlprism schema: {"usage": [{node_name, node_kind, file, ...}]}
            # CTE rows resolve to the enclosing file's stem, since CTEs aren't
            # standalone models for bench scoring.
            if "usage" in data and isinstance(data["usage"], list):
                for row in data["usage"]:
                    if not isinstance(row, dict):
                        continue
                    kind = row.get("node_kind")
                    if kind == "cte":
                        file_path = row.get("file") or ""
                        if file_path:
                            entities.append(Path(file_path).stem)
                    else:
                        name = row.get("node_name")
                        if name:
                            entities.append(name)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    entities.append(item.get("name") or item.get("target") or "")

        return [e for e in entities if e]

    @staticmethod
    def _extract_source_from_hop(hop: dict) -> str:
        """Extract the source model name from a column lineage hop.

        Hop tables are often CTE aliases (e.g., "ot", "i"). The actual source
        model name is in the expression for leaf hops — table reference patterns:
          "memory"."sushi"."items" AS "i"
          "sushi"."order_items" AS "oi"
        Returns the last unquoted segment of the qualified name, or empty string
        for intermediate CTE/subquery hops.
        """
        import re
        expr = hop.get("expression", "")
        # Match: qualified_table_ref AS alias (must contain dots = qualified name)
        # e.g. "memory"."sushi"."items" AS "i" → items
        # Does NOT match: SUM(x) AS "total" (function expressions)
        as_match = re.match(r'^((?:"[^"]+"|[\w]+)(?:\.(?:"[^"]+"|[\w]+))+)\s+AS\s+', expr, re.IGNORECASE)
        if as_match:
            qualified = as_match.group(1)
            parts = qualified.split(".")
            return parts[-1].strip('"').strip("'")
        # Fallback: use the table field, skip CTE-like names
        table = hop.get("table", "").strip('"').strip("'")
        if table and table.upper() not in ("WITH", "SUBQUERY"):
            # Skip short aliases (1-3 chars) that are likely CTE aliases
            if len(table) <= 3 and table.isalpha():
                return ""
            return table
        return ""

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

    def _query_trace(self, name: str, direction: str, breakdown: dict[str, int], max_depth: int = 5) -> list[str]:
        output = self._run_sqlprism(["query", "trace", name, "--direction", direction, "--max-depth", str(max_depth)])
        breakdown["query_trace"] = breakdown.get("query_trace", 0) + 1
        return self._parse_entities(output)

    def _query_column_usage(self, table: str, column: str, breakdown: dict[str, int]) -> list[str]:
        output = self._run_sqlprism(["query", "column-usage", table, "--column", column])
        breakdown["query_column_usage"] = breakdown.get("query_column_usage", 0) + 1
        return self._parse_entities(output)

    def _query_lineage(self, model: str, breakdown: dict[str, int], column: str | None = None) -> list[str]:
        args = ["query", "lineage", "--output-node", model]
        if column:
            args.extend(["--column", column])
        output = self._run_sqlprism(args)
        breakdown["query_lineage"] = breakdown.get("query_lineage", 0) + 1
        return self._parse_entities(output)
