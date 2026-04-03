# sql-nav-bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a vendor-agnostic benchmark for evaluating how well agents understand SQL project structure, with a scorer CLI and task sets across 4 real-world repos.

**Architecture:** YAML task files define questions with gold answers. A Python CLI clones benchmark repos, validates task files, scores agent results against gold (P/R/F1 + token efficiency), and produces comparison reports. No LLM SDKs — users bring their own agent.

**Tech Stack:** Python 3.12+, uv, click, pydantic, pyyaml, pytest

**User Verification:** NO — no user verification required

---

### Task 0: Project scaffold and packaging

**Goal:** Create the uv project with pyproject.toml, directory structure, git init, and repos.yml manifest.

**Files:**
- Create: `pyproject.toml`
- Create: `repos.yml`
- Create: `src/sql_nav_bench/__init__.py`
- Create: `LICENSE`
- Create: `README.md`
- Create: `tools/sqlprism.yml`
- Create: `tools/baseline.yml`
- Create: `results/.gitkeep`
- Create: `tasks/.gitkeep`

**Acceptance Criteria:**
- [ ] `uv sync` succeeds
- [ ] `sql-nav-bench --help` shows CLI entry point
- [ ] repos.yml contains all 4 benchmark repos
- [ ] git repo initialized with first commit

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv sync && uv run sql-nav-bench --help`

**Steps:**

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/alfred/code/sql-nav-bench
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "sql-nav-bench"
version = "0.1.0"
description = "Benchmark for evaluating agent SQL project understanding"
requires-python = ">=3.12"
license = "Apache-2.0"
dependencies = [
    "click>=8.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]

[project.scripts]
sql-nav-bench = "sql_nav_bench.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sql_nav_bench"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 120
```

- [ ] **Step 3: Create src/sql_nav_bench/__init__.py**

```python
"""sql-nav-bench: Benchmark for evaluating agent SQL project understanding."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create CLI skeleton**

```python
# src/sql_nav_bench/cli.py
"""CLI entry point for sql-nav-bench."""

import click

from sql_nav_bench import __version__


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """sql-nav-bench: Benchmark for agent SQL project understanding."""


@main.command()
@click.option("--repo", help="Clone a specific repo only")
def setup(repo: str | None) -> None:
    """Clone benchmark repos."""
    click.echo("setup: not yet implemented")


@main.command()
@click.option("--repo", help="Filter by repo")
@click.option("--category", help="Filter by category")
def tasks(repo: str | None, category: str | None) -> None:
    """List available benchmark tasks."""
    click.echo("tasks: not yet implemented")


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results directory")
@click.option("--repo", help="Filter by repo")
def score(results: str, repo: str | None) -> None:
    """Score results against gold answers."""
    click.echo("score: not yet implemented")


@main.command()
@click.option("--a", "run_a", required=True, type=click.Path(exists=True), help="First results directory")
@click.option("--b", "run_b", required=True, type=click.Path(exists=True), help="Second results directory")
def compare(run_a: str, run_b: str) -> None:
    """Compare two benchmark runs side-by-side."""
    click.echo("compare: not yet implemented")


@main.command()
def validate() -> None:
    """Validate task and result files."""
    click.echo("validate: not yet implemented")
```

- [ ] **Step 5: Create repos.yml**

```yaml
repos:
  jaffle-mesh:
    type: dbt
    sources:
      - url: https://github.com/dbt-labs/jaffle-shop-mesh-platform
        path: platform/
      - url: https://github.com/dbt-labs/jaffle-shop-mesh-finance
        path: finance/
      - url: https://github.com/dbt-labs/jaffle-shop-mesh-marketing
        path: marketing/
    pin: main
    difficulty: medium
    description: "dbt mesh trio — cross-project deps, contracts, groups"

  sqlmesh-examples:
    type: sqlmesh
    sources:
      - url: https://github.com/TobikoData/sqlmesh
        sparse_checkout: examples/
        path: examples/
    pin: main
    difficulty: medium
    description: "SQLMesh multi-project — multi-repo, hybrid dbt+sqlmesh"

  mozilla-bigquery:
    type: sql
    sources:
      - url: https://github.com/mozilla/bigquery-etl
        path: .
    pin: main
    difficulty: brutal
    description: "2,346 raw SQL files, BigQuery dialect, deep nesting"

  cal-itp:
    type: dbt
    sources:
      - url: https://github.com/cal-itp/data-infra
        sparse_checkout: warehouse/
        path: warehouse/
    pin: main
    difficulty: brutal
    description: "630 dbt models, staging/int/mart layers, real public infra"
```

- [ ] **Step 6: Create tool configs**

`tools/sqlprism.yml`:
```yaml
name: sqlprism
description: "SQLPrism MCP server — structural SQL tools"
type: mcp
config:
  command: uv
  args: ["run", "sqlprism", "serve"]
tools:
  - search
  - find_references
  - find_column_usage
  - trace_dependencies
  - trace_column_lineage
  - get_schema
  - get_context
  - check_impact
  - pr_impact
  - find_path
  - find_critical_models
  - detect_cycles
  - find_subgraphs
  - find_bottlenecks
  - index_status
  - reindex
  - reindex_files
  - reindex_dbt
  - reindex_sqlmesh
```

`tools/baseline.yml`:
```yaml
name: baseline
description: "Search-only baseline — grep, file read, glob"
type: native
tools:
  - grep
  - file_read
  - glob
  - bash
```

- [ ] **Step 7: Create LICENSE (Apache-2.0), .gitkeep files, README.md stub**

```bash
touch results/.gitkeep tasks/.gitkeep
```

`README.md`:
```markdown
# sql-nav-bench

Benchmark for evaluating how well agents understand SQL project structure.

Tests structural reasoning — lineage, impact analysis, dependencies, cross-project navigation — not SQL query generation.

## Quick Start

```bash
uv sync
sql-nav-bench setup          # clone benchmark repos
sql-nav-bench tasks           # list available tasks
sql-nav-bench score --results results/my-run/
sql-nav-bench compare --a results/baseline/ --b results/sqlprism/
```

