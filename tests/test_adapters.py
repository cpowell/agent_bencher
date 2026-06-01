from pathlib import Path

from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter
from agent_bencher.models import AgentConfig, Prompt


def test_opencode_start_command_uses_real_cli_shape(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={},
    )

    command = adapter.build_start_command(
        prompt=Prompt(text="Reply with exactly OK"),
        variant=agent,
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


def test_opencode_warmup_command_reuses_model_args_and_env(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={"FOO": "bar"},
    )

    command = adapter.build_warmup_command(variant=agent, workspace=tmp_path)

    assert command.argv == [
        "opencode",
        "run",
        "--format",
        "json",
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "Reply with exactly OK. This is a benchmark warmup run.",
    ]
    assert command.env == {"FOO": "bar"}


def test_claude_parser_reads_usage_and_session_id_from_json_fixture() -> None:
    payload = Path("tests/fixtures/claude-turn.json").read_text()

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-123"
    assert parsed["token_usage"]["input"] == 120
    assert parsed["token_usage"]["output"] == 45


def test_claude_parser_reads_usage_and_session_id_from_json_list_fixture() -> None:
    payload = """
[
  {
    "type": "system",
    "session_id": "claude-session-456"
  },
  {
    "result": {
      "session_id": "claude-session-456",
      "usage": {
        "input_tokens": 210,
        "output_tokens": 80,
        "reasoning_tokens": 5,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0
      }
    }
  }
]
"""

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-456"
    assert parsed["token_usage"]["input"] == 210
    assert parsed["token_usage"]["output"] == 80


def test_claude_parser_tolerates_string_result_entries() -> None:
    payload = """
[
  {
    "type": "system",
    "session_id": "claude-session-789"
  },
  {
    "result": "intermediate text event"
  }
]
"""

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-789"
    assert parsed["token_usage"]["input"] == 0
    assert parsed["token_usage"]["output"] == 0


def test_opencode_parser_reads_usage_and_session_id_from_jsonl_fixture() -> None:
    payload = Path("tests/fixtures/opencode-turn.jsonl").read_text()

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["token_usage"]["input"] == 210
    assert parsed["token_usage"]["output"] == 80


def test_claude_warmup_command_reuses_args_and_env(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    agent = AgentConfig(
        id="claude-fast",
        frontend="claude",
        model="Qwen3.6-27B-4bit",
        args=["--output-format", "json", "--model", "opus"],
        env={"ANTHROPIC_BASE_URL": "http://127.0.0.1:8000"},
    )

    command = adapter.build_warmup_command(variant=agent, workspace=tmp_path)

    assert command.argv == [
        "claude",
        "-p",
        "Reply with exactly OK. This is a benchmark warmup run.",
        "--output-format",
        "json",
        "--model",
        "opus",
    ]
    assert command.env == {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8000"}
