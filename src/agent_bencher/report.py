from __future__ import annotations

from agent_bencher.models import SessionResult


def build_markdown_report(sessions: list[SessionResult]) -> str:
    lines = ["# Benchmark Summary", ""]

    for session in sessions:
        total_input = sum(turn.token_usage.input for turn in session.turns)
        total_output = sum(turn.token_usage.output for turn in session.turns)
        total_duration = sum(turn.duration_seconds for turn in session.turns)

        lines.extend(
            [
                f"## {session.variant_id}",
                f"- frontend: {session.frontend}",
                f"- backend model: {session.backend_model}",
                f"- session id: {session.session_id}",
                f"- completed {session.prompts_completed}/{session.prompts_attempted} prompts",
                f"- total duration: {total_duration:.2f}s",
                f"- total input tokens: {total_input}",
                f"- total output tokens: {total_output}",
                "",
            ]
        )

    return "\n".join(lines)