See [docs/](docs/) for full documentation.
```

- [ ] **Step 8: uv sync, verify CLI, initial commit**

```bash
cd /home/alfred/code/sql-nav-bench
uv sync
uv run sql-nav-bench --help
git add pyproject.toml repos.yml src/ tools/ results/ tasks/ README.md LICENSE docs/
git commit -m "chore: initial project scaffold"
```

---

### Task 1: Pydantic models

**Goal:** Define all data shapes — Task, Gold, Result, Metrics, RepoManifest — as pydantic models with validation.

**Files:**
- Create: `src/sql_nav_bench/models.py`
- Create: `tests/test_models.py`

**Acceptance Criteria:**
- [ ] Task model validates all fields from spec (id, repo, category, difficulty, question, tool_hint, gold, scoring, notes)
- [ ] Gold model validates required/optional/forbidden entity lists
- [ ] Result model validates answer + metrics with all required fields
- [ ] Metrics model requires tokens_total, tool_calls, search_calls, files_opened, wall_time_seconds, tokens_input, tokens_output, tool_breakdown
- [ ] RepoManifest model validates repos.yml structure
- [ ] Invalid data raises ValidationError with clear messages
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_models.py -v`

**Steps:**

- [ ] **Step 1: Write tests for Task model**

```python
# tests/test_models.py
"""Tests for pydantic data models."""

import pytest
from pydantic import ValidationError

from sql_nav_bench.models import (
    Category,
    Difficulty,
    Gold,
    Metrics,
    Result,
    ScoringConfig,
    ScoringMethod,
    Task,
)


class TestTaskModel:
    def test_valid_task(self):
        task = Task(
            id="jaffle-mesh_B1_01",
            repo="jaffle-mesh",
            category=Category.IMPACT,
            difficulty=Difficulty.MEDIUM,
            question="If I remove customer_id from stg_orders, what breaks?",
            tool_hint="column_impact",
            gold=Gold(
                required=["int_orders", "fct_orders"],
                optional=["mart_customer_orders"],
                forbidden=["stg_customers"],
            ),
            scoring=ScoringConfig(method=ScoringMethod.SET_MATCH, partial_credit=True),
        )
        assert task.id == "jaffle-mesh_B1_01"
        assert task.category == Category.IMPACT
        assert len(task.gold.required) == 2

    def test_task_missing_required_fields(self):
        with pytest.raises(ValidationError):
            Task(id="bad", repo="x")  # type: ignore[call-arg]

    def test_task_invalid_category(self):
        with pytest.raises(ValidationError):
            Task(
                id="t1",
                repo="r",
                category="invalid",  # type: ignore[arg-type]
                difficulty=Difficulty.EASY,
                question="q",
                tool_hint="h",
                gold=Gold(required=["a"]),
                scoring=ScoringConfig(method=ScoringMethod.SET_MATCH),
            )


class TestGoldModel:
    def test_gold_defaults(self):
        gold = Gold(required=["model_a"])
        assert gold.optional == []
        assert gold.forbidden == []

    def test_gold_empty_required_allowed(self):
        gold = Gold(required=[])
        assert gold.required == []


class TestMetricsModel:
    def test_valid_metrics(self):
        m = Metrics(
            tool_calls=3,
            search_calls=0,
            files_opened=1,
            tokens_input=2140,
            tokens_output=700,
            tokens_total=2840,
            wall_time_seconds=4.2,
            tool_breakdown={"check_impact": 1, "trace_column_lineage": 1},
        )
        assert m.tokens_total == 2840

    def test_metrics_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(
                tool_calls=-1,
                search_calls=0,
                files_opened=0,
                tokens_input=0,
                tokens_output=0,
                tokens_total=0,
                wall_time_seconds=0,
                tool_breakdown={},
            )


class TestResultModel:
    def test_valid_result(self):
        result = Result(
            task_id="jaffle-mesh_B1_01",
            agent="claude-sonnet-4-6",
            tools="sqlprism",
            timestamp="2026-04-03T14:30:00Z",
            answer={"entities": ["int_orders"], "explanation": "direct ref", "confidence": "high"},
            metrics=Metrics(
                tool_calls=3,
                search_calls=0,
                files_opened=1,
                tokens_input=2140,
                tokens_output=700,
                tokens_total=2840,
                wall_time_seconds=4.2,
                tool_breakdown={"check_impact": 1},
            ),
        )
        assert result.task_id == "jaffle-mesh_B1_01"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_models.py -v
```

Expected: ImportError — models module doesn't exist yet.

- [ ] **Step 3: Implement models.py**

```python
# src/sql_nav_bench/models.py
"""Pydantic data models for tasks, results, gold answers, and scoring."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Category(str, Enum):
    REFERENCE = "reference"
    IMPACT = "impact"
    LINEAGE = "lineage"
    MESH = "mesh"
    REINDEX = "reindex"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    BRUTAL = "brutal"


class ScoringMethod(str, Enum):
    SET_MATCH = "set_match"
    CONTAINS = "contains"
    ORDERED_LIST = "ordered_list"
    JUDGMENT = "judgment"


class Gold(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    method: ScoringMethod
    partial_credit: bool = False


class Task(BaseModel):
    id: str
    repo: str
    category: Category
    difficulty: Difficulty
    question: str
    tool_hint: str
    gold: Gold
    scoring: ScoringConfig
    notes: str = ""


class Metrics(BaseModel):
    tool_calls: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    files_opened: int = Field(ge=0)
    tokens_input: int = Field(ge=0)
    tokens_output: int = Field(ge=0)
    tokens_total: int = Field(ge=0)
    wall_time_seconds: float = Field(ge=0)
    tool_breakdown: dict[str, int] = Field(default_factory=dict)


class Result(BaseModel):
    task_id: str
    agent: str
    tools: str
    timestamp: str
    answer: dict[str, Any]
    metrics: Metrics


class RepoSource(BaseModel):
    url: str
    path: str
    sparse_checkout: str | None = None


class RepoConfig(BaseModel):
    type: str
    sources: list[RepoSource]
    pin: str = "main"
    difficulty: Difficulty
    description: str


class RepoManifest(BaseModel):
    repos: dict[str, RepoConfig]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_models.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/sql_nav_bench/models.py tests/test_models.py
git commit -m "feat: add pydantic data models for tasks, results, and scoring"
```

---

### Task 2: YAML loader

**Goal:** Load task YAML files and result YAML files into pydantic models, with validation and error reporting.

