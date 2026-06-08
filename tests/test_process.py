from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.process import CompletedRun, run_command


def test_run_command_captures_stdout_stderr_and_exit_code() -> None:
    cmd = CommandSpec(argv=["echo", "hello"], cwd=Path("/tmp"))
    mock_result = MagicMock()
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result):
        result = run_command(cmd)

    assert isinstance(result, CompletedRun)
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_run_command_propagates_nonzero_exit_code() -> None:
    cmd = CommandSpec(argv=["false"], cwd=Path("/tmp"))
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = "error\n"
    mock_result.returncode = 1

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result):
        result = run_command(cmd)

    assert result.exit_code == 1
    assert result.stderr == "error\n"


def test_run_command_injects_environment_variables() -> None:
    cmd = CommandSpec(
        argv=["env"],
        cwd=Path("/tmp"),
        env={"MY_VAR": "my_value", "ANOTHER": "42"},
    )
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result) as mock_run, \
         patch("agent_bencher.process.os.environ", {"PATH": "/usr/bin"}):
        run_command(cmd)

    call_env = mock_run.call_args.kwargs["env"]
    assert call_env["MY_VAR"] == "my_value"
    assert call_env["ANOTHER"] == "42"
    assert call_env["PATH"] == "/usr/bin"


def test_run_command_uses_specified_working_directory() -> None:
    cmd = CommandSpec(argv=["ls"], cwd=Path("/custom/dir"))
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result) as mock_run:
        run_command(cmd)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["cwd"] == Path("/custom/dir")


def test_run_command_passes_argv_correctly() -> None:
    cmd = CommandSpec(argv=["opencode", "run", "-m", "gpt-4"], cwd=Path("/tmp"))
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result) as mock_run:
        run_command(cmd)

    assert mock_run.call_args.args[0] == ["opencode", "run", "-m", "gpt-4"]


def test_run_command_measures_duration() -> None:
    cmd = CommandSpec(argv=["sleep", "0.1"], cwd=Path("/tmp"))
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result), \
         patch("agent_bencher.process.time.monotonic", side_effect=[0.0, 1.5]):
        result = run_command(cmd)

    assert result.duration_seconds == 1.5


def test_run_command_records_utc_timestamps() -> None:
    cmd = CommandSpec(argv=["echo"], cwd=Path("/tmp"))
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("agent_bencher.process.subprocess.run", return_value=mock_result), \
         patch("agent_bencher.process.time.monotonic", side_effect=[0.0, 0.5]):
        result = run_command(cmd)

    assert result.started_at
    assert result.ended_at
    assert result.started_at <= result.ended_at
