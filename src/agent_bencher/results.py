from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.models import SessionResult, TurnResult
from agent_bencher.report import build_markdown_report


def _write_turn_transcripts(*, output_dir: Path, turn: TurnResult, turn_index: int) -> None:
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stdout.txt"
    stderr_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stderr.txt"

    stdout_path.write_text(turn.stdout)
    stderr_path.write_text(turn.stderr)

    turn.stdout_path = str(stdout_path)
    turn.stderr_path = str(stderr_path)


def _serialize_turn(turn: TurnResult, *, run_id: str, turn_index: int) -> dict:
    return {
        "run_id": run_id,
        "turn_index": turn_index,
        "prompt_id": turn.prompt_id,
        "prompt_text": turn.prompt_text,
        "session_id": turn.session_id,
        "exit_code": turn.exit_code,
        "duration_seconds": turn.duration_seconds,
        "input_tokens": turn.token_usage.input,
        "output_tokens": turn.token_usage.output,
        "reasoning_tokens": turn.token_usage.reasoning,
        "cache_read_tokens": turn.token_usage.cache_read,
        "cache_write_tokens": turn.token_usage.cache_write,
        "stdout_path": turn.stdout_path,
        "stderr_path": turn.stderr_path,
        "warnings": list(turn.warnings),
    }


def _serialize_run(session: SessionResult, *, conversation_path: str, transcript_dir: str) -> dict:
    return {
        "run_id": session.run_id,
        "conversation_name": session.conversation_name,
        "agent_id": session.agent_id,
        "frontend": session.frontend,
        "backend_model": session.backend_model,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "duration_seconds": session.duration_seconds,
        "prompts_attempted": session.prompts_attempted,
        "prompts_completed": session.prompts_completed,
        "session_id": session.session_id,
        "status": session.status,
        "total_input_tokens": sum(turn.token_usage.input for turn in session.turns),
        "total_output_tokens": sum(turn.token_usage.output for turn in session.turns),
        "total_reasoning_tokens": sum(turn.token_usage.reasoning for turn in session.turns),
        "total_cache_read_tokens": sum(turn.token_usage.cache_read for turn in session.turns),
        "total_cache_write_tokens": sum(turn.token_usage.cache_write for turn in session.turns),
        "conversation_path": conversation_path,
        "transcript_dir": transcript_dir,
    }


def _write_combined_conversation_artifact(*, output_dir: Path, session: SessionResult) -> Path:
    destination = output_dir / "conversation.md"
    destination.write_text(f"# {session.conversation_name}\n")
    return destination


def write_results(*, sessions: list[SessionResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        for turn_index, turn in enumerate(session.turns, start=1):
            _write_turn_transcripts(output_dir=output_dir, turn=turn, turn_index=turn_index)

        conversation_path = str(_write_combined_conversation_artifact(output_dir=output_dir, session=session))
        transcript_dir = str(output_dir / "transcripts")

        turns_destination = output_dir / "turns.jsonl"
        turns_destination.write_text(
            "\n".join(
                json.dumps(_serialize_turn(turn, run_id=session.run_id, turn_index=index))
                for index, turn in enumerate(session.turns, start=1)
            )
            + "\n"
        )

        run_destination = output_dir / "run.json"
        run_destination.write_text(
            json.dumps(_serialize_run(session, conversation_path=conversation_path, transcript_dir=transcript_dir), indent=2)
        )

    (output_dir / "summary.md").write_text(build_markdown_report(sessions))
