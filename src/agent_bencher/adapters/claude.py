from __future__ import annotations

from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class ClaudeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, "--resume", session_id, *variant.args],
            cwd=workspace,
            env=variant.env,
        )
