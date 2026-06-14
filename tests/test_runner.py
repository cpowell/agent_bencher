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


class FakeProgressBar:
    def __init__(self, *, total: int, disable: bool, unit: str) -> None:
        self.total = total
        self.disable = disable
        self.unit = unit
        self.descriptions: list[str] = []
        self.updated: list[int] = []
        self.closed = False

    def set_description_str(self, value: str) -> None:
        self.descriptions.append(value)

    def update(self, value: int) -> None:
        self.updated.append(value)

    def close(self) -> None:
        self.closed = True


class FakeProgressFactory:
    def __init__(self) -> None:
        self.created: list[FakeProgressBar] = []

    def __call__(self, *, total: int, disable: bool, unit: str) -> FakeProgressBar:
        bar = FakeProgressBar(total=total, disable=disable, unit=unit)
        self.created.append(bar)
        return bar


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


def test_run_conversation_reports_prompt_progress(tmp_path: Path) -> None:
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
    progress_factory = FakeProgressFactory()

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

    run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=tmp_path,
        adapter=adapter,
        run_command=lambda _command: next(calls),
        run_id="2026-05-31T14-26-00",
        started_at="2026-05-31T14:26:00Z",
        progress_factory=progress_factory,
    )

    assert len(progress_factory.created) == 1
    progress_bar = progress_factory.created[0]
    assert progress_bar.total == 2
    assert progress_bar.unit == "prompt"
    assert progress_bar.descriptions == [
        "prompt 1/2: Do this",
        "prompt 2/2: Explain that",
    ]
    assert progress_bar.updated == [1, 1]
    assert progress_bar.closed is True


def test_run_conversation_closes_progress_bar_after_nonzero_exit(tmp_path: Path) -> None:
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
    progress_factory = FakeProgressFactory()

    calls = iter(
        [
            FakeCompletedRun(
                stdout='{"session_id":"session-123"}',
                stderr="",
                exit_code=1,
                duration_seconds=1.5,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:01.500000Z",
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
        progress_factory=progress_factory,
    )

    progress_bar = progress_factory.created[0]
    assert result.status == "failed"
    assert progress_bar.updated == [1]
    assert progress_bar.closed is True


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


def test_run_conversation_records_failed_turn_when_adapter_reports_fatal_turn_error(tmp_path: Path) -> None:
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

    result = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=tmp_path,
        adapter=adapter,
        run_command=lambda _command: next(calls),
        run_id="2026-05-31T14-26-00",
        started_at="2026-05-31T14:26:00Z",
    )

    assert result.status == "failed"
    assert result.prompts_attempted == 1
    assert result.prompts_completed == 0
    assert result.turns[0].exit_code == 1
    assert "turn 1 failed" in result.turns[0].fatal_error
    assert "frontend: opencode" in result.turns[0].fatal_error
    assert "model: mtplx/mtplx-qwen36-27b-optimized-speed" in result.turns[0].fatal_error
    assert "prompt: Do this" in result.turns[0].fatal_error
    assert "error: UnknownError: boom" in result.turns[0].fatal_error
    assert 'stdout: {"session_id":"session-123"}' in result.turns[0].fatal_error


def test_run_conversation_emits_incremental_checkpoints(tmp_path: Path) -> None:
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
    checkpoints: list[SessionResult] = []

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
        on_turn_completed=checkpoints.append,
    )

    assert result.status == "completed"
    assert len(checkpoints) == 2
    assert checkpoints[0].status == "partial"
    assert checkpoints[0].prompts_attempted == 1
    assert checkpoints[0].prompts_completed == 1
    assert len(checkpoints[0].turns) == 1
    assert checkpoints[1].status == "completed"
    assert checkpoints[1].prompts_attempted == 2
    assert checkpoints[1].prompts_completed == 2
    assert len(checkpoints[1].turns) == 2
