from __future__ import annotations

from agent_bencher.metrics import prompt_input_tokens, total_prompt_input_tokens
from agent_bencher.models import BatchResult, SessionResult


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def build_markdown_report(sessions: list[SessionResult]) -> str:
    lines = ["# Benchmark Summary", ""]

    for session in sessions:
        total_input = total_prompt_input_tokens(session)
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
            input_tokens = prompt_input_tokens(turn)
            output_tps = _safe_divide(turn.token_usage.output, turn.duration_seconds)
            total_throughput_tps = _safe_divide(
                input_tokens + turn.token_usage.output,
                turn.duration_seconds,
            )
            lines.append(
                f"| {turn_index} | {turn.prompt_id} | {turn.duration_seconds:.2f} | "
                f"{input_tokens} | {turn.token_usage.output} | "
                f"{output_tps:.2f} | {total_throughput_tps:.2f} | "
                f"`{turn.stdout_path or 'transcripts/pending'}` | `{turn.stderr_path or 'transcripts/pending'}` |"
            )
        lines.append("")

    return "\n".join(lines)


def build_batch_markdown_report(batch: BatchResult) -> str:
    lines = [
        "# Benchmark Batch Summary",
        "",
        f"- batch id: {batch.batch_id}",
        f"- conversation: {batch.conversation_name}",
        f"- agent: {batch.agent_id}",
        f"- frontend: {batch.frontend}",
        f"- backend model: {batch.backend_model}",
        f"- status: {batch.status}",
        f"- successful runs: {batch.successful_runs}/{batch.requested_runs}",
        f"- failed runs: {batch.failed_runs}",
        f"- duration: {batch.duration_seconds:.2f}s",
    ]
    if batch.comment:
        lines.append(f"- comment: {batch.comment}")

    lines.extend(
        [
            "",
            "## Run-Level Aggregates",
            "",
            "| Metric | Mean | Min | Max | Stddev |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for metric_name, summary in batch.run_metrics.items():
        lines.append(
            f"| {metric_name} | {summary.mean:.2f} | {summary.min:.2f} | {summary.max:.2f} | {summary.stddev:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Per-Turn Aggregates",
            "",
            "| Turn | Metric | Mean | Min | Max | Stddev |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for turn_index, turn_metrics in enumerate(batch.turn_metrics, start=1):
        for metric_name, summary in turn_metrics.items():
            lines.append(
                f"| {turn_index} | {metric_name} | {summary.mean:.2f} | {summary.min:.2f} | {summary.max:.2f} | {summary.stddev:.2f} |"
            )

    lines.extend(
        [
            "",
            "## Trials",
            "",
            "| Trial | Run ID | Status | Path |",
            "| --- | --- | --- | --- |",
        ]
    )
    for index, session in enumerate(batch.sessions, start=1):
        lines.append(
            f"| trial-{index:03d} | {session.run_id} | {session.status} | `trials/trial-{index:03d}` |"
        )

    return "\n".join(lines) + "\n"
