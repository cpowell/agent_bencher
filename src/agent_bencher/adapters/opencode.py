from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import AgentConfig, Prompt


class OpenCodeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: AgentConfig, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["opencode", "run", *variant.args, "-m", variant.model, prompt.text],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: AgentConfig,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=[
                "opencode",
                "run",
                *variant.args,
                "-m",
                variant.model,
                "--session",
                session_id,
                prompt.text,
            ],
            cwd=workspace,
            env=variant.env,
        )

    def parse_turn_output(self, *, stdout: str, stderr: str):
        session_id = ""
        token_usage = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}

        for line in stdout.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            session_id = payload.get("sessionID", payload.get("session_id", session_id))
            if payload.get("type") == "step_finish":
                part = payload.get("part", {})
                tokens = part.get("tokens", {})
                cache = tokens.get("cache", {})
                token_usage = {
                    "input": tokens.get("input", 0),
                    "output": tokens.get("output", 0),
                    "reasoning": tokens.get("reasoning", 0),
                    "cache_read": cache.get("read", 0),
                    "cache_write": cache.get("write", 0),
                }
            elif payload.get("type") == "response.completed":
                token_usage = payload.get("token_usage", token_usage)

        return {
            "session_id": session_id,
            "token_usage": token_usage,
            "warnings": [],
        }
