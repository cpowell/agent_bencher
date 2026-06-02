from pathlib import Path

from agent_bencher.batch import build_batch_result
from agent_bencher.cli import build_parser, format_run_id
from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.report import build_batch_markdown_report, build_markdown_report


def test_build_markdown_report_includes_session_summary() -> None:
    session = SessionResult(
        run_id="2026-05-31T14-26-00",
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="mtplx/mtplx-qwen36-27b-optimized-speed",
        session_id="opencode-session-123",
        started_at="2026-05-31T14:26:00Z",
        ended_at="2026-05-31T14:26:03Z",
        duration_seconds=3.5,
        status="completed",
        comment="nightly comparison against local models",
        prompts_attempted=2,
        prompts_completed=2,
        turns=[
            TurnResult(
                prompt_id="intro",
                prompt_text="Do this",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=1.2,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            ),
            TurnResult(
                prompt_id="explain",
                prompt_text="Explain that",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=2.3,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=210, output=80),
            ),
        ],
    )

    report = build_markdown_report([session])

    assert "# Benchmark Summary" in report
    assert "open-fast" in report
    assert "completed 2/2 prompts" in report
    assert "mtplx/mtplx-qwen36-27b-optimized-speed" in report
    assert "effective output TPS" in report
    assert "34.29" in report
    assert "effective total throughput TPS" in report
    assert "122.86" in report
    assert "comment: nightly comparison against local models" in report
    assert "| Turn | Prompt | Duration (s) | Input | Output | Output TPS | Total Throughput TPS | Stdout | Stderr |" in report
    assert "| 1 | intro | 1.20 | 100 | 40 | 33.33 | 116.67 |" in report
    assert "| 2 | explain | 2.30 | 210 | 80 | 34.78 | 126.09 |" in report


def test_build_parser_accepts_positional_run_config_then_conversation_args() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            "runs",
        ]
    )

    assert parsed.command == "bench"
    assert parsed.conversation == Path("conversations/sample.yaml")
    assert parsed.run_config == Path("run_configs/opencode.yaml")
    assert parsed.output_dir == Path("runs")


def test_format_run_id_uses_cross_platform_timestamp() -> None:
    assert format_run_id("2026-05-31", "14:26:00") == "2026-05-31T14-26-00"


def test_build_markdown_report_points_to_run_artifacts() -> None:
    session = SessionResult(
        run_id="2026-05-31T14-26-00",
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="mtplx/mtplx-qwen36-27b-optimized-speed",
        session_id="opencode-session-123",
        started_at="2026-05-31T14:26:00Z",
        ended_at="2026-05-31T14:26:03Z",
        duration_seconds=3.5,
        status="completed",
        comment="",
        prompts_attempted=2,
        prompts_completed=2,
        turns=[],
    )

    report = build_markdown_report([session])

    assert "conversation.md" in report
    assert "run.json" in report
    assert "turns.jsonl" in report


def test_build_parser_accepts_comment_arg() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--comment",
            "nightly regression sweep",
        ]
    )

    assert parsed.comment == "nightly regression sweep"


def test_build_batch_markdown_report_lists_failed_trials_and_aggregate_metrics() -> None:
    successful = SessionResult(
        run_id="run-1",
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-1",
        started_at="2026-06-01T00:00:00Z",
        ended_at="2026-06-01T00:00:01Z",
        duration_seconds=1.0,
        status="completed",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id="session-1",
                exit_code=0,
                duration_seconds=1.0,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            )
        ],
        comment="",
    )
    failed = SessionResult(
        run_id="run-2",
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-2",
        started_at="2026-06-01T00:00:02Z",
        ended_at="2026-06-01T00:00:03Z",
        duration_seconds=2.0,
        status="failed",
        prompts_attempted=1,
        prompts_completed=0,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id="session-2",
                exit_code=1,
                duration_seconds=2.0,
                stdout="{}",
                stderr="boom",
                token_usage=TokenUsage(input=10, output=1),
            )
        ],
        comment="",
    )

    batch = build_batch_result(batch_id="batch-1", requested_runs=2, comment="", sessions=[successful, failed])
    report = build_batch_markdown_report(batch)

    assert "# Benchmark Batch Summary" in report
    assert "successful runs: 1/2" in report
    assert "failed runs: 1" in report
    assert "duration_seconds" in report
    assert "trial-002" in report
