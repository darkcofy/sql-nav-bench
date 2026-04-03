"""Tests for runner ABC and registry."""

import pytest

from sql_nav_bench.runners import Runner, get_runner


class TestRunnerRegistry:
    def test_get_sqlprism_cli_runner(self):
        runner = get_runner("sqlprism-cli")
        assert runner.name == "sqlprism-cli"
        assert isinstance(runner, Runner)

    def test_get_baseline_runner(self):
        runner = get_runner("baseline")
        assert runner.name == "baseline"
        assert isinstance(runner, Runner)

    def test_unknown_runner_raises(self):
        with pytest.raises(ValueError, match="Unknown runner"):
            get_runner("nonexistent")
