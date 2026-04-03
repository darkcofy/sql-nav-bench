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

    # Project extraction (do this early so we don't confuse project with model)
    proj_match = re.search(r"(?:from|in)\s+the\s+(\w+)\s+project", question, re.IGNORECASE)
    if proj_match:
        result["project"] = proj_match.group(1)

    # Extract column: "column X from/in Y" or "column X in the Y model"
    col_match = re.search(
        r"column\s+[`']?(\w+)[`']?\s+(?:from|in|of)\s+[`']?(\w+)[`']?",
        question,
        re.IGNORECASE,
    )
    if col_match:
        result["column"] = col_match.group(1)
        result["model"] = col_match.group(2)
        return result

    # Also handle "lineage of X in the Y model"
    col_match2 = re.search(
        r"(?:lineage|trace)\s+(?:of\s+)?[`']?(\w+)[`']?\s+in\s+(?:the\s+)?[`']?(\w+)[`']?\s+model",
        question,
        re.IGNORECASE,
    )
    if col_match2:
        result["column"] = col_match2.group(1)
        result["model"] = col_match2.group(2)
        return result

    # Model extraction — ordered by specificity
    model_patterns = [
        # "the stg_orders model" or "the orders model"
        r"(?:the|a)\s+[`']?(\w+)[`']?\s+(?:model|table|asset)",
        # "model stg_orders"
        r"(?:model|table|asset)\s+[`']?(\w+)[`']?",
        # "stg_orders model" (name before keyword)
        r"[`']?(\w+(?:_\w+)+)[`']?\s+(?:model|table|changes|change)",
        # "depend on stg_customers"
        r"depend\s+on\s+[`']?(\w+)[`']?",
        # "X changes" or "change X" or "modify X"
        r"(?:change|modify|remove|drop)\s+(?:the\s+)?(?:model\s+)?[`']?(\w+(?:_\w+)+)[`']?",
        r"[`']?(\w+(?:_\w+)+)[`']?\s+changes",
        # "feed the X model" or "feed X"
        r"feed\w*\s+(?:the\s+)?[`']?(\w+)[`']?",
    ]

    for pattern in model_patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            name = match.group(1)
            # Don't pick up project names or generic words as model names
            if name != result.get("project") and name.lower() not in (
                "the", "all", "which", "what", "from", "that", "this",
                "downstream", "upstream", "new", "specific",
            ):
                result["model"] = name
                break

    # Fallback: first snake_case name (likely a model/table name)
    if not result["model"]:
        snake_match = re.search(r"\b(\w+(?:_\w+)+)\b", question)
        if snake_match:
            name = snake_match.group(1)
            if name != result.get("project"):
                result["model"] = name

    # "to X in the Y project" pattern (e.g., "adding column to stg_orders in platform")
    if not result["model"] or result["model"] == result.get("project"):
        to_match = re.search(r"to\s+[`']?(\w+(?:_\w+)+)[`']?\s+in\s+the", question, re.IGNORECASE)
        if to_match:
            result["model"] = to_match.group(1)

    # Backtick names override if we got a bad match or no match
    if backtick_names:
        # Use first backtick name that isn't the project
        for bn in backtick_names:
            if bn != result.get("project"):
                result["model"] = bn
                break

    # Final fallback: use project as model if nothing else found
    if not result["model"] and result["project"]:
        result["model"] = result["project"]

    return result
