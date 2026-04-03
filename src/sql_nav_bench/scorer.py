"""Scoring engine for benchmark results."""

from __future__ import annotations

from dataclasses import dataclass

from sql_nav_bench.models import Gold, Metrics


@dataclass
class ScoreResult:
    precision: float
    recall: float
    f1: float


def score_set_match(found: list[str], gold: Gold) -> ScoreResult:
    """Score a set of found entities against gold standard.

    - Required entities in found: true positives for recall
    - Optional entities in found: true positives (no penalty if missing)
    - Forbidden entities in found: false positives
    - Unknown entities (not in any gold list): false positives
    """
    found_set = set(found)
    required_set = set(gold.required)
    optional_set = set(gold.optional)
    valid_set = required_set | optional_set

    if not found_set and not required_set:
        return ScoreResult(precision=1.0, recall=1.0, f1=1.0)

    true_positives = found_set & valid_set

    if found_set:
        precision = len(true_positives) / len(found_set)
    else:
        precision = 0.0

    if required_set:
        recall = len(found_set & required_set) / len(required_set)
    else:
        recall = 1.0

    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return ScoreResult(precision=precision, recall=recall, f1=f1)


_WEIGHTS = {
    "tokens_total": 0.40,
    "tool_calls": 0.25,
    "search_calls": 0.20,
    "files_opened": 0.15,
}


def score_efficiency(metrics_list: list[Metrics]) -> list[float]:
    """Compute normalized efficiency scores using min-max scaling.

    Lower is better for all metrics. Best = 1.0, worst = 0.0.
    Single run scores 1.0.
    """
    if len(metrics_list) == 1:
        return [1.0]

    scores = []
    for metrics in metrics_list:
        weighted = 0.0
        for field, weight in _WEIGHTS.items():
            values = [getattr(m, field) for m in metrics_list]
            min_val = min(values)
            max_val = max(values)
            val = getattr(metrics, field)
            if max_val == min_val:
                normalized = 1.0
            else:
                normalized = 1.0 - (val - min_val) / (max_val - min_val)
            weighted += normalized * weight
        scores.append(weighted)

    return scores
