from pathlib import Path
import json

from agent_bencher.batch import build_batch_result
from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.results import write_batch_results, write_results


def test_write_results_emits_compact_run_json_and_turns_jsonl(tmp_path: Path) -> None:
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
        turns=[
            TurnResult(
                prompt_id="intro",
                prompt_text="Do this",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=1.2,
                stdout="assistant output",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            ),
            TurnResult(
                prompt_id="explain",
                prompt_text="Explain that",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=2.3,
                stdout="assistant output 2",
                stderr="",
                token_usage=TokenUsage(input=210, output=80),
            ),
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    run_payload = json.loads((tmp_path / "run.json").read_text())
    turn_payloads = [
        json.loads(line)
        for line in (tmp_path / "turns.jsonl").read_text().strip().splitlines()
    ]

    assert run_payload["run_id"] == "2026-05-31T14-26-00"
    assert run_payload["total_input_tokens"] == 310
    assert run_payload["total_output_tokens"] == 120
    assert run_payload["comment"] == ""
    assert run_payload["effective_output_tps"] == 34.285714285714285
    assert run_payload["effective_total_throughput_tps"] == 122.85714285714286
    assert "stdout" not in run_payload

    assert len(turn_payloads) == 2
    assert turn_payloads[0]["output_tps"] == 33.333333333333336
    assert turn_payloads[0]["total_throughput_tps"] == 116.66666666666667
    assert turn_payloads[1]["output_tps"] == 34.78260869565218
    assert turn_payloads[1]["total_throughput_tps"] == 126.08695652173914


def test_write_results_emits_human_readable_conversation_markdown(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="2026-05-31T14-26-00",
        conversation_name="sample-conversation",
        agent_id="mixed-agent",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-123",
        started_at="2026-05-31T14:26:00Z",
        ended_at="2026-05-31T14:26:03Z",
        duration_seconds=3.5,
        status="completed",
        comment="Benchmarking opencode against the repo after uv sync.",
        prompts_attempted=2,
        prompts_completed=2,
        turns=[
            TurnResult(
                prompt_id="inspect",
                prompt_text="Inspect the project",
                session_id="session-123",
                exit_code=0,
                duration_seconds=1.2,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:01.200000Z",
                stdout=(
                    '{"type":"step_start","timestamp":1780237817372,"sessionID":"session-123","part":{"type":"step-start"}}\n'
                    '{"type":"text","timestamp":1780237823600,"sessionID":"session-123","part":{"type":"text","text":"Project looks healthy."}}\n'
                    '{"type":"step_finish","timestamp":1780237823633,"sessionID":"session-123","part":{"type":"step-finish","tokens":{"input":100,"output":40,"reasoning":0,"cache":{"write":0,"read":0}}}}\n'
                ),
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            ),
            TurnResult(
                prompt_id="summarize",
                prompt_text="Summarize the findings",
                session_id="session-123",
                exit_code=0,
                duration_seconds=2.3,
                started_at="2026-05-31T14:26:01.200000Z",
                ended_at="2026-05-31T14:26:03.500000Z",
                stdout=json.dumps(
                    [
                        {"type": "system", "session_id": "session-123"},
                        {
                            "type": "assistant",
                            "session_id": "session-123",
                            "message": {
                                "content": [
                                    {"type": "thinking", "thinking": "private"},
                                    {"type": "text", "text": "Here is the summary."},
                                ]
                            },
                        },
                    ]
                ),
                stderr="",
                token_usage=TokenUsage(input=210, output=80),
            ),
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    conversation = (tmp_path / "conversation.md").read_text()
    run_payload = json.loads((tmp_path / "run.json").read_text())

    assert "# sample-conversation" in conversation
    assert "User comment: Benchmarking opencode against the repo after uv sync." in conversation
    assert "### Prompt" in conversation
    assert "Inspect the project" in conversation
    assert "Project looks healthy." in conversation
    assert "Summarize the findings" in conversation
    assert "Here is the summary." in conversation
    assert "private" not in conversation
    assert "## Turn 1" in conversation
    assert "## Turn 2" in conversation
    assert "## Turn 2: summarize" not in conversation
    assert "### Prompt (" in conversation
    assert "### Response (" in conversation
    assert "T+0.00s" in conversation
    assert "T+1.20s" in conversation
    assert "Response concluded at" in conversation
    assert run_payload["comment"] == "Benchmarking opencode against the repo after uv sync."


def test_write_results_extracts_human_readable_text_from_top_level_claude_result(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="2026-06-05T23-12-14-trial-001",
        conversation_name="sample-conversation",
        agent_id="claude-qwen35-122B-mtp",
        frontend="claude",
        backend_model="Qwen3.5-122B-A10B-4bit",
        session_id="ca0d7a5c-bc30-402a-af2b-056ed6a9fba7",
        started_at="2026-06-05T23:12:14.430000Z",
        ended_at="2026-06-05T23:12:40.869657Z",
        duration_seconds=26.1,
        status="completed",
        comment="MTP enabled",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Describe the MVC Pattern in software engineering.",
                session_id="ca0d7a5c-bc30-402a-af2b-056ed6a9fba7",
                exit_code=0,
                duration_seconds=26.1,
                started_at="2026-06-05T23:12:14.762104+00:00",
                ended_at="2026-06-05T23:12:40.869657+00:00",
                stdout=json.dumps(
                    {
                        "type": "result",
                        "result": "# MVC Pattern\n\nThis is the assistant answer.",
                        "session_id": "ca0d7a5c-bc30-402a-af2b-056ed6a9fba7",
                        "usage": {
                            "input_tokens": 0,
                            "output_tokens": 483,
                        },
                    }
                ),
                stderr="",
                token_usage=TokenUsage(input=0, output=483),
            ),
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    conversation = (tmp_path / "conversation.md").read_text()

    assert "# MVC Pattern" in conversation
    assert "This is the assistant answer." in conversation
    assert "_No human-readable assistant text extracted._" not in conversation


def test_write_results_counts_cached_prompt_tokens_in_input_totals(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="2026-06-05T23-12-14-trial-001",
        conversation_name="sample-conversation",
        agent_id="claude-qwen35-122B-mtp",
        frontend="claude",
        backend_model="Qwen3.5-122B-A10B-4bit",
        session_id="claude-session-123",
        started_at="2026-06-05T23:12:14Z",
        ended_at="2026-06-05T23:12:40Z",
        duration_seconds=10.0,
        status="completed",
        comment="",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Describe MVC",
                session_id="claude-session-123",
                exit_code=0,
                duration_seconds=10.0,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=0, output=40, cache_read=1000, cache_write=200),
            )
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    run_payload = json.loads((tmp_path / "run.json").read_text())
    turn_payload = json.loads((tmp_path / "turns.jsonl").read_text().strip())

    assert run_payload["total_input_tokens"] == 1200
    assert run_payload["total_cache_read_tokens"] == 1000
    assert run_payload["total_cache_write_tokens"] == 200
    assert run_payload["effective_total_throughput_tps"] == 124.0
    assert turn_payload["input_tokens"] == 1200
    assert turn_payload["cache_read_tokens"] == 1000
    assert turn_payload["cache_write_tokens"] == 200
    assert turn_payload["total_throughput_tps"] == 124.0


def test_write_results_uses_zero_throughput_for_zero_duration(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="2026-05-31T14-26-00",
        conversation_name="sample-conversation",
        agent_id="zero-duration",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-123",
        started_at="2026-05-31T14:26:00Z",
        ended_at="2026-05-31T14:26:00Z",
        duration_seconds=0.0,
        status="completed",
        comment="",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="instant",
                prompt_text="Reply instantly",
                session_id="session-123",
                exit_code=0,
                duration_seconds=0.0,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:00Z",
                stdout="assistant output",
                stderr="",
                token_usage=TokenUsage(input=10, output=4),
            ),
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    run_payload = json.loads((tmp_path / "run.json").read_text())
    turn_payload = json.loads((tmp_path / "turns.jsonl").read_text().strip())

    assert run_payload["effective_output_tps"] == 0.0
    assert run_payload["effective_total_throughput_tps"] == 0.0
    assert turn_payload["output_tps"] == 0.0
    assert turn_payload["total_throughput_tps"] == 0.0


def test_write_batch_results_uses_batch_first_layout(tmp_path: Path) -> None:
    session = SessionResult(
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
                stdout="assistant output",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            )
        ],
        comment="",
    )
    batch = build_batch_result(batch_id="batch-1", requested_runs=1, comment="", sessions=[session])

    write_batch_results(batch=batch, output_dir=tmp_path)

    batch_payload = json.loads((tmp_path / "batch.json").read_text())
    assert batch_payload["batch_id"] == "batch-1"
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "trials" / "trial-001" / "run.json").exists()
    assert (tmp_path / "trials" / "trial-001" / "turns.jsonl").exists()
