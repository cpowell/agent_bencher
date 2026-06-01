from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.adapters.base import CommandSpec, WARMUP_PROMPT
from agent_bencher.models import AgentConfig, Prompt


def _result_dict(candidate: dict) -> dict:
    candidate_result = candidate.get("result")
    if isinstance(candidate_result, dict):
        return candidate_result
    return candidate


class ClaudeAdapter:
    def build_warmup_command(self, *, variant: AgentConfig, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", WARMUP_PROMPT, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def build_start_command(self, *, prompt: Prompt, variant: AgentConfig, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, *variant.args],
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
            argv=["claude", "-p", prompt.text, "--resume", session_id, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def parse_turn_output(self, *, stdout: str, stderr: str):
        payload = json.loads(stdout) if stdout.strip() else {}

        if isinstance(payload, list):
            candidates = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            candidates = [payload]
        else:
            candidates = []

        result = {}
        for candidate in candidates:
            candidate_result = _result_dict(candidate)
            if candidate_result.get("usage"):
                result = candidate_result
                break

        if not result and candidates:
            result = _result_dict(candidates[-1])

        usage = result.get("usage", {})
        session_id = result.get("session_id", "")
        if not session_id:
            for candidate in candidates:
                candidate_result = _result_dict(candidate)
                session_id = candidate_result.get("session_id", candidate.get("session_id", session_id))
                if session_id:
                    break

        return {
            "session_id": session_id,
            "token_usage": {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "reasoning": usage.get("reasoning_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
            "warnings": [],
        }
