# sql-nav-bench

Benchmark for evaluating how well agents understand SQL project structure.

Tests structural reasoning — lineage, impact analysis, dependencies, cross-project navigation — not SQL query generation. No existing benchmark covers this category.

## Why

Every SQL benchmark today tests "write a query from natural language" (Spider, BIRD, etc.). None test "understand a SQL codebase well enough to answer structural questions about it."

sql-nav-bench fills that gap. It provides:

- **40 tasks** across 4 real-world repos (dbt, sqlmesh, raw SQL)
- **Gold answers** manually verified against actual source files
- **A scorer** that computes precision/recall/F1 and token efficiency
- **Vendor-agnostic** design — works with any LLM (Claude, Codex, Ollama, etc.)

## Quick Start

```bash
# Install
git clone https://github.com/your-org/sql-nav-bench && cd sql-nav-bench
uv sync

# Clone benchmark repos
sql-nav-bench setup

# List available tasks
sql-nav-bench tasks

# Score your results
sql-nav-bench score --results results/my-run/

# Compare two runs
sql-nav-bench compare --a results/baseline/ --b results/sqlprism/

# Validate task files
sql-nav-bench validate
```

## Benchmark Repos

| Repo | Type | Models | Difficulty | Tests |
|------|------|--------|------------|-------|
| Jaffle Shop Mesh Trio | dbt mesh | 12 | Medium | Cross-project deps, contracts, groups |
| TobikoData/sqlmesh examples/ | sqlmesh | ~57 | Medium | Multi-repo, hybrid dbt+sqlmesh |
| mozilla/bigquery-etl | Raw SQL | 2,346 | Brutal | BigQuery dialect, deep nesting |
| cal-itp/data-infra warehouse/ | dbt | 630 | Brutal | staging/int/mart, macros, incremental |

## Task Categories

| Category | Prefix | What It Tests |
|----------|--------|---------------|
| Reference | A | Where is X used? What depends on X? |
| Impact | B | If X changes, what breaks? (model + column level) |
| Lineage | C | What feeds X? Where does column Y come from? |
| Mesh | D | Cross-project consumers, boundary impact |
| Reindex | E | Post-change correctness, incremental update |

## Task Format

Tasks are YAML files with a question and gold answer:

```yaml
id: jaffle-mesh_impact_02
repo: jaffle-mesh
category: impact
difficulty: brutal
question: |
  If I remove column customer_id from stg_orders,
  what downstream models break?
tool_hint: column_impact
gold:
  required:
    - order_items
    - orders
    - customers
  optional: []
  forbidden:
    - stg_customers
scoring:
  method: set_match
  partial_credit: true
```

## Result Format

Agents produce result files:

```yaml
task_id: jaffle-mesh_impact_02
agent: claude-sonnet-4-6
tools: sqlprism
timestamp: 2026-04-03T14:30:00Z
answer:
  entities:
    - order_items
    - orders
    - customers
  explanation: "Traced via column lineage"
  confidence: high
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

## Scoring

**Correctness:** Precision, recall, and F1 against gold answers. Required entities must be found. Optional entities get credit but no penalty. Forbidden entities reduce precision.

**Efficiency:** Token usage (40%), tool calls (25%), search calls (20%), files opened (15%). Normalized via min-max scaling across compared runs.

**Composite:** 50% correctness + 50% efficiency.

```
sql-nav-bench compare --a results/baseline/ --b results/sqlprism/

| Metric               |     baseline |     sqlprism |
|----------------------|--------------|--------------|
| Tokens (median)      |       47,200 |        2,840 |  <- 94% reduction
| Tool calls           |           22 |            3 |
| Search calls         |           18 |            0 |
| Files opened         |           14 |            1 |
```

## How to Run a Benchmark

1. **Clone repos:** `sql-nav-bench setup`
2. **Pick tasks:** `sql-nav-bench tasks --repo jaffle-mesh --category impact`
3. **Run your agent** against each task question, recording results in the YAML format above
4. **Score:** `sql-nav-bench score --results results/my-run/`
5. **Compare:** `sql-nav-bench compare --a results/baseline/ --b results/my-tool/`

The benchmark does NOT run agents for you — bring your own LLM and tools.

## Contributing

### Add tasks

1. Fork the repo
2. Create task YAML files in `tasks/<repo-name>/`
3. Verify gold answers by inspecting actual source files
4. Run `sql-nav-bench validate`
5. Submit a PR

### Submit results

1. Run benchmark with your agent/tool
2. Save results in `results/<agent>-<tools>/`
3. Submit a PR

## License

Apache-2.0
