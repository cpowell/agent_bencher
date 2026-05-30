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


def test_claude_parser_reads_usage_and_session_id_from_json_fixture() -> None:
    payload = Path("tests/fixtures/claude-turn.json").read_text()

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-123"
    assert parsed["token_usage"]["input"] == 120
    assert parsed["token_usage"]["output"] == 45


def test_opencode_parser_reads_usage_and_session_id_from_jsonl_fixture() -> None:
    payload = Path("tests/fixtures/opencode-turn.jsonl").read_text()

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["token_usage"]["input"] == 210
    assert parsed["token_usage"]["output"] == 80
