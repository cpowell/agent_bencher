from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Prompt:
    id: str
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
    stdout_path: str = ""
    stderr_path: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionResult:
    conversation_name: str
    agent_id: str
    frontend: str
    backend_model: str
    session_id: str
    prompts_attempted: int
    prompts_completed: int
    turns: list[TurnResult]
