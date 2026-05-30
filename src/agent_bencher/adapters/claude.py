from __future__ import annotations

import json
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

    def parse_turn_output(self, *, stdout: str, stderr: str):
        payload = json.loads(stdout) if stdout.strip() else {}
        result = payload.get("result", payload)
        usage = result.get("usage", {})
        return {
            "session_id": result.get("session_id", payload.get("session_id", "")),
            "token_usage": {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "reasoning": usage.get("reasoning_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
            "warnings": [],
        }
