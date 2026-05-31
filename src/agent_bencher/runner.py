from __future__ import annotations

from pathlib import Path

from agent_bencher.models import AgentConfig, Conversation, SessionResult, TokenUsage, TurnResult

def run_conversation(
    *,
    conversation: Conversation,
    agent: AgentConfig,
    workspace: Path,
    adapter,
    run_command,
    run_id: str,
    started_at: str,
):
    turns: list[TurnResult] = []
    session_id = ""
    execution_duration = 0.0

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
        execution_duration += completed.duration_seconds

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
                started_at=completed.started_at,
                ended_at=completed.ended_at,
                warnings=list(parsed["warnings"]),
            )
        )

        if completed.exit_code != 0:
            break

    status = "completed" if len(turns) == len(conversation.prompts) and all(turn.exit_code == 0 for turn in turns) else "partial"
    if turns and turns[-1].exit_code != 0:
        status = "failed"

    return SessionResult(
        run_id=run_id,
        conversation_name=conversation.name,
        agent_id=agent.id,
        frontend=agent.frontend,
        backend_model=agent.model,
        session_id=session_id,
        started_at=started_at,
        ended_at=turns[-1].ended_at if turns else started_at,
        duration_seconds=execution_duration,
        status=status,
        prompts_attempted=len(turns),
        prompts_completed=sum(1 for turn in turns if turn.exit_code == 0),
        turns=turns,
    )
