from pathlib import Path
import json

from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.results import write_results


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
    turns_lines = (tmp_path / "turns.jsonl").read_text().strip().splitlines()

    assert run_payload["run_id"] == "2026-05-31T14-26-00"
    assert run_payload["total_input_tokens"] == 310
    assert run_payload["total_output_tokens"] == 120
    assert "stdout" not in run_payload
    assert len(turns_lines) == 2


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

    assert "# sample-conversation" in conversation
    assert "### Prompt" in conversation
    assert "Inspect the project" in conversation
    assert "Project looks healthy." in conversation
    assert "Summarize the findings" in conversation
    assert "Here is the summary." in conversation
    assert "private" not in conversation
    assert "### Prompt (" in conversation
    assert "### Response (" in conversation
    assert "T+0.00s" in conversation
    assert "T+1.20s" in conversation
    assert "Response concluded at" in conversation
