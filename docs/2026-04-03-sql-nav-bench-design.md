# sql-nav-bench Design Spec

**Date**: 2026-04-03
**Status**: Draft
**Version**: 0.1.0

## Purpose

sql-nav-bench is an open-source benchmark for evaluating how well agents understand SQL project structure. It measures performance on structural reasoning tasks — lineage tracing, impact analysis, dependency discovery, cross-project navigation — not SQL query generation.

No existing benchmark covers this category. Spider, BIRD, and similar benchmarks test "write SQL from natural language." sql-nav-bench tests "understand a SQL codebase well enough to answer structural questions about it."

## Core Thesis

An agent equipped with structural SQL tools (like an MCP server providing lineage/impact/dependency queries) can answer SQL project understanding tasks using fewer tool calls, fewer tokens, and equal or better correctness than an agent using only text search and file inspection.

## What It Is

- A set of task definitions (YAML) with ground-truth answer keys
- A scorer that compares any agent's output against gold answers
- A CLI for setup, scoring, and comparison
- Vendor-agnostic — works with any LLM provider (Claude, Codex, Ollama, etc.)

## What It Is Not

- Not an agent runner — users bring their own agent
- Not an LLM SDK wrapper — no provider adapters
- Not a SQL parser benchmark — tests project understanding, not parsing
- Not tied to any specific tool — SQLPrism is one tool that can be evaluated

---

## Benchmark Repos

Four repos across three difficulty tiers.

### Tier 1: Medium — dbt Mesh

**Jaffle Shop Mesh Trio**
- `dbt-labs/jaffle-shop-mesh-platform` (6 models)
- `dbt-labs/jaffle-shop-mesh-finance` (4 models)
- `dbt-labs/jaffle-shop-mesh-marketing` (2 models)
- 12 models total, cross-project dependencies, contracts, groups, access controls
- Marketing depends on both platform and finance — multi-hop cross-project lineage

### Tier 1: Medium — SQLMesh

**TobikoData/sqlmesh `examples/` directory**
- ~57 SQL models across 7 sub-projects
- `multi/` — true multi-repo (repo_1 + repo_2)
- `multi_hybrid/` — dbt + sqlmesh hybrid
- `sushi` — canonical 18-model project
- Actively maintained, updated daily

### Tier 2: Brutal — Raw SQL

**mozilla/bigquery-etl**
- 2,346 SQL files, BigQuery dialect
- Raw SQL (no dbt) — direct table references, no `ref()`/`source()`
- Deep nesting (8 levels), UDFs, Jinja templates (small fraction)
- MPL-2.0 license, actively maintained

### Tier 2: Brutal — dbt

**cal-itp/data-infra `warehouse/`**
- 630 dbt models with clean staging/intermediate/mart layers
- Light Jinja (~5-10%), standard dbt patterns
- Uses dbt_utils, custom macros, incremental/microbatch strategies
- AGPL-3.0 license, actively maintained

---

## Task Format

Each task is a YAML file defining a question, expected tool approach, and ground truth.

```yaml
id: jaffle-mesh_B1_01
repo: jaffle-mesh
category: impact            # impact | lineage | reference | mesh | reindex
difficulty: medium           # easy | medium | brutal

question: |
  If I remove the column `customer_id` from `stg_orders`,
  what downstream models break?

tool_hint: column_impact

gold:
  required:                  # must find — missing = recall penalty
    - int_orders
    - fct_orders
  optional:                  # credit if found, no penalty if missed
    - mart_customer_orders
  forbidden:                 # finding these = precision penalty
    - stg_customers
    - stg_products

scoring:
  method: set_match          # set_match | contains | ordered_list | judgment
  partial_credit: true

notes: |
  Wildcard SELECT * in int_orders creates ambiguity.
  Accept answer if tool flags uncertainty.
```

### Task Categories

| Category | ID Prefix | What It Tests |
|----------|-----------|---------------|
| Reference discovery | A | Where is X used? What depends on X? |
| Downstream impact | B | If X changes, what breaks? (model + column level) |
| Lineage tracing | C | What feeds X? Where does column Y come from? |
| Mesh / cross-project | D | Cross-project consumers, boundary impact |
| Reindex / edit loop | E | Post-change correctness, incremental update |

### Scoring Methods

| Method | Use Case | Mechanism |
|--------|----------|-----------|
| `set_match` | Impact, references, lineage endpoints | P/R/F1 against required/optional/forbidden sets |
| `contains` | Column tracing with free-text | Gold substrings must appear in answer |
| `ordered_list` | Lineage chains (A -> B -> C) | Order-aware comparison |
| `judgment` | Explanation quality, confidence | LLM-as-judge or human rating 1-5 |

---

## Repo Manifest

Repos are defined in `repos.yml`:

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

---

## Result Format

Agents produce result files in a standardized YAML format:

```yaml
task_id: jaffle-mesh_B1_01
agent: claude-sonnet-4-6
tools: sqlprism
timestamp: 2026-04-03T14:30:00Z

answer:
  entities:
    - int_orders
    - fct_orders
    - mart_customer_orders
  explanation: |
    stg_orders.customer_id is referenced directly in int_orders
    via SELECT customer_id, and transitively in fct_orders via
    ref('int_orders'). mart_customer_orders joins on this column.
  confidence: high
  caveats:
    - "int_orders uses SELECT * — implicit dependency"

metrics:
  tool_calls: 3
  search_calls: 0
  files_opened: 1
  tokens_input: 2140
  tokens_output: 700
  tokens_total: 2840
  wall_time_seconds: 4.2
  tool_breakdown:
    check_impact: 1
    trace_column_lineage: 1
    get_context: 1
```

