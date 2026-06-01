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
    started_at: str
    ended_at: str


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.workspaces: list[tuple[str, Path]] = []
        self.fatal_error: str | None = None

    def build_start_command(self, *, prompt, variant, workspace):
        self.calls.append(("start", None))
        self.workspaces.append(("start", workspace))
        return object()

    def build_continue_command(self, *, prompt, variant, workspace, session_id):
        self.calls.append(("continue", session_id))
        self.workspaces.append(("continue", workspace))
        return object()

    def parse_turn_output(self, *, stdout: str, stderr: str):
        return {
            "session_id": "session-123",
            "token_usage": {"input": 10, "output": 5},
            "warnings": [],
            "fatal_error": self.fatal_error,
        }


def test_run_conversation_reuses_session_id_across_prompts(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[
            Prompt(text="Do this"),
            Prompt(text="Explain that"),
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
            started_at="2026-05-31T14:26:00Z",
            ended_at="2026-05-31T14:26:01.500000Z",
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
    assert adapter.workspaces[0][1] == tmp_path
    assert adapter.workspaces[1][1] == tmp_path
    assert result.prompts_attempted == 2
    assert result.prompts_completed == 2
    assert result.turns[0].started_at == "2026-05-31T14:26:00Z"
    assert result.turns[0].ended_at == "2026-05-31T14:26:01.500000Z"
    assert result.turns[0].prompt_id == "01"
    assert result.turns[1].session_id == "session-123"
    assert result.turns[1].prompt_id == "02"


def test_run_conversation_records_status_and_execution_timestamps(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[Prompt(text="Do this")],
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
            started_at="2026-05-31T14:26:00Z",
            ended_at="2026-05-31T14:26:01.500000Z",
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
    assert result.turns[0].started_at == "2026-05-31T14:26:00Z"
    assert result.turns[0].ended_at == "2026-05-31T14:26:01.500000Z"


def test_run_conversation_uses_agent_execution_time_not_bookkeeping(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[Prompt(text="Do this"), Prompt(text="Explain that")],
    )
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
    )
    adapter = FakeAdapter()

    calls = iter(
        [
            FakeCompletedRun(
                stdout='{"session_id":"session-123"}',
                stderr="",
                exit_code=0,
                duration_seconds=1.5,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:01.500000Z",
            ),
            FakeCompletedRun(
                stdout='{"session_id":"session-123"}',
                stderr="",
                exit_code=0,
                duration_seconds=2.0,
                started_at="2026-05-31T14:26:01.500000Z",
                ended_at="2026-05-31T14:26:03.500000Z",
            ),
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


def test_run_conversation_aborts_when_adapter_reports_fatal_turn_error(tmp_path: Path) -> None:
    conversation = Conversation(
        name="sample",
        source_workspace=tmp_path,
        prompts=[Prompt(text="Do this")],
    )
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
    )
    adapter = FakeAdapter()
    adapter.fatal_error = "UnknownError: boom"

    calls = iter(
        [
            FakeCompletedRun(
                stdout='{"session_id":"session-123"}',
                stderr="",
                exit_code=0,
                duration_seconds=1.5,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:01.500000Z",
            ),
        ]
    )

    try:
        run_conversation(
            conversation=conversation,
            agent=agent,
            workspace=tmp_path,
            adapter=adapter,
            run_command=lambda _command: next(calls),
            run_id="2026-05-31T14-26-00",
            started_at="2026-05-31T14:26:00Z",
        )
    except RuntimeError as error:
        message = str(error)
        assert "turn 1 failed" in message
        assert "frontend: opencode" in message
        assert "model: mtplx/mtplx-qwen36-27b-optimized-speed" in message
        assert "prompt: Do this" in message
        assert "error: UnknownError: boom" in message
        assert 'stdout: {"session_id":"session-123"}' in message
    else:
        raise AssertionError("expected fatal turn error to abort the benchmark")