**Files:**
- Create: `src/sql_nav_bench/loader.py`
- Create: `tests/test_loader.py`
- Create: `tests/fixtures/` (test YAML files)

**Acceptance Criteria:**
- [ ] `load_task(path)` returns a validated Task
- [ ] `load_result(path)` returns a validated Result
- [ ] `load_tasks(directory)` returns all tasks from a repo directory
- [ ] `load_manifest(path)` returns a validated RepoManifest
- [ ] Invalid YAML raises clear errors with file path context
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_loader.py -v`

**Steps:**

- [ ] **Step 1: Create test fixture YAML files**

`tests/fixtures/valid_task.yml`:
```yaml
id: test_A1_01
repo: test-repo
category: reference
difficulty: easy
question: "Where is model_a used?"
tool_hint: find_references
gold:
  required:
    - model_b
    - model_c
  optional: []
  forbidden:
    - model_d
scoring:
  method: set_match
  partial_credit: true
notes: "Test task for loader validation"
```

`tests/fixtures/valid_result.yml`:
```yaml
task_id: test_A1_01
agent: test-agent
tools: baseline
timestamp: "2026-04-03T10:00:00Z"
answer:
  entities:
    - model_b
    - model_c
  explanation: "Found via grep"
  confidence: high
metrics:
  tool_calls: 5
  search_calls: 3
  files_opened: 2
  tokens_input: 1000
  tokens_output: 500
  tokens_total: 1500
  wall_time_seconds: 8.1
  tool_breakdown:
    grep: 3
    file_read: 2
```

`tests/fixtures/invalid_task.yml`:
```yaml
id: bad
repo: x
category: not_a_category
```

- [ ] **Step 2: Write tests**

```python
# tests/test_loader.py
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_loader.py -v
```

- [ ] **Step 4: Implement loader.py**

```python
# src/sql_nav_bench/loader.py
"""YAML file loaders for tasks, results, and repo manifests."""

from __future__ import annotations

from pathlib import Path

import yaml

from sql_nav_bench.models import RepoManifest, Result, Task


def load_task(path: Path) -> Task:
    """Load and validate a task YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return Task(**data)


def load_result(path: Path) -> Result:
    """Load and validate a result YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return Result(**data)


def load_tasks(directory: Path) -> list[Task]:
    """Load all task YAML files from a directory."""
    if not directory.exists():
        return []
    tasks = []
    for path in sorted(directory.glob("*.yml")):
        tasks.append(load_task(path))
    return tasks


def load_results(directory: Path) -> list[Result]:
    """Load all result YAML files from a directory."""
    if not directory.exists():
        return []
    results = []
    for path in sorted(directory.glob("*.yml")):
        results.append(load_result(path))
    return results


def load_manifest(path: Path) -> RepoManifest:
    """Load and validate the repos.yml manifest."""
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return RepoManifest(**data)
```

- [ ] **Step 5: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_loader.py -v
git add src/sql_nav_bench/loader.py tests/test_loader.py tests/fixtures/
git commit -m "feat: add YAML loader for tasks, results, and manifests"
```

---

### Task 3: Scorer — set_match and efficiency scoring

**Goal:** Implement the core scoring engine: precision/recall/F1 for set_match, efficiency normalization, and composite task scores.

**Files:**
- Create: `src/sql_nav_bench/scorer.py`
- Create: `tests/test_scorer.py`

**Acceptance Criteria:**
- [ ] `score_set_match(result, gold)` returns precision, recall, F1 accounting for required/optional/forbidden
- [ ] `score_efficiency(metrics_list)` returns normalized scores using min-max scaling
- [ ] `score_task(result, task)` returns composite correctness + efficiency score
- [ ] Forbidden entities in answer reduce precision
- [ ] Optional entities in answer increase recall without penalty if missing
- [ ] Single-run scoring works (no comparison needed)
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_scorer.py -v`

**Steps:**

- [ ] **Step 1: Write tests**

```python
# tests/test_scorer.py
"""Tests for scoring engine."""

import pytest

from sql_nav_bench.models import Gold, Metrics
from sql_nav_bench.scorer import ScoreResult, score_efficiency, score_set_match


