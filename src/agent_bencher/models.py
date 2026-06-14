from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Prompt:
    text: str


@dataclass(slots=True)
class AgentConfig:
    id: str
    frontend: str
    model: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Conversation:
    name: str
    source_workspace: Path
    prompts: list[Prompt]


@dataclass(slots=True)
class TokenUsage:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


@dataclass(slots=True)
class TurnResult:
    prompt_id: str
    prompt_text: str
    session_id: str
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    token_usage: TokenUsage
    started_at: str = ""
    ended_at: str = ""
    stdout_path: str = ""
    stderr_path: str = ""
    warnings: list[str] = field(default_factory=list)
    fatal_error: str = ""


@dataclass(slots=True)
class SessionResult:
    run_id: str
    conversation_name: str
    agent_id: str
    frontend: str
    backend_model: str
    session_id: str
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    prompts_attempted: int
    prompts_completed: int
    turns: list[TurnResult]
    comment: str = ""


@dataclass(slots=True)
class MetricSummary:
    mean: float
    min: float
    max: float
    stddev: float


@dataclass(slots=True)
class BatchResult:
    batch_id: str
    conversation_name: str
    agent_id: str
    frontend: str
    backend_model: str
    comment: str
    requested_runs: int
    successful_runs: int
    failed_runs: int
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    sessions: list[SessionResult]
    run_metrics: dict[str, MetricSummary]
    turn_metrics: list[dict[str, MetricSummary]]
