from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from agent_bencher.models import AgentConfig, Conversation, SessionResult, TokenUsage, TurnResult


class ProgressBar(Protocol):
    def set_description_str(self, value: str) -> None: ...

    def update(self, value: int) -> None: ...

    def close(self) -> None: ...


class NoOpProgressBar:
    def set_description_str(self, value: str) -> None:
        return None

    def update(self, value: int) -> None:
        return None

    def close(self) -> None:
        return None


def _default_progress_factory(*, total: int, disable: bool, unit: str) -> ProgressBar:
    try:
        from tqdm import tqdm
    except ModuleNotFoundError:
        return NoOpProgressBar()

    return tqdm(total=total, disable=disable, unit=unit)


def _excerpt(value: str, *, limit: int = 400) -> str:
    text = value.strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _build_turn_failure_message(
    *,
    turn_index: int,
    prompt_text: str,
    agent: AgentConfig,
    fatal_error: str,
    stdout: str,
    stderr: str,
) -> str:
    lines = [
        f"turn {turn_index} failed",
        f"frontend: {agent.frontend}",
        f"model: {agent.model}",
        f"prompt: {prompt_text}",
        f"error: {fatal_error}",
    ]

    stdout_excerpt = _excerpt(stdout)
    stderr_excerpt = _excerpt(stderr)
    if stdout_excerpt:
        lines.append(f"stdout: {stdout_excerpt}")
    if stderr_excerpt:
        lines.append(f"stderr: {stderr_excerpt}")

    return "\n".join(lines)


def _format_prompt_id(index: int) -> str:
    return f"{index + 1:02d}"


def _format_progress_description(*, index: int, total: int, prompt_text: str) -> str:
    return f"prompt {index + 1}/{total}: {_excerpt(prompt_text, limit=80)}"


def run_conversation(
    *,
    conversation: Conversation,
    agent: AgentConfig,
    workspace: Path,
    adapter,
    run_command,
    run_id: str,
    started_at: str,
    comment: str = "",
    progress_factory: Callable[..., ProgressBar] = _default_progress_factory,
):
    turns: list[TurnResult] = []
    session_id = ""
    execution_duration = 0.0

    progress = progress_factory(
        total=len(conversation.prompts),
        disable=not sys.stderr.isatty(),
        unit="prompt",
    )
    try:
        for index, prompt in enumerate(conversation.prompts):
            progress.set_description_str(
                _format_progress_description(
                    index=index,
                    total=len(conversation.prompts),
                    prompt_text=prompt.text,
                )
            )

            if index == 0:
                command = adapter.build_start_command(prompt=prompt, variant=agent, workspace=workspace)
            else:
                command = adapter.build_continue_command(
                    prompt=prompt,
                    variant=agent,
                    workspace=workspace,
                    session_id=session_id,
                )

            completed = run_command(command)
            parsed = adapter.parse_turn_output(stdout=completed.stdout, stderr=completed.stderr)
            fatal_error = parsed.get("fatal_error")
            if fatal_error:
                raise RuntimeError(
                    _build_turn_failure_message(
                        turn_index=index + 1,
                        prompt_text=prompt.text,
                        agent=agent,
                        fatal_error=fatal_error,
                        stdout=completed.stdout,
                        stderr=completed.stderr,
                    )
                )
            session_id = parsed["session_id"]
            execution_duration += completed.duration_seconds

            turns.append(
                TurnResult(
                    prompt_id=_format_prompt_id(index),
                    prompt_text=prompt.text,
                    session_id=session_id,
                    exit_code=completed.exit_code,
                    duration_seconds=completed.duration_seconds,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    token_usage=TokenUsage(**parsed["token_usage"]),
                    started_at=completed.started_at,
                    ended_at=completed.ended_at,
                    warnings=list(parsed["warnings"]),
                )
            )
            progress.update(1)

            if completed.exit_code != 0:
                break
    finally:
        progress.close()

    status = "completed" if len(turns) == len(conversation.prompts) and all(turn.exit_code == 0 for turn in turns) else "partial"
    if turns and turns[-1].exit_code != 0:
        status = "failed"

    return SessionResult(
        run_id=run_id,
        conversation_name=conversation.name,
        agent_id=agent.id,
        frontend=agent.frontend,
        backend_model=agent.model,
        comment=comment,
        session_id=session_id,
        started_at=started_at,
        ended_at=turns[-1].ended_at if turns else started_at,
        duration_seconds=execution_duration,
        status=status,
        prompts_attempted=len(turns),
        prompts_completed=sum(1 for turn in turns if turn.exit_code == 0),
        turns=turns,
    )
