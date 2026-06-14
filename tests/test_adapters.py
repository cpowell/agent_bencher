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
        "--dir",
        str(tmp_path.resolve()),
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "Reply with exactly OK",
    ]


def test_opencode_continue_command_pins_workspace_dir(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    agent = AgentConfig(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={},
    )

    command = adapter.build_continue_command(
        prompt=Prompt(text="Continue"),
        variant=agent,
        workspace=tmp_path,
        session_id="session-123",
    )

    assert command.argv == [
        "opencode",
        "run",
        "--format",
        "json",
        "--dir",
        str(tmp_path.resolve()),
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "--session",
        "session-123",
        "Continue",
    ]



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


def test_claude_parser_recovers_usage_from_malformed_json() -> None:
    payload = """
{
  "session_id": "claude-session-broken",
  "result": {
    "session_id": "claude-session-broken",
    "usage": {
      "input_tokens": 321,
      "output_tokens": 123,
      "reasoning_tokens": 7,
      "cache_read_input_tokens": 11,
      "cache_creation_input_tokens": 13
    },
    "text": "unterminated
"""

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-broken"
    assert parsed["token_usage"]["input"] == 321
    assert parsed["token_usage"]["output"] == 123
    assert parsed["token_usage"]["reasoning"] == 7
    assert parsed["token_usage"]["cache_read"] == 11
    assert parsed["token_usage"]["cache_write"] == 13


def test_claude_parser_surfaces_unrecoverable_malformed_json_as_fatal() -> None:
    payload = '{"text": "unterminated'

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == ""
    assert parsed["fatal_error"].startswith("ClaudeOutputParseError:")


def test_opencode_parser_reads_usage_and_session_id_from_jsonl_fixture() -> None:
    payload = Path("tests/fixtures/opencode-turn.jsonl").read_text()

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["token_usage"]["input"] == 210
    assert parsed["token_usage"]["output"] == 80


def test_opencode_parser_surfaces_error_events_as_fatal() -> None:
    payload = """
{"type":"step_start","sessionID":"opencode-session-123","part":{"type":"step-start"}}
{"type":"error","sessionID":"opencode-session-123","error":{"name":"UnknownError","data":{"message":"boom"}}}
"""

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["fatal_error"] == "UnknownError: boom"


def test_opencode_parser_surfaces_malformed_json_line_with_exact_output() -> None:
    payload = """
{"type":"step_start","sessionID":"opencode-session-123","part":{"type":"step-start"}}
Hi there
"""

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["warnings"] == ["malformed-opencode-jsonl"]
    assert parsed["fatal_error"] == (
        "OpenCodeOutputParseError: Expecting value at column 1; offending line: 'Hi there'"
    )


def test_opencode_parser_reports_exact_malformed_json_syntax() -> None:
    payload = "{'broken': true}"

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == ""
    assert parsed["warnings"] == ["malformed-opencode-jsonl"]
    assert parsed["fatal_error"] == (
        'OpenCodeOutputParseError: Expecting property name enclosed in double quotes '
        'at column 2; offending line: "{\'broken\': true}"'
    )


def test_opencode_parser_rewrites_provider_model_not_found_into_corrective_error() -> None:
    payload = """
[07:03:02.484] ERROR (#10949): failed {
  ref: "err_2d043162",
  error: {
    providerID: "omlx",
    modelID: "Qwen3.6-35B-A3B-oQ6-fp16-mtp",
    suggestions: [ "Qwen3.6-35B-A3B-6bit", "Qwen3.6-27B-MLX-6bit" ],
    _tag: "ProviderModelNotFoundError",
  },
  cause: "ProviderModelNotFoundError: ...",
}
"""

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == ""
    assert parsed["warnings"] == ["malformed-opencode-jsonl"]
    assert parsed["fatal_error"] == (
        "OpenCodeProviderError: omlx model 'Qwen3.6-35B-A3B-oQ6-fp16-mtp' not found; "
        "suggestions: Qwen3.6-35B-A3B-6bit, Qwen3.6-27B-MLX-6bit"
    )
