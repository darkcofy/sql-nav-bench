"""Extract entity names from task questions."""

from __future__ import annotations

import re

from sql_nav_bench.models import Task


def extract_entities(task: Task) -> dict[str, str | None]:
    """Extract model, column, and project names from task question.

    Returns dict with keys: model, column, project (any may be None).
    """
    question = task.question
    result: dict[str, str | None] = {"model": None, "column": None, "project": None}

    # Extract backtick-quoted names
    backtick_names = re.findall(r"`(\w+)`", question)

    # Extract column: look for "column X from Y" or "column X in Y" patterns
    col_match = re.search(
        r"column\s+[`]?(\w+)[`]?\s+(?:from|in|of)\s+[`]?(\w+)[`]?",
        question,
        re.IGNORECASE,
    )
    if col_match:
        result["column"] = col_match.group(1)
        result["model"] = col_match.group(2)
        return result

    # Extract model: look for common patterns
    model_patterns = [
        r"(?:model|table|asset)\s+[`]?(\w+)[`]?",
        r"(?:is|does)\s+[`]?(\w+)[`]?\s+(?:used|referenced)",
        r"(?:feed|feeds)\s+(?:the\s+)?[`]?(\w+)[`]?",
        r"(?:change|modify|remove|drop)\s+(?:model\s+)?[`]?(\w+)[`]?",
        r"[`](\w+)[`]",  # any backtick-quoted name as fallback
    ]

    for pattern in model_patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            result["model"] = match.group(1)
            break

    # If we found backtick names but no model yet, use first one
    if not result["model"] and backtick_names:
        result["model"] = backtick_names[0]

    # Project extraction
    proj_match = re.search(r"(?:from|in)\s+the\s+(\w+)\s+project", question, re.IGNORECASE)
    if proj_match:
        result["project"] = proj_match.group(1)
        if not result["model"]:
            result["model"] = proj_match.group(1)

    return result
