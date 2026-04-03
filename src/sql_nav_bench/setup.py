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

            click.echo("  Cloning...")
            subprocess.run(cmd, shell=True, check=True)

        click.echo(f"  Done: {name}")
