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
