"""Tests for repo setup/cloning."""

from pathlib import Path

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
