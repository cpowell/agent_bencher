from __future__ import annotations

import json
from pathlib import Path
import re

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import AgentConfig, Prompt


def _extract_text_field(stdout: str, field_name: str) -> str:
    match = re.search(rf'{re.escape(field_name)}:\s*"([^"]+)"', stdout)
    return match.group(1) if match else ""


def _extract_suggestions(stdout: str) -> list[str]:
    match = re.search(r"suggestions:\s*\[(.*?)\]", stdout, re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def _extract_provider_model_not_found_error(stdout: str) -> str | None:
    if "ProviderModelNotFoundError" not in stdout:
        return None

    provider_id = _extract_text_field(stdout, "providerID")
    model_id = _extract_text_field(stdout, "modelID")
    suggestions = _extract_suggestions(stdout)

    if not provider_id and not model_id:
        return "OpenCodeProviderError: provider model not found"

    parts = [
        "OpenCodeProviderError:",
        provider_id or "unknown provider",
        "model",
        f"{model_id!r}" if model_id else "'unknown'",
        "not found",
    ]
    message = " ".join(parts)
    if suggestions:
        message += f"; suggestions: {', '.join(suggestions)}"
    return message


class OpenCodeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: AgentConfig, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=[
                "opencode",
                "run",
                *variant.args,
                "--dir",
                str(workspace.resolve()),
                "-m",
                variant.model,
                prompt.text,
            ],
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
                "--dir",
                str(workspace.resolve()),
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
        fatal_error = None
        warnings = []

        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                warnings.append("malformed-opencode-jsonl")
                fatal_error = _extract_provider_model_not_found_error(stdout) or (
                    f"OpenCodeOutputParseError: {error.msg} "
                    f"at column {error.colno}; offending line: {line!r}"
                )
                break
            session_id = payload.get("sessionID", payload.get("session_id", session_id))
            if payload.get("type") == "error":
                error = payload.get("error", {})
                name = error.get("name", "UnknownError")
                data = error.get("data", {})
                message = data.get("message") or error.get("message") or "unknown opencode error"
                fatal_error = f"{name}: {message}"
                continue
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
            "warnings": warnings,
            "fatal_error": fatal_error,
        }
