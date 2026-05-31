from dataclasses import dataclass
from pathlib import Path

from agent_bencher.models import AgentConfig, Conversation, Prompt
from agent_bencher.runner import run_conversation


@dataclass
class FakeCompletedRun:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def build_start_command(self, *, prompt, variant, workspace):
        self.calls.append(("start", None))
        return object()

    def build_continue_command(self, *, prompt, variant, workspace, session_id):
        self.calls.append(("continue", session_id))
        return object()

    def parse_turn_output(self, *, stdout: str, stderr: str):
        return {
            "session_id": "session-123",
            "token_usage": {"input": 10, "output": 5},
            "warnings": [],
        }


def test_run_conversation_reuses_session_id_across_prompts(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[
            Prompt(id="one", text="Do this"),
            Prompt(id="two", text="Explain that"),
        ],
    )
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
    )
    adapter = FakeAdapter()

    def fake_runner(_command):
        return FakeCompletedRun(
            stdout='{"session_id":"session-123"}',
            stderr="",
            exit_code=0,
            duration_seconds=1.5,
        )

    result = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=tmp_path,
        adapter=adapter,
        run_command=fake_runner,
        run_id="2026-05-31T14-26-00",
        started_at="2026-05-31T14:26:00Z",
    )

    assert adapter.calls == [("start", None), ("continue", "session-123")]
    assert result.prompts_attempted == 2
    assert result.prompts_completed == 2
    assert result.turns[1].session_id == "session-123"


def test_run_conversation_records_status_and_execution_timestamps(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[Prompt(id="one", text="Do this")],
    )
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
    )
    adapter = FakeAdapter()

    def fake_runner(_command):
        return FakeCompletedRun(
            stdout='{"session_id":"session-123"}',
            stderr="",
            exit_code=0,
            duration_seconds=1.5,
        )

    result = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=tmp_path,
        adapter=adapter,
        run_command=fake_runner,
        run_id="2026-05-31T14-26-00",
        started_at="2026-05-31T14:26:00Z",
    )

    assert result.status == "completed"
    assert result.started_at
    assert result.ended_at
    assert result.duration_seconds == 1.5


def test_run_conversation_uses_agent_execution_time_not_bookkeeping(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[Prompt(id="one", text="Do this"), Prompt(id="two", text="Explain that")],
    )
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
    )
    adapter = FakeAdapter()

    calls = iter(
        [
            FakeCompletedRun(stdout='{"session_id":"session-123"}', stderr="", exit_code=0, duration_seconds=1.5),
            FakeCompletedRun(stdout='{"session_id":"session-123"}', stderr="", exit_code=0, duration_seconds=2.0),
        ]
    )

    result = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=tmp_path,
        adapter=adapter,
        run_command=lambda _command: next(calls),
        run_id="2026-05-31T14-26-00",
        started_at="2026-05-31T14:26:00Z",
    )

    assert result.duration_seconds == 3.5
