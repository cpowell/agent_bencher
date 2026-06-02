from __future__ import annotations

import json
from pathlib import Path
import re

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import AgentConfig, Prompt


def _result_dict(candidate: dict) -> dict:
    candidate_result = candidate.get("result")
    if isinstance(candidate_result, dict):
        return candidate_result
    return candidate


def _extract_json_string_field(stdout: str, field_name: str) -> str:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"([^"]*)"', stdout)
    if not match:
        return ""
    return bytes(match.group(1), "utf-8").decode("unicode_escape")


def _extract_usage(stdout: str) -> dict[str, int]:
    field_names = {
        "input_tokens": "input",
        "output_tokens": "output",
        "reasoning_tokens": "reasoning",
        "cache_read_input_tokens": "cache_read",
        "cache_creation_input_tokens": "cache_write",
    }
    extracted: dict[str, int] = {}
    for json_field, parsed_field in field_names.items():
        match = re.search(rf'"{re.escape(json_field)}"\s*:\s*(\d+)', stdout)
        if match:
            extracted[parsed_field] = int(match.group(1))
    return extracted


class ClaudeAdapter:
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
        fatal_error = None
        try:
            payload = json.loads(stdout) if stdout.strip() else {}
        except json.JSONDecodeError as error:
            session_id = _extract_json_string_field(stdout, "session_id")
            token_usage = _extract_usage(stdout)
            if session_id or token_usage:
                return {
                    "session_id": session_id,
                    "token_usage": {
                        "input": token_usage.get("input", 0),
                        "output": token_usage.get("output", 0),
                        "reasoning": token_usage.get("reasoning", 0),
                        "cache_read": token_usage.get("cache_read", 0),
                        "cache_write": token_usage.get("cache_write", 0),
                    },
                    "warnings": ["recovered-from-malformed-json"],
                    "fatal_error": None,
                }
            payload = {}
            fatal_error = f"ClaudeOutputParseError: {error.msg}"

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
            "fatal_error": fatal_error,
        }