class TestSetMatchScoring:
    def test_perfect_match(self):
        gold = Gold(required=["a", "b"], optional=[], forbidden=["x"])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_partial_recall(self):
        gold = Gold(required=["a", "b", "c"], optional=[], forbidden=[])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == pytest.approx(2 / 3)

    def test_false_positive_reduces_precision(self):
        gold = Gold(required=["a"], optional=[], forbidden=["x"])
        found = ["a", "x"]
        result = score_set_match(found, gold)
        assert result.precision == 0.5
        assert result.recall == 1.0

    def test_optional_boosts_recall(self):
        gold = Gold(required=["a"], optional=["b"], forbidden=[])
        found = ["a", "b"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_missing_optional_no_penalty(self):
        gold = Gold(required=["a"], optional=["b"], forbidden=[])
        found = ["a"]
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_empty_found_zero_recall(self):
        gold = Gold(required=["a", "b"], optional=[], forbidden=[])
        found: list[str] = []
        result = score_set_match(found, gold)
        assert result.recall == 0.0

    def test_empty_required_and_found(self):
        gold = Gold(required=[], optional=[], forbidden=[])
        found: list[str] = []
        result = score_set_match(found, gold)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_unknown_entity_not_forbidden(self):
        """Entity not in required/optional/forbidden — counts as false positive."""
        gold = Gold(required=["a"], optional=[], forbidden=[])
        found = ["a", "z"]
        result = score_set_match(found, gold)
        assert result.precision == 0.5
        assert result.recall == 1.0


class TestEfficiencyScoring:
    def test_single_run_scores_one(self):
        metrics = [
            Metrics(
                tool_calls=3, search_calls=0, files_opened=1,
                tokens_input=2000, tokens_output=800, tokens_total=2800,
                wall_time_seconds=4.0, tool_breakdown={},
            )
        ]
        scores = score_efficiency(metrics)
        assert len(scores) == 1
        assert scores[0] == 1.0  # single run is both best and worst

    def test_two_runs_best_worst(self):
        low = Metrics(
            tool_calls=3, search_calls=0, files_opened=1,
            tokens_input=2000, tokens_output=800, tokens_total=2800,
            wall_time_seconds=4.0, tool_breakdown={},
        )
        high = Metrics(
            tool_calls=22, search_calls=18, files_opened=14,
            tokens_input=40000, tokens_output=7200, tokens_total=47200,
            wall_time_seconds=45.0, tool_breakdown={},
        )
        scores = score_efficiency([low, high])
        assert scores[0] > scores[1]
        assert scores[0] == 1.0
        assert scores[1] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_scorer.py -v
```

- [ ] **Step 3: Implement scorer.py**

```python
# src/sql_nav_bench/scorer.py
"""Scoring engine for benchmark results."""

from __future__ import annotations

from dataclasses import dataclass

from sql_nav_bench.models import Gold, Metrics


@dataclass
class ScoreResult:
    precision: float
    recall: float
    f1: float


def score_set_match(found: list[str], gold: Gold) -> ScoreResult:
    """Score a set of found entities against gold standard.

    - Required entities in found: true positives for recall
    - Optional entities in found: true positives (no penalty if missing)
    - Forbidden entities in found: false positives
    - Unknown entities (not in any gold list): false positives
    """
    found_set = set(found)
    required_set = set(gold.required)
    optional_set = set(gold.optional)
    forbidden_set = set(gold.forbidden)
    valid_set = required_set | optional_set

    if not found_set and not required_set:
        return ScoreResult(precision=1.0, recall=1.0, f1=1.0)

    # True positives: found entities that are required or optional
    true_positives = found_set & valid_set
    # False positives: found entities that are forbidden or unknown
    false_positives = found_set - valid_set

    # Precision: of what we found, how many are valid?
    if found_set:
        precision = len(true_positives) / len(found_set)
    else:
        precision = 0.0

    # Recall: of required entities, how many did we find?
    if required_set:
        recall = len(found_set & required_set) / len(required_set)
    else:
        recall = 1.0  # nothing required, perfect recall

    # F1
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return ScoreResult(precision=precision, recall=recall, f1=f1)


# Efficiency weights from spec
_WEIGHTS = {
    "tokens_total": 0.40,
    "tool_calls": 0.25,
    "search_calls": 0.20,
    "files_opened": 0.15,
}


def score_efficiency(metrics_list: list[Metrics]) -> list[float]:
    """Compute normalized efficiency scores for a list of metrics.

    Uses min-max scaling: best value = 1.0, worst = 0.0.
    Lower is better for all metrics (fewer tokens/calls = higher score).
    Single run scores 1.0 (both best and worst).
    """
    if len(metrics_list) == 1:
        return [1.0]

    scores = []
    for metrics in metrics_list:
        weighted = 0.0
        for field, weight in _WEIGHTS.items():
            values = [getattr(m, field) for m in metrics_list]
            min_val = min(values)
            max_val = max(values)
            val = getattr(metrics, field)
            if max_val == min_val:
                normalized = 1.0
            else:
                # Lower is better, so invert: best (min) = 1.0, worst (max) = 0.0
                normalized = 1.0 - (val - min_val) / (max_val - min_val)
            weighted += normalized * weight
        scores.append(weighted)

    return scores
```

- [ ] **Step 4: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_scorer.py -v
git add src/sql_nav_bench/scorer.py tests/test_scorer.py
git commit -m "feat: add scoring engine with set_match and efficiency normalization"
```

---

### Task 4: Report generator

**Goal:** Generate markdown comparison tables and JSON summaries from scored results.

**Files:**
- Create: `src/sql_nav_bench/report.py`
- Create: `tests/test_report.py`

**Acceptance Criteria:**
- [ ] `generate_comparison(run_a, run_b)` produces a markdown table with median metrics and F1
- [ ] `generate_summary(results, tasks)` produces a JSON summary per task with scores
- [ ] Comparison table shows token reduction percentage
- [ ] Output matches the format from the spec
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_report.py -v`

**Steps:**

- [ ] **Step 1: Write tests**

```python
# tests/test_report.py
"""Tests for report generation."""

from sql_nav_bench.models import Metrics, Result
from sql_nav_bench.report import generate_comparison, generate_summary


def _make_result(task_id: str, tools: str, tokens: int, tool_calls: int, entities: list[str]) -> Result:
    return Result(
        task_id=task_id,
        agent="test-agent",
        tools=tools,
        timestamp="2026-04-03T10:00:00Z",
        answer={"entities": entities, "explanation": "test", "confidence": "high"},
        metrics=Metrics(
            tool_calls=tool_calls,
            search_calls=tool_calls - 1 if tools == "baseline" else 0,
            files_opened=tool_calls,
            tokens_input=tokens // 2,
            tokens_output=tokens // 2,
            tokens_total=tokens,
            wall_time_seconds=float(tool_calls),
            tool_breakdown={},
        ),
    )


class TestGenerateComparison:
    def test_comparison_table_structure(self):
        run_a = [_make_result("t1", "baseline", 47200, 22, ["a"])]
        run_b = [_make_result("t1", "sqlprism", 2840, 3, ["a", "b"])]
        table = generate_comparison(run_a, run_b, "baseline", "sqlprism")
        assert "baseline" in table
        assert "sqlprism" in table
        assert "Tokens" in table

    def test_comparison_shows_both_runs(self):
        run_a = [_make_result("t1", "baseline", 10000, 10, ["a"])]
        run_b = [_make_result("t1", "sqlprism", 1000, 2, ["a"])]
        table = generate_comparison(run_a, run_b, "baseline", "sqlprism")
        assert "10000" in table or "10,000" in table
        assert "1000" in table or "1,000" in table


class TestGenerateSummary:
    def test_summary_json_structure(self):
        results = [_make_result("t1", "sqlprism", 2840, 3, ["a", "b"])]
        summary = generate_summary(results)
        assert len(summary) == 1
        assert summary[0]["task_id"] == "t1"
        assert "metrics" in summary[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_report.py -v
```

- [ ] **Step 3: Implement report.py**

```python
# src/sql_nav_bench/report.py
"""Report generation — markdown tables and JSON summaries."""

from __future__ import annotations

import statistics
from typing import Any

from sql_nav_bench.models import Result


def generate_comparison(
    run_a: list[Result],
    run_b: list[Result],
    label_a: str,
    label_b: str,
) -> str:
    """Generate a markdown comparison table from two runs."""

    def _medians(results: list[Result]) -> dict[str, float]:
        if not results:
            return {}
        return {
            "tokens_total": statistics.median([r.metrics.tokens_total for r in results]),
            "tool_calls": statistics.median([r.metrics.tool_calls for r in results]),
            "search_calls": statistics.median([r.metrics.search_calls for r in results]),
            "files_opened": statistics.median([r.metrics.files_opened for r in results]),
            "wall_time_seconds": statistics.median([r.metrics.wall_time_seconds for r in results]),
        }

    ma = _medians(run_a)
    mb = _medians(run_b)

    rows = [
        ("Tokens (median)", "tokens_total", True),
        ("Tool calls", "tool_calls", False),
        ("Search calls", "search_calls", False),
        ("Files opened", "files_opened", False),
        ("Wall time (s)", "wall_time_seconds", False),
    ]

    lines = [
        f"| {'Metric':<20} | {label_a:>12} | {label_b:>12} |",
        f"|{'-' * 22}|{'-' * 14}|{'-' * 14}|",
    ]

    for label, key, is_headline in rows:
        va = ma.get(key, 0)
        vb = mb.get(key, 0)
        if isinstance(va, float) and va == int(va):
            sa = str(int(va))
        else:
            sa = f"{va:.1f}" if isinstance(va, float) else str(va)
        if isinstance(vb, float) and vb == int(vb):
            sb = str(int(vb))
        else:
            sb = f"{vb:.1f}" if isinstance(vb, float) else str(vb)
        suffix = ""
        if is_headline and va > 0 and vb < va:
            pct = (1 - vb / va) * 100
            suffix = f"  <- {pct:.0f}% reduction"
        lines.append(f"| {label:<20} | {sa:>12} | {sb:>12} |{suffix}")

    return "\n".join(lines)


def generate_summary(results: list[Result]) -> list[dict[str, Any]]:
    """Generate a JSON-serializable summary of results."""
    return [
        {
            "task_id": r.task_id,
            "agent": r.agent,
            "tools": r.tools,
            "metrics": {
                "tokens_total": r.metrics.tokens_total,
                "tool_calls": r.metrics.tool_calls,
                "search_calls": r.metrics.search_calls,
                "files_opened": r.metrics.files_opened,
                "wall_time_seconds": r.metrics.wall_time_seconds,
            },
            "answer_entities": r.answer.get("entities", []),
        }
        for r in results
    ]
```

- [ ] **Step 4: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_report.py -v
git add src/sql_nav_bench/report.py tests/test_report.py
git commit -m "feat: add report generator with comparison tables and JSON summaries"
```

---

### Task 5: Repo setup command

**Goal:** Implement `sql-nav-bench setup` to clone benchmark repos per the manifest, with sparse checkout and pin support.

**Files:**
- Create: `src/sql_nav_bench/setup.py`
- Modify: `src/sql_nav_bench/cli.py` (wire up setup command)
- Create: `tests/test_setup.py`

**Acceptance Criteria:**
- [ ] `clone_repo(repo_config, target_dir)` clones sources per manifest
- [ ] Sparse checkout works for sqlmesh-examples and cal-itp
- [ ] Multi-source repos (jaffle-mesh) clone each source into subdirectories
- [ ] `--repo` flag clones only one repo
- [ ] Re-running setup updates existing clones (git pull)
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_setup.py -v`

**Steps:**

- [ ] **Step 1: Write tests**

```python
# tests/test_setup.py
"""Tests for repo setup/cloning."""

from pathlib import Path
from unittest.mock import patch, call

from sql_nav_bench.models import Difficulty, RepoConfig, RepoSource
from sql_nav_bench.setup import build_clone_commands


class TestBuildCloneCommands:
    def test_simple_clone(self):
        config = RepoConfig(
            type="sql",
            sources=[RepoSource(url="https://github.com/org/repo", path=".")],
            pin="main",
            difficulty=Difficulty.MEDIUM,
            description="test",
        )
        cmds = build_clone_commands(config, "test-repo", Path("/tmp/repos"))
        assert len(cmds) == 1
        assert "git clone" in cmds[0]
        assert "https://github.com/org/repo" in cmds[0]

    def test_multi_source_clone(self):
        config = RepoConfig(
            type="dbt",
            sources=[
                RepoSource(url="https://github.com/org/a", path="platform/"),
                RepoSource(url="https://github.com/org/b", path="finance/"),
            ],
            pin="main",
            difficulty=Difficulty.MEDIUM,
            description="test",
        )
        cmds = build_clone_commands(config, "mesh", Path("/tmp/repos"))
        assert len(cmds) == 2
        assert "platform" in cmds[0]
        assert "finance" in cmds[1]

    def test_sparse_checkout(self):
        config = RepoConfig(
            type="sqlmesh",
            sources=[
                RepoSource(
                    url="https://github.com/org/repo",
                    path="examples/",
                    sparse_checkout="examples/",
                )
            ],
            pin="main",
            difficulty=Difficulty.MEDIUM,
            description="test",
        )
        cmds = build_clone_commands(config, "sm", Path("/tmp/repos"))
        assert len(cmds) == 1
        assert "sparse-checkout" in cmds[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_setup.py -v
```

- [ ] **Step 3: Implement setup.py**

```python
# src/sql_nav_bench/setup.py
"""Clone and manage benchmark repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

from sql_nav_bench.loader import load_manifest
from sql_nav_bench.models import RepoConfig


def build_clone_commands(config: RepoConfig, repo_name: str, base_dir: Path) -> list[str]:
    """Build git clone commands for a repo config."""
    commands = []
    for source in config.sources:
        target = base_dir / repo_name / source.path.rstrip("/")
        if source.sparse_checkout:
            cmd = (
                f"git clone --filter=blob:none --sparse "
                f"--branch {config.pin} "
                f"{source.url} {target} && "
                f"cd {target} && "
                f"git sparse-checkout set {source.sparse_checkout}"
            )
        else:
            cmd = (
                f"git clone --branch {config.pin} "
                f"{source.url} {target}"
            )
        commands.append(cmd)
    return commands


def setup_repos(manifest_path: Path, repos_dir: Path, repo_filter: str | None = None) -> None:
    """Clone benchmark repos per manifest."""
    manifest = load_manifest(manifest_path)
    repos_dir.mkdir(parents=True, exist_ok=True)

    for name, config in manifest.repos.items():
        if repo_filter and name != repo_filter:
            continue

        click.echo(f"Setting up {name}...")
        commands = build_clone_commands(config, name, repos_dir)

        for cmd in commands:
            target_check = repos_dir / name
            if target_check.exists():
                click.echo(f"  {name} already exists, pulling latest...")
                subprocess.run(
                    ["git", "pull"],
                    cwd=target_check,
                    check=True,
                    capture_output=True,
                )
                continue

            click.echo(f"  Cloning...")
            subprocess.run(cmd, shell=True, check=True)

        click.echo(f"  Done: {name}")
```

- [ ] **Step 4: Wire up CLI setup command**

Update `src/sql_nav_bench/cli.py` setup command:

```python
@main.command()
@click.option("--repo", help="Clone a specific repo only")
def setup(repo: str | None) -> None:
    """Clone benchmark repos."""
    from sql_nav_bench.setup import setup_repos

    manifest_path = Path("repos.yml")
    repos_dir = Path("repos")
    setup_repos(manifest_path, repos_dir, repo_filter=repo)
```

Add `from pathlib import Path` to cli.py imports.

- [ ] **Step 5: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_setup.py -v
git add src/sql_nav_bench/setup.py src/sql_nav_bench/cli.py tests/test_setup.py
git commit -m "feat: add repo setup command with sparse checkout support"
```

---

### Task 6: Wire CLI commands to implementations

**Goal:** Connect all CLI commands (tasks, score, compare, validate) to the loader, scorer, and report modules.

**Files:**
- Modify: `src/sql_nav_bench/cli.py`
- Create: `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `sql-nav-bench tasks` lists tasks from tasks/ directory with repo/category filters
- [ ] `sql-nav-bench score --results <dir>` loads results, matches to tasks, computes scores
- [ ] `sql-nav-bench compare --a <dir> --b <dir>` generates comparison table
- [ ] `sql-nav-bench validate` checks all task YAML files for schema validity
- [ ] All commands exit cleanly with appropriate output
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_cli.py -v`

**Steps:**

- [ ] **Step 1: Write tests using click.testing.CliRunner**

```python
# tests/test_cli.py
"""Tests for CLI commands."""

from pathlib import Path

from click.testing import CliRunner

from sql_nav_bench.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestTasksCommand:
    def test_tasks_no_tasks_directory(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(main, ["tasks"], catch_exceptions=False)
        assert result.exit_code == 0

    def test_tasks_with_fixture(self, tmp_path: Path, monkeypatch: object):
        # Create a task file in expected location
        task_dir = tmp_path / "tasks" / "test-repo"
        task_dir.mkdir(parents=True)
        (task_dir / "A1_test.yml").write_text(
            (FIXTURES / "valid_task.yml").read_text()
        )
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Symlink tasks dir
            Path("tasks").symlink_to(tmp_path / "tasks")
            result = runner.invoke(main, ["tasks"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "test_A1_01" in result.output


class TestValidateCommand:
    def test_validate_no_tasks(self):
        runner = CliRunner()
        result = runner.invoke(main, ["validate"], catch_exceptions=False)
        assert result.exit_code == 0


class TestScoreCommand:
    def test_score_with_results(self, tmp_path: Path):
        # Create minimal result file
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        (results_dir / "t1.yml").write_text(
            (FIXTURES / "valid_result.yml").read_text()
        )
        # Create matching task
        tasks_dir = tmp_path / "tasks" / "test-repo"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "A1_test.yml").write_text(
            (FIXTURES / "valid_task.yml").read_text()
        )
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("tasks").symlink_to(tasks_dir.parent)
            result = runner.invoke(
                main, ["score", "--results", str(results_dir)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_cli.py -v
```

- [ ] **Step 3: Implement full CLI**

```python
# src/sql_nav_bench/cli.py
"""CLI entry point for sql-nav-bench."""

from pathlib import Path

import click

from sql_nav_bench import __version__


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """sql-nav-bench: Benchmark for agent SQL project understanding."""


@main.command()
@click.option("--repo", help="Clone a specific repo only")
def setup(repo: str | None) -> None:
    """Clone benchmark repos."""
    from sql_nav_bench.setup import setup_repos

    manifest_path = Path("repos.yml")
    repos_dir = Path("repos")
    setup_repos(manifest_path, repos_dir, repo_filter=repo)


@main.command()
@click.option("--repo", help="Filter by repo")
@click.option("--category", help="Filter by category")
def tasks(repo: str | None, category: str | None) -> None:
    """List available benchmark tasks."""
    from sql_nav_bench.loader import load_tasks

    tasks_dir = Path("tasks")
    if not tasks_dir.exists():
        click.echo("No tasks directory found.")
        return

    all_tasks = []
    for repo_dir in sorted(tasks_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        if repo and repo_dir.name != repo:
            continue
        all_tasks.extend(load_tasks(repo_dir))

    if category:
        all_tasks = [t for t in all_tasks if t.category.value == category]

    if not all_tasks:
        click.echo("No tasks found.")
        return

    click.echo(f"{'ID':<35} {'Repo':<20} {'Category':<12} {'Difficulty':<10}")
    click.echo("-" * 77)
    for t in all_tasks:
        click.echo(f"{t.id:<35} {t.repo:<20} {t.category.value:<12} {t.difficulty.value:<10}")

    click.echo(f"\n{len(all_tasks)} tasks total")


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results directory")
@click.option("--repo", help="Filter by repo")
def score(results: str, repo: str | None) -> None:
    """Score results against gold answers."""
    from sql_nav_bench.loader import load_results, load_tasks
    from sql_nav_bench.scorer import score_set_match

    results_list = load_results(Path(results))
    if not results_list:
        click.echo("No result files found.")
        return

    # Load all tasks to match against
    tasks_dir = Path("tasks")
    task_map: dict[str, object] = {}
    if tasks_dir.exists():
        for repo_dir in sorted(tasks_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            if repo and repo_dir.name != repo:
                continue
            for t in load_tasks(repo_dir):
                task_map[t.id] = t

    click.echo(f"{'Task ID':<35} {'P':>6} {'R':>6} {'F1':>6} {'Tokens':>8} {'Calls':>6}")
    click.echo("-" * 67)

    for r in results_list:
        task = task_map.get(r.task_id)
        entities = r.answer.get("entities", [])
        if task:
            sr = score_set_match(entities, task.gold)
            click.echo(
                f"{r.task_id:<35} {sr.precision:>6.2f} {sr.recall:>6.2f} {sr.f1:>6.2f} "
                f"{r.metrics.tokens_total:>8} {r.metrics.tool_calls:>6}"
            )
        else:
            click.echo(f"{r.task_id:<35} {'(no matching task)':>30}")

    click.echo(f"\n{len(results_list)} results scored")


@main.command()
@click.option("--a", "run_a", required=True, type=click.Path(exists=True), help="First results directory")
@click.option("--b", "run_b", required=True, type=click.Path(exists=True), help="Second results directory")
def compare(run_a: str, run_b: str) -> None:
    """Compare two benchmark runs side-by-side."""
    from sql_nav_bench.loader import load_results
    from sql_nav_bench.report import generate_comparison

    results_a = load_results(Path(run_a))
    results_b = load_results(Path(run_b))

    if not results_a or not results_b:
        click.echo("Both result directories must contain result files.")
        return

    label_a = results_a[0].tools if results_a else "run-a"
    label_b = results_b[0].tools if results_b else "run-b"

    table = generate_comparison(results_a, results_b, label_a, label_b)
    click.echo(table)


@main.command()
def validate() -> None:
    """Validate task and result files."""
    from pydantic import ValidationError

    from sql_nav_bench.loader import load_task

    tasks_dir = Path("tasks")
    if not tasks_dir.exists():
        click.echo("No tasks directory found. Nothing to validate.")
        return

    errors = 0
    total = 0
    for yml in sorted(tasks_dir.rglob("*.yml")):
        total += 1
        try:
            load_task(yml)
            click.echo(f"  OK: {yml}")
        except (ValidationError, Exception) as e:
            errors += 1
            click.echo(f"  FAIL: {yml} — {e}")

    click.echo(f"\n{total} files checked, {errors} errors")
```

- [ ] **Step 4: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_cli.py -v
git add src/sql_nav_bench/cli.py tests/test_cli.py
git commit -m "feat: wire CLI commands to loader, scorer, and report modules"
```

---

### Task 7: Jaffle-mesh gold set — task YAML files

**Goal:** Create the first complete set of benchmark tasks for the jaffle-mesh trio with manually verified gold answers.

**Files:**
- Create: `tasks/jaffle-mesh/A1_model_usage.yml`
- Create: `tasks/jaffle-mesh/A2_file_dependencies.yml`
- Create: `tasks/jaffle-mesh/B1_model_change_impact.yml`
- Create: `tasks/jaffle-mesh/B2_column_change_impact.yml`
- Create: `tasks/jaffle-mesh/C1_table_lineage.yml`
- Create: `tasks/jaffle-mesh/C2_column_lineage.yml`
- Create: `tasks/jaffle-mesh/D1_cross_project_consumer.yml`
- Create: `tasks/jaffle-mesh/D2_cross_project_impact.yml`
- Create: `tasks/jaffle-mesh/D3_contract_column_impact.yml`
- Create: `tasks/jaffle-mesh/E1_single_file_reindex.yml`

**Acceptance Criteria:**
- [ ] 10 task files covering all 5 categories (A, B, C, D, E)
- [ ] All gold answers manually verified against actual repo source files
- [ ] `sql-nav-bench validate` passes on all files
- [ ] Cross-project tasks (D) test the mesh trio's inter-project dependencies
- [ ] Each task has clear notes documenting any ambiguity
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run sql-nav-bench validate`

**Steps:**

- [ ] **Step 1: Clone jaffle-mesh repos to inspect source**

```bash
cd /home/alfred/code/sql-nav-bench
sql-nav-bench setup --repo jaffle-mesh
```

- [ ] **Step 2: Inspect all model files in the mesh trio**

Read every SQL file in platform/, finance/, marketing/ to understand the exact dependency graph, column usage, and cross-project refs. Document the full dependency graph before writing tasks.

- [ ] **Step 3: Create task YAML files**

Create each of the 10 task files listed above. For each task:
1. Write the question
2. Manually trace the answer through the source files
3. Record required/optional/forbidden entities
4. Add notes for any ambiguity

Example (B2 — column impact):
```yaml
id: jaffle-mesh_B2_01
repo: jaffle-mesh
category: impact
difficulty: medium
question: |
  If I remove the column `customer_id` from `stg_orders` in the
  platform project, what downstream models across all projects break?
tool_hint: column_impact
gold:
  required: []   # filled after manual inspection
  optional: []
  forbidden: []
scoring:
  method: set_match
  partial_credit: true
notes: |
  Must inspect actual SQL files to determine gold answer.
  Cross-project refs via dependencies.yml.
```

**IMPORTANT:** Gold answers MUST be filled with actual entities after inspecting the source files. Do not leave them empty or use placeholder values.

- [ ] **Step 4: Validate all task files**

```bash
cd /home/alfred/code/sql-nav-bench && uv run sql-nav-bench validate
```

- [ ] **Step 5: Commit**

```bash
git add tasks/jaffle-mesh/
git commit -m "feat: add jaffle-mesh benchmark task set with gold answers"
```

---

### Task 8: Remaining repo task sets

**Goal:** Create benchmark tasks for sqlmesh-examples, mozilla-bigquery, and cal-itp repos.

**Files:**
- Create: `tasks/sqlmesh-examples/*.yml` (~10 tasks)
- Create: `tasks/mozilla-bigquery/*.yml` (~10 tasks)
- Create: `tasks/cal-itp/*.yml` (~10 tasks)

**Acceptance Criteria:**
- [ ] ~10 tasks per repo covering relevant categories
- [ ] All gold answers manually verified against actual repo source files
- [ ] sqlmesh-examples tasks include multi-project (D) tasks using multi/ and multi_hybrid/
- [ ] mozilla-bigquery tasks stress raw SQL parsing (no ref/source, direct table refs)
- [ ] cal-itp tasks include dbt-specific patterns (incremental, macros)
- [ ] `sql-nav-bench validate` passes on all files
- [ ] Total task count: ~40 across all 4 repos

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run sql-nav-bench validate && uv run sql-nav-bench tasks`

**Steps:**

- [ ] **Step 1: Clone remaining repos**

```bash
cd /home/alfred/code/sql-nav-bench
sql-nav-bench setup --repo sqlmesh-examples
sql-nav-bench setup --repo mozilla-bigquery
sql-nav-bench setup --repo cal-itp
```

- [ ] **Step 2: For each repo, inspect source files and create tasks**

For each repo:
1. Read model files to understand dependency graph
2. Identify interesting lineage chains, impact scenarios, column usage
3. Create ~10 task YAML files with manually verified gold answers
4. Run `sql-nav-bench validate` after each repo

- [ ] **Step 3: Validate and commit per repo**

```bash
uv run sql-nav-bench validate
git add tasks/sqlmesh-examples/ tasks/mozilla-bigquery/ tasks/cal-itp/
git commit -m "feat: add benchmark tasks for sqlmesh, mozilla, and cal-itp repos"
```

---

### Task 9: End-to-end integration test

**Goal:** Verify the full workflow: load tasks, load results, score, compare, report.

**Files:**
- Create: `tests/test_integration.py`
- Create: `tests/fixtures/results_baseline/` (mock baseline results)
- Create: `tests/fixtures/results_sqlprism/` (mock sqlprism results)

**Acceptance Criteria:**
- [ ] Full pipeline: load tasks -> load results -> score -> compare -> report
- [ ] Comparison table correctly shows efficiency differences
- [ ] F1 scores correctly computed for set_match tasks
- [ ] CLI commands work end-to-end with fixture data
- [ ] All tests pass

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_integration.py -v`

**Steps:**

- [ ] **Step 1: Create mock result fixtures**

Create result YAML files for both baseline and sqlprism runs of the same task, with different metrics to verify comparison works.

`tests/fixtures/results_baseline/test_A1_01.yml`:
```yaml
task_id: test_A1_01
agent: claude-sonnet-4-6
tools: baseline
timestamp: "2026-04-03T10:00:00Z"
answer:
  entities:
    - model_b
  explanation: "Found model_b via grep but missed model_c"
  confidence: medium
metrics:
  tool_calls: 15
  search_calls: 12
  files_opened: 8
  tokens_input: 20000
  tokens_output: 5000
  tokens_total: 25000
  wall_time_seconds: 30.0
  tool_breakdown:
    grep: 12
    file_read: 3
```

`tests/fixtures/results_sqlprism/test_A1_01.yml`:
```yaml
task_id: test_A1_01
agent: claude-sonnet-4-6
tools: sqlprism
timestamp: "2026-04-03T10:05:00Z"
answer:
  entities:
    - model_b
    - model_c
  explanation: "Found via find_references tool"
  confidence: high
metrics:
  tool_calls: 2
  search_calls: 0
  files_opened: 0
  tokens_input: 1500
  tokens_output: 400
  tokens_total: 1900
  wall_time_seconds: 3.0
  tool_breakdown:
    find_references: 1
    get_context: 1
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_integration.py
"""End-to-end integration tests."""

from pathlib import Path

from click.testing import CliRunner

from sql_nav_bench.cli import main
from sql_nav_bench.loader import load_results, load_task
from sql_nav_bench.report import generate_comparison
from sql_nav_bench.scorer import score_set_match

FIXTURES = Path(__file__).parent / "fixtures"


class TestEndToEnd:
    def test_score_baseline_vs_sqlprism(self):
        task = load_task(FIXTURES / "valid_task.yml")
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        assert len(baseline) == 1
        assert len(sqlprism) == 1

        # Baseline found 1 of 2 required
        bs = score_set_match(baseline[0].answer["entities"], task.gold)
        assert bs.recall < 1.0

        # SQLPrism found 2 of 2 required
        ss = score_set_match(sqlprism[0].answer["entities"], task.gold)
        assert ss.recall == 1.0
        assert ss.f1 > bs.f1

    def test_token_comparison(self):
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        assert baseline[0].metrics.tokens_total > sqlprism[0].metrics.tokens_total
        assert baseline[0].metrics.tool_calls > sqlprism[0].metrics.tool_calls

    def test_comparison_table(self):
        baseline = load_results(FIXTURES / "results_baseline")
        sqlprism = load_results(FIXTURES / "results_sqlprism")

        table = generate_comparison(baseline, sqlprism, "baseline", "sqlprism")
        assert "baseline" in table
        assert "sqlprism" in table
        assert "reduction" in table.lower()

    def test_cli_compare(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "compare",
                "--a", str(FIXTURES / "results_baseline"),
                "--b", str(FIXTURES / "results_sqlprism"),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "baseline" in result.output
        assert "sqlprism" in result.output
```

- [ ] **Step 3: Run tests, then commit**

```bash
cd /home/alfred/code/sql-nav-bench && uv run pytest tests/test_integration.py -v
git add tests/test_integration.py tests/fixtures/results_baseline/ tests/fixtures/results_sqlprism/
git commit -m "test: add end-to-end integration tests with mock results"
```

---

### Task 10: Lint, final validation, and README

**Goal:** Ensure code quality, write proper README, and prepare for v0.1.0 release.

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml` (add dev dependencies)

**Acceptance Criteria:**
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest tests/ -v` all pass
- [ ] README documents: purpose, quick start, task format, scoring, how to contribute results
- [ ] All CLI commands work as documented
- [ ] `sql-nav-bench validate` passes on all task files

**Verify:** `cd /home/alfred/code/sql-nav-bench && uv run ruff check . && uv run pytest tests/ -v && uv run sql-nav-bench validate`

**Steps:**

- [ ] **Step 1: Add dev dependencies to pyproject.toml**

Add to pyproject.toml:
```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.4.0",
]
```

- [ ] **Step 2: Run ruff, fix any issues**

```bash
cd /home/alfred/code/sql-nav-bench && uv run ruff check . --fix
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 4: Update README.md**

Write full README with:
- Purpose and positioning (not a SQL generation benchmark)
- Quick start (setup, run tasks, score, compare)
- Task format documentation
- Scoring methodology
- How to contribute tasks and results
- Supported repos

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "chore: lint, full test suite, README for v0.1.0"
```
