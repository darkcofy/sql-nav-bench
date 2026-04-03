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
