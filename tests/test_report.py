from pathlib import Path

from agent_bencher.cli import build_parser
from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.report import build_markdown_report


def test_build_markdown_report_includes_session_summary() -> None:
    session = SessionResult(
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="mtplx/mtplx-qwen36-27b-optimized-speed",
        session_id="opencode-session-123",
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


def test_build_parser_accepts_conversation_and_agent_args() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        [
            "bench",
            "--conversation",
            "conversations/sample.yaml",
            "--agent",
            "agents/opencode.yaml",
            "--output-dir",
            "runs",
        ]
    )

    assert parsed.command == "bench"
    assert parsed.conversation == Path("conversations/sample.yaml")
    assert parsed.agent == Path("agents/opencode.yaml")
    assert parsed.output_dir == Path("runs")
