"""Pydantic data models for tasks, results, gold answers, and scoring."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Category(str, Enum):
    REFERENCE = "reference"
    IMPACT = "impact"
    LINEAGE = "lineage"
    MESH = "mesh"
    REINDEX = "reindex"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    BRUTAL = "brutal"


class ScoringMethod(str, Enum):
    SET_MATCH = "set_match"
    CONTAINS = "contains"
    ORDERED_LIST = "ordered_list"
    JUDGMENT = "judgment"


class Gold(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    method: ScoringMethod
    partial_credit: bool = False


class Task(BaseModel):
    id: str
    repo: str
    category: Category
    difficulty: Difficulty
    question: str
    tool_hint: str
    gold: Gold
    scoring: ScoringConfig
    notes: str = ""


class Metrics(BaseModel):
    tool_calls: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    files_opened: int = Field(ge=0)
    tokens_input: int = Field(ge=0)
    tokens_output: int = Field(ge=0)
    tokens_total: int = Field(ge=0)
    wall_time_seconds: float = Field(ge=0)
    tool_breakdown: dict[str, int] = Field(default_factory=dict)


class Result(BaseModel):
    task_id: str
    agent: str
    tools: str
    timestamp: str
    answer: dict[str, Any]
    metrics: Metrics


class RepoSource(BaseModel):
    url: str
    path: str
    sparse_checkout: str | None = None


class RepoConfig(BaseModel):
    type: str
    sources: list[RepoSource]
    pin: str = "main"
    difficulty: Difficulty
    description: str


class RepoManifest(BaseModel):
    repos: dict[str, RepoConfig]
