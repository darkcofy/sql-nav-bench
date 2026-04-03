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
@click.option("--runner", required=True, type=click.Choice(["sqlprism-cli", "baseline"]))
@click.option("--repo", help="Run against specific repo only")
def run(runner: str, repo: str | None) -> None:
    """Run benchmark tasks with a specific runner."""
    import yaml as yaml_lib

    from sql_nav_bench.loader import load_tasks
    from sql_nav_bench.runners import get_runner

    runner_instance = get_runner(runner)
    tasks_dir = Path("tasks")
    repos_dir = Path("repos")
    results_dir = Path("results") / runner_instance.name

    if not tasks_dir.exists():
        click.echo("No tasks directory found.")
        return

    results_dir.mkdir(parents=True, exist_ok=True)

    all_tasks = []
    for repo_dir in sorted(tasks_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        if repo and repo_dir.name != repo:
            continue
        all_tasks.extend(load_tasks(repo_dir))

    if not all_tasks:
        click.echo("No tasks found.")
        return

    # Group tasks by repo for setup
    repos_seen: set[str] = set()
    for task in all_tasks:
        if task.repo not in repos_seen:
            repo_path = repos_dir / task.repo
            if repo_path.exists():
                click.echo(f"Setting up {runner_instance.name} for {task.repo}...")
                try:
                    runner_instance.setup(task.repo, repo_path)
                except Exception as e:
                    click.echo(f"  Setup failed: {e}")
            repos_seen.add(task.repo)

    click.echo(f"\nRunning {len(all_tasks)} tasks with {runner_instance.name}...\n")
    click.echo(f"{'Task ID':<35} {'Entities':>8} {'Calls':>6} {'Time':>8}")
    click.echo("-" * 57)

    for task in all_tasks:
        repo_path = repos_dir / task.repo
        result = runner_instance.execute_task(task, repo_path)

        # Save result
        result_path = results_dir / f"{task.id}.yml"
        with open(result_path, "w") as f:
            yaml_lib.dump(result.model_dump(), f, default_flow_style=False, sort_keys=False)

        entity_count = len(result.answer.get("entities", []))
        click.echo(
            f"{task.id:<35} {entity_count:>8} {result.metrics.tool_calls:>6} "
            f"{result.metrics.wall_time_seconds:>7.2f}s"
        )

    click.echo(f"\nResults saved to {results_dir}/")


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