### Required Metrics

All metrics fields are required for a valid result:

- `tool_calls` — total tool invocations
- `search_calls` — grep/glob/code-search calls specifically
- `files_opened` — number of files read
- `tokens_input` — prompt/context tokens
- `tokens_output` — completion tokens
- `tokens_total` — total tokens consumed
- `wall_time_seconds` — wall-clock time from task start to answer
- `tool_breakdown` — map of tool name to call count

---

## Scoring

### Per-Task Score

```
efficiency = normalize(
    tokens_total     x 0.40
    tool_calls       x 0.25
    search_calls     x 0.20
    files_opened     x 0.15
)

correctness = F1 x 0.60 + completeness x 0.20 + calibration x 0.20

task_score  = correctness x 0.50 + efficiency x 0.50
```

Normalization uses min-max scaling across all runs being compared. For each metric, the best value scores 1.0 and worst scores 0.0. This makes scores relative to the comparison set, not absolute.

Tokens are weighted highest in efficiency (40%) because token reduction is the primary value proposition of structural SQL tools.

### Aggregate Reporting

The scorer produces a comparison table:

```
+-------------------+----------+----------+
| Metric            | Baseline | SQLPrism |
+-------------------+----------+----------+
| Tokens (median)   | 47,200   | 2,840   |  <- headline
| Tool calls        | 22       | 3       |
| Search calls      | 18       | 0       |
| Files opened      | 14       | 1       |
| F1                | 0.58     | 0.89    |
+-------------------+----------+----------+
```

---

## Project Structure

```
sql-nav-bench/
  pyproject.toml              # uv project, cli entrypoint
  README.md
  LICENSE                     # Apache-2.0
  repos.yml                   # repo manifest

  tasks/                      # task definitions
    jaffle-mesh/
    sqlmesh-examples/
    mozilla-bigquery/
    cal-itp/

  tools/                      # tool set configs
    sqlprism.yml              # MCP server config
    baseline.yml              # grep + file read only

  src/sql_nav_bench/
    __init__.py
    cli.py                    # click CLI
    setup.py                  # clone repos per manifest
    scorer.py                 # P/R/F1/token comparison
    loader.py                 # parse task + gold YAML
    report.py                 # markdown/JSON output

  results/                    # submitted results
    claude-sqlprism/
    claude-baseline/

  docs/
    task-format.md            # how to write tasks
    scoring.md                # how scoring works
    contributing.md           # how to add repos/tasks/results
    guides/
      claude.md               # how to run with Claude
      codex.md                # how to run with Codex
      ollama.md               # how to run with Ollama
```

## CLI

```bash
# Setup — clone benchmark repos
sql-nav-bench setup
sql-nav-bench setup --repo jaffle-mesh

# List available tasks
sql-nav-bench tasks
sql-nav-bench tasks --repo mozilla-bigquery --category impact

# Score results against gold
sql-nav-bench score --results results/claude-sqlprism/
sql-nav-bench score --results results/claude-sqlprism/ --repo jaffle-mesh

# Compare two runs side-by-side
sql-nav-bench compare \
  --a results/claude-baseline/ \
  --b results/claude-sqlprism/

# Validate task/gold files (for contributors)
sql-nav-bench validate
```

The CLI handles setup, scoring, and comparison only. It does NOT run agents.

## Dependencies

Minimal:
- `click` — CLI framework
- `pyyaml` — task/gold/result parsing
- `pydantic` — validation

No LLM SDKs. No MCP dependencies. The benchmark is a measuring stick, not a runner.

---

## Task Count Target

Per repo:
- 2-3 reference tasks (A)
- 2-3 impact tasks (B)
- 2-3 lineage tasks (C)
- 2 mesh/boundary tasks where relevant (D)
- 1-2 reindex tasks (E)

~10-12 tasks per repo, ~40-48 tasks total.

## Gold Answer Creation

Ground truth is manually verified by inspecting repo source files directly. Not generated by any tool under test.

For each task:
1. Inspect relevant SQL/model files
2. Trace dependencies manually
3. Record exact expected entities
4. Note ambiguities (wildcards, macros, implicit deps)
5. Review with a second pass

## Success Criteria

Strong result:
- 50%+ reduction in tokens
- 50%+ reduction in tool calls
- Equal or better F1 on most tasks
- Clear wins on column lineage and cross-project impact
- Biggest gains on brutal repos

## Public Narrative

"On open SQL/dbt/SQLMesh repos, structural SQL tools helped an agent answer project understanding questions with far fewer tokens and tool calls than brute-force search, while improving correctness on lineage and impact tasks."

## Implementation Phases

1. **Scaffold** — project structure, CLI skeleton, repos.yml
2. **Gold set** — create tasks + gold answers for jaffle-mesh first (easiest to verify)
3. **Scorer** — implement set_match scoring, comparison report
4. **Expand** — add tasks for remaining 3 repos
5. **Results** — run SQLPrism + baseline, publish first results
