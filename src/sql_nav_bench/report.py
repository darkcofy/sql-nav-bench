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
