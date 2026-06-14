from pathlib import Path
import pytest
import re

from agent_bencher.cli import build_parser, main
from agent_bencher.models import AgentConfig, Conversation, Prompt, SessionResult, TokenUsage, TurnResult


def _make_session(*, run_id: str) -> SessionResult:
    return SessionResult(
        run_id=run_id,
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="model-x",
        session_id=f"session-{run_id}",
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
                session_id=f"session-{run_id}",
                exit_code=0,
                duration_seconds=1.0,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            )
        ],
        comment="",
    )


def test_build_parser_defaults_runs_to_one() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["bench", "run_configs/opencode.yaml", "conversations/sample.yaml"])

    assert parsed.runs == 1


def test_build_parser_accepts_runs_arg() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        ["bench", "run_configs/opencode.yaml", "conversations/sample.yaml", "--runs", "3"]
    )

    assert parsed.runs == 3


def test_build_parser_rejects_non_positive_runs() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["bench", "run_configs/opencode.yaml", "conversations/sample.yaml", "--runs", "0"]
        )


def test_main_executes_requested_number_of_trials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    workspaces: list[Path] = []

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / f"hex-{len(workspaces) + 1}"
        path = root / "workspace"
        path.mkdir(parents=True)
        (root / "artifacts").mkdir()
        workspaces.append(path)
        return PreparedWorkspace(path, root / "artifacts")

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)

    sessions = iter([_make_session(run_id="run-1"), _make_session(run_id="run-2"), _make_session(run_id="run-3")])

    def fake_run_conversation(**kwargs):
        return next(sessions)

    captured = {}

    def fake_write_batch_results(*, batch, output_dir: Path) -> None:
        captured["batch"] = batch
        captured["output_dir"] = output_dir

    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", fake_write_batch_results)

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--runs",
            "3",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 0
    assert len(workspaces) == 3
    assert captured["batch"].requested_runs == 3
    assert len(captured["batch"].sessions) == 3
    assert captured["output_dir"].parent.name == "open-fast"


def test_main_deletes_successful_trial_workspaces(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    workspace_roots: list[Path] = []

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / f"hex-{len(workspace_roots) + 1}"
        workspace = root / "workspace"
        artifacts = root / "artifacts"
        workspace.mkdir(parents=True)
        artifacts.mkdir()
        workspace_roots.append(root)
        return PreparedWorkspace(workspace, artifacts)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kwargs: None)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", lambda **kwargs: _make_session(run_id="run-1"))

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 0
    assert workspace_roots
    assert not workspace_roots[0].exists()


def test_main_writes_incremental_trial_artifacts_to_prepared_artifacts_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    artifacts_dir = tmp_path / "hex-1" / "artifacts"

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / "hex-1"
        workspace = root / "workspace"
        workspace.mkdir(parents=True)
        artifacts_dir.mkdir(parents=True)
        return PreparedWorkspace(workspace, artifacts_dir)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kwargs: None)

    checkpoint_paths: list[Path] = []

    def fake_write_trial_results(*, session, output_dir: Path) -> None:
        checkpoint_paths.append(output_dir)

    def fake_run_conversation(**kwargs):
        kwargs["on_turn_completed"](_make_session(run_id="run-1"))
        return _make_session(run_id="run-1")

    monkeypatch.setattr("agent_bencher.cli.write_trial_results", fake_write_trial_results)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 0
    assert checkpoint_paths == [artifacts_dir]


def test_main_keeps_failed_trial_workspaces(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    workspace_roots: list[Path] = []

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / f"hex-{len(workspace_roots) + 1}"
        workspace = root / "workspace"
        artifacts = root / "artifacts"
        workspace.mkdir(parents=True)
        artifacts.mkdir()
        workspace_roots.append(root)
        return PreparedWorkspace(workspace, artifacts)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kwargs: None)

    def failed_session(**kwargs):
        session = _make_session(run_id="run-1")
        session.status = "failed"
        session.prompts_completed = 0
        session.turns[0].exit_code = 1
        return session

    monkeypatch.setattr("agent_bencher.cli.run_conversation", failed_session)

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 0
    assert workspace_roots
    assert workspace_roots[0].exists()


def test_main_prints_run_start_and_end_timestamps(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / "hex-1"
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (root / "artifacts").mkdir(exist_ok=True)
        return PreparedWorkspace(workspace, root / "artifacts")

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kwargs: None)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", lambda **kwargs: _make_session(run_id="run-1"))

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert re.search(r"Run started at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured.err)
    assert re.search(r"Run concluded at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured.err)


def test_main_handles_keyboard_interrupt_with_polite_message(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / "hex-1"
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (root / "artifacts").mkdir(exist_ok=True)
        return PreparedWorkspace(workspace, root / "artifacts")

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kwargs: None)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", lambda **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()))

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 130
    assert "Terminating early at user request" in captured.err
    assert "KeyboardInterrupt" not in captured.err


def test_main_writes_partial_batch_results_before_interrupt(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample-conversation",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="open-fast", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path, artifacts_dir: Path) -> None:
            self.variant_workspace = path
            self.artifacts_dir = artifacts_dir

    workspaces: list[Path] = []

    def fake_prepare_variant_workspace(*, source_workspace: Path, run_root: Path, suite_name: str, variant_id: str):
        root = tmp_path / f"hex-{len(workspaces) + 1}"
        workspace = root / "workspace"
        workspace.mkdir(parents=True)
        (root / "artifacts").mkdir()
        workspaces.append(root)
        return PreparedWorkspace(workspace, root / "artifacts")

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare_variant_workspace)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda _frontend: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda _command: None)

    calls: list[tuple[int, str, int]] = []

    def fake_write_batch_results(*, batch, output_dir: Path) -> None:
        calls.append((len(batch.sessions), batch.status, batch.requested_runs))

    sessions = iter([_make_session(run_id="run-1")])

    def fake_run_conversation(**kwargs):
        if kwargs["run_id"].endswith("trial-001"):
            return next(sessions)
        raise KeyboardInterrupt()

    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", fake_write_batch_results)

    exit_code = main(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--runs",
            "3",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 130
    assert "Terminating early at user request" in captured.err
    assert calls == [(1, "partial", 3), (1, "partial", 3)]
