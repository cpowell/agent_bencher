from pathlib import Path

from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter
from agent_bencher.models import Prompt, Variant


def test_opencode_start_command_uses_real_cli_shape(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    variant = Variant(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={},
    )

    command = adapter.build_start_command(
        prompt=Prompt(id="intro", text="Reply with exactly OK"),
        variant=variant,
        workspace=tmp_path,
    )

    assert command.argv == [
        "opencode",
        "run",
        "--format",
        "json",
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "Reply with exactly OK",
    ]
    assert command.cwd == tmp_path


def test_claude_start_command_keeps_env_and_model_flag(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    variant = Variant(
        id="claude-opus",
        frontend="claude",
        model="Qwen3.6-27B-4bit",
        args=["--output-format", "json", "--permission-mode", "bypassPermissions", "--model", "opus"],
        env={
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
            "ANTHROPIC_AUTH_TOKEN": "cbp8",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "Qwen3.6-27B-4bit",
        },
    )

    command = adapter.build_start_command(
        prompt=Prompt(id="intro", text="Reply with exactly OK"),
        variant=variant,
        workspace=tmp_path,
    )

    assert command.argv == [
        "claude",
        "-p",
        "Reply with exactly OK",
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        "opus",
    ]
    assert command.env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "Qwen3.6-27B-4bit"
    assert command.cwd == tmp_path
