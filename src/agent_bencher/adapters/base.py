from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from agent_bencher.models import AgentConfig, Prompt


@dataclass(slots=True)
class CommandSpec:
    argv: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)


class FrontendAdapter(Protocol):
    def build_start_command(self, *, prompt: Prompt, variant: AgentConfig, workspace: Path) -> CommandSpec: ...

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: AgentConfig,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec: ...
