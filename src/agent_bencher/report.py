from __future__ import annotations

from agent_bencher.models import SessionResult


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def build_markdown_report(sessions: list[SessionResult]) -> str:
    lines = ["# Benchmark Summary", ""]

    for session in sessions:
        total_input = sum(turn.token_usage.input for turn in session.turns)
        total_output = sum(turn.token_usage.output for turn in session.turns)
        effective_output_tps = _safe_divide(total_output, session.duration_seconds)
        effective_total_throughput_tps = _safe_divide(total_input + total_output, session.duration_seconds)

        lines.extend(
            [
                f"## {session.agent_id}",
                f"- run id: {session.run_id}",
                f"- frontend: {session.frontend}",
                f"- backend model: {session.backend_model}",
                f"- conversation: {session.conversation_name}",
                f"- session id: {session.session_id}",
                *([f"- comment: {session.comment}"] if session.comment else []),
                f"- status: {session.status}",
                f"- completed {session.prompts_completed}/{session.prompts_attempted} prompts",
                f"- duration: {session.duration_seconds:.2f}s",
                f"- total input tokens: {total_input}",
                f"- total output tokens: {total_output}",
                f"- effective output TPS: {effective_output_tps:.2f}",
                f"- effective total throughput TPS: {effective_total_throughput_tps:.2f}",
                f"- run summary: run.json",
                f"- turn records: turns.jsonl",
                f"- combined conversation: conversation.md",
                "",
                "| Turn | Prompt | Duration (s) | Input | Output | Output TPS | Total Throughput TPS | Stdout | Stderr |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )

        for turn_index, turn in enumerate(session.turns, start=1):
            output_tps = _safe_divide(turn.token_usage.output, turn.duration_seconds)
            total_throughput_tps = _safe_divide(
                turn.token_usage.input + turn.token_usage.output,
                turn.duration_seconds,
            )
            lines.append(
                f"| {turn_index} | {turn.prompt_id} | {turn.duration_seconds:.2f} | "
                f"{turn.token_usage.input} | {turn.token_usage.output} | "
                f"{output_tps:.2f} | {total_throughput_tps:.2f} | "
                f"`{turn.stdout_path or 'transcripts/pending'}` | `{turn.stderr_path or 'transcripts/pending'}` |"
            )
        lines.append("")

    return "\n".join(lines)
