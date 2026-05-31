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
                f"## {session.agent_id}",
                f"- frontend: {session.frontend}",
                f"- backend model: {session.backend_model}",
                f"- conversation: {session.conversation_name}",
                f"- session id: {session.session_id}",
                f"- completed {session.prompts_completed}/{session.prompts_attempted} prompts",
                f"- total duration: {total_duration:.2f}s",
                f"- total input tokens: {total_input}",
                f"- total output tokens: {total_output}",
                f"- combined conversation: conversation.md",
                "",
                "| Turn | Prompt | Duration (s) | Input | Output | Stdout | Stderr |",
                "| --- | --- | ---: | ---: | ---: | --- | --- |",
            ]
        )

        for turn_index, turn in enumerate(session.turns, start=1):
            lines.append(
                f"| {turn_index} | {turn.prompt_id} | {turn.duration_seconds:.2f} | "
                f"{turn.token_usage.input} | {turn.token_usage.output} | "
                f"`{turn.stdout_path or 'transcripts/pending'}` | `{turn.stderr_path or 'transcripts/pending'}` |"
            )
        lines.append("")

    return "\n".join(lines)
