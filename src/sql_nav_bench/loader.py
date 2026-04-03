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
