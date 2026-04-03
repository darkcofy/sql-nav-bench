# sql-nav-bench Runner Design Spec

**Date**: 2026-04-03
**Status**: Draft
**Version**: 0.1.0

## Purpose

Add deterministic runners to sql-nav-bench that execute benchmark tasks using either sqlprism CLI tools or a grep/file-read baseline. This produces reproducible, comparable results without requiring an LLM agent.

## Architecture

A `Runner` abstract base class defines the interface. Two implementations ship initially:

- **SqlprismCLIRunner** — calls sqlprism CLI commands, parses output
- **BaselineRunner** — uses grep, find, and file reads to answer tasks

A clean interface allows adding an MCP runner later without refactoring.

---

## Runner Interface

```python
class Runner(ABC):
    name: str

    def setup(self, repo_name: str, repo_path: Path) -> None:
        """One-time setup (e.g., index the repo)."""

    def execute_task(self, task: Task, repo_path: Path) -> Result:
        """Run one task, return a result with metrics."""
```

---

## Task-to-Tool Mapping

Each task has a `tool_hint` field. Runners map this to their own strategy:

| tool_hint | SqlprismCLI Runner | Baseline Runner |
|-----------|-------------------|-----------------|
| `find_references` | `sqlprism query references <name>` | `grep -rl "<name>" --include="*.sql"` then extract model names |
| `column_impact` | `sqlprism query column-usage <table>` | grep for column name across all SQL files |
| `trace_column_lineage` | `sqlprism query lineage <table> <column>` | read file, extract FROM/JOIN/ref(), follow chain, grep for column |
| `trace_dependencies` | `sqlprism query trace <name>` | grep for ref/FROM, recursive follow |
| `find_downstream` | `sqlprism query references <name> --direction downstream` | grep for model name in ref() calls |
| `check_impact` | `sqlprism query references <name>` (transitive) | recursive grep: find consumers, then consumers of consumers |
| `reindex` | `sqlprism reindex-file <path>` then re-query | identify changed file, grep for its model name |

---

## SqlprismCLI Runner

### Setup

```bash
sqlprism reindex --path <repo_path>
```

Indexes the repo once. Subsequent tasks query the index.

### Execution

For each task:
1. Parse `tool_hint` and question to extract entity names
2. Call the appropriate `sqlprism query` subcommand
3. Parse stdout to extract entity names
4. Measure wall time and count subprocess calls
5. Build Result YAML

### Entity Extraction from Questions

Questions follow patterns like:
- "Where is stg_orders used?" → entity = `stg_orders`
- "If I remove column customer_id from stg_orders" → table = `stg_orders`, column = `customer_id`

The runner extracts entities from the task question using simple regex patterns matched against backtick-quoted names or known model references in the question text.

### Output Parsing

Sqlprism CLI outputs structured text (one entity per line or JSON depending on command). The runner parses stdout line-by-line, extracting model/table names. If the output format varies by command, each tool_hint handler has its own parser.

---

## Baseline Runner

### Setup

No-op. Baseline works directly on files.

### Execution Per Category

**Reference (A):** "Where is X used?"
1. `grep -rl "model_name" --include="*.sql"` across repo
2. For each matching file, extract model name from filename/path
3. Filter out the target model itself
4. Return list of consuming models

**Impact (B):** "If X changes, what breaks?"
1. Find direct consumers (same as reference)
2. For each consumer, recursively find ITS consumers (transitive)
3. For column-level: grep for column name in each consumer file, exclude files that don't use it
4. Return full downstream set

**Lineage (C):** "What feeds X?"
1. Read the target model file
2. Extract FROM/JOIN table references and ref() calls via regex
3. For each upstream, recursively read and extract (transitive lineage)
4. Return upstream chain

**Mesh (D):** "Cross-project impact"
Same as impact/reference but search spans all project subdirectories.

**Reindex (E):** "What changed after edit?"
1. Identify the changed file from the question
2. `grep -rl "model_name" --include="*.sql"` to find consumers
3. Return direct consumers

The baseline is deliberately naive — grep will over-count (matches in comments, strings) and miss implicit deps (SELECT *). This is realistic: it's what an agent with only grep can do.

---

## Metrics Collection

| Metric | SqlprismCLI | Baseline |
|--------|------------|----------|
| `tool_calls` | count of sqlprism subprocess calls | count of grep/cat/find calls |
| `search_calls` | 0 | same as tool_calls (all calls are searches) |
| `files_opened` | 0 (index handles it) | count of files read with cat/open |
| `tokens_input` | 0 | 0 |
| `tokens_output` | 0 | 0 |
| `tokens_total` | 0 | 0 |
| `wall_time_seconds` | measured | measured |
| `tool_breakdown` | map of sqlprism command to count | map of grep/cat to count |

Token metrics are 0 for deterministic runners. They become meaningful when the agent benchmark is added later.

---

## CLI Command

```bash
sql-nav-bench run --runner sqlprism-cli --repo jaffle-mesh
sql-nav-bench run --runner baseline --repo jaffle-mesh
sql-nav-bench run --runner sqlprism-cli  # all repos
```

The `run` command:
1. Loads tasks for specified repo (or all)
2. Calls `runner.setup(repo_name, repo_path)` per repo
3. For each task, calls `runner.execute_task(task, repo_path)`
4. Saves result YAML to `results/<runner-name>/<task_id>.yml`
5. Prints summary table

---

## Output Directory

```
results/
  sqlprism-cli/
    jaffle-mesh_ref_01.yml
    jaffle-mesh_ref_02.yml
    ...
  baseline/
    jaffle-mesh_ref_01.yml
    ...
```

Existing `score` and `compare` commands work unchanged on these directories.

---

## File Structure

```
src/sql_nav_bench/
  runners/
    __init__.py        # Runner ABC, runner registry, get_runner()
    sqlprism_cli.py    # SqlprismCLIRunner
    baseline.py        # BaselineRunner
```

CLI addition in `cli.py`:

```python
@main.command()
@click.option("--runner", required=True, type=click.Choice(["sqlprism-cli", "baseline"]))
@click.option("--repo", help="Run against specific repo only")
def run(runner: str, repo: str | None) -> None:
    """Run benchmark tasks with a specific runner."""
```

---

## Scope: Jaffle-mesh First

Initial implementation targets jaffle-mesh only (10 tasks). This validates the full pipeline:
1. Runner executes 10 tasks
2. Results saved as YAML
3. `score` command grades them
4. `compare` shows sqlprism vs baseline

Expand to remaining repos once the pipeline is validated.

---

## Dependencies

- `sqlprism` must be installed and available as CLI command (for SqlprismCLIRunner)
- No new Python dependencies beyond what sql-nav-bench already has

---

## Future: MCP Runner

The Runner ABC is designed so an MCP runner slots in:

```python
class SqlprismMCPRunner(Runner):
    name = "sqlprism-mcp"
    
    def setup(self, repo_name, repo_path):
        # Start MCP server, connect client
    
    def execute_task(self, task, repo_path):
        # Send MCP tool call, parse response
```

This will require `mcp` as a dependency. Deferred to after CLI runner is validated.
