from __future__ import annotations

from pathlib import Path

from agent_bencher.models import AgentConfig, Conversation, SessionResult, TokenUsage, TurnResult


def run_conversation(*, conversation: Conversation, agent: AgentConfig, workspace: Path, adapter, run_command):
    turns: list[TurnResult] = []
    session_id = ""

    for index, prompt in enumerate(conversation.prompts):
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
        session_id = parsed["session_id"]

        turns.append(
            TurnResult(
                prompt_id=prompt.id,
                prompt_text=prompt.text,
                session_id=session_id,
                exit_code=completed.exit_code,
                duration_seconds=completed.duration_seconds,
                stdout=completed.stdout,
                stderr=completed.stderr,
                token_usage=TokenUsage(**parsed["token_usage"]),
                warnings=list(parsed["warnings"]),
            )
        )

        if completed.exit_code != 0:
            break

    return SessionResult(
        conversation_name=conversation.name,
        agent_id=agent.id,
        frontend=agent.frontend,
        backend_model=agent.model,
        session_id=session_id,
        prompts_attempted=len(turns),
        prompts_completed=sum(1 for turn in turns if turn.exit_code == 0),
        turns=turns,
    )
