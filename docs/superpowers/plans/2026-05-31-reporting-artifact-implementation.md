# Reporting Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor benchmark output into immutable per-run directories with concise machine-readable artifacts (`run.json` and `turns.jsonl`) that a future reporting interface can ingest directly.

**Architecture:** The runner keeps producing human-facing artifacts, but `results.py` becomes responsible for a clearer run-directory layout and a dedicated analytics shape. Timing data is computed from agent execution only, while output persistence and transcript generation happen afterward and write into one run-scoped artifact directory.

**Tech Stack:** Python 3.14, `dataclasses`, `json`, `pathlib`, `datetime`, `pytest`

---

## File Structure

### Source files

- Modify: `src/agent_bencher/models.py`
  - Add run-level fields needed for concise reporting output
- Modify: `src/agent_bencher/process.py`
  - Capture timestamp metadata alongside execution duration
- Modify: `src/agent_bencher/runner.py`
  - Produce run-level timing and status data without including bookkeeping time
- Modify: `src/agent_bencher/cli.py`
  - Allocate a timestamp-based run id and write into `runs/<conversation>/<agent>/<run-id>/`
- Modify: `src/agent_bencher/results.py`
  - Write `run.json`, `turns.jsonl`, `summary.md`, `conversation.md`, and transcripts into the run directory
- Modify: `src/agent_bencher/report.py`
  - Point human-facing links and summaries at the new per-run layout

### Tests

- Modify: `tests/test_runner.py`
  - Assert run-level status and timing fields
- Modify: `tests/test_report.py`
  - Assert summary output still points at human-facing artifacts correctly
- Create: `tests/test_results.py`
  - Assert new run artifact layout, compact `run.json`, and `turns.jsonl` contents

## Task 1: Add Run Metadata To The Result Models

**Files:**
- Modify: `src/agent_bencher/models.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Write the failing runner metadata test**

Append this test to `tests/test_runner.py`:

```python
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
    )

    assert result.status == "completed"
    assert result.started_at
    assert result.ended_at
    assert result.duration_seconds == 1.5
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_runner.py::test_run_conversation_records_status_and_execution_timestamps -v
```

Expected: FAIL with `AttributeError` because `SessionResult` does not yet expose `status`, `started_at`, `ended_at`, or `duration_seconds`

- [ ] **Step 3: Extend the result models with run-level metadata**

Replace `src/agent_bencher/models.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Prompt:
    id: str
    text: str


@dataclass(slots=True)
class AgentConfig:
    id: str
    frontend: str
    model: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Conversation:
    name: str
    source_workspace: Path
    prompts: list[Prompt]


@dataclass(slots=True)
class TokenUsage:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


@dataclass(slots=True)
class TurnResult:
    prompt_id: str
    prompt_text: str
    session_id: str
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    token_usage: TokenUsage
    stdout_path: str = ""
    stderr_path: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionResult:
    run_id: str
    conversation_name: str
    agent_id: str
    frontend: str
    backend_model: str
    session_id: str
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    prompts_attempted: int
    prompts_completed: int
    turns: list[TurnResult]
```

- [ ] **Step 4: Update the existing runner fixture construction to match the expanded model**

Replace the `SessionResult(...)` block in `tests/test_report.py` with:

```python
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
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            ),
            TurnResult(
                prompt_id="explain",
                prompt_text="Explain that",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=2.3,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=210, output=80),
            ),
        ],
    )
```

- [ ] **Step 5: Run the targeted tests to verify the model change passes**

Run:

```bash
uv run pytest tests/test_runner.py tests/test_report.py -v
```

Expected: FAIL only in the new runner test because `run_conversation()` does not yet populate the new fields

- [ ] **Step 6: Commit the model expansion**

Suggested commit text for the user:

```text
refactor: add run-level benchmark metadata
Extend session results with run ids, timestamps, duration, and status so later artifact writing can emit concise reporting-oriented records.
```

## Task 2: Measure Execution-Only Timing In The Runner

**Files:**
- Modify: `src/agent_bencher/process.py`
- Modify: `src/agent_bencher/runner.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Write the failing execution-timing test**

Append this test to `tests/test_runner.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_runner.py::test_run_conversation_uses_agent_execution_time_not_bookkeeping -v
```

Expected: FAIL because `run_conversation()` does not yet accept `run_id` and `started_at`

- [ ] **Step 3: Thread run metadata into the runner and compute execution-only status**

Replace `src/agent_bencher/runner.py` with:

```python
from __future__ import annotations

from pathlib import Path

from agent_bencher.models import AgentConfig, Conversation, SessionResult, TokenUsage, TurnResult


def run_conversation(
    *,
    conversation: Conversation,
    agent: AgentConfig,
    workspace: Path,
    adapter,
    run_command,
    run_id: str,
    started_at: str,
):
    turns: list[TurnResult] = []
    session_id = ""
    execution_duration = 0.0

    for index, prompt in enumerate(conversation.prompts):
        if index == 0:
            command = adapter.build_start_command(prompt=prompt, variant=agent, workspace=workspace)
        else:
            command = adapter.build_continue_command(
                prompt=prompt,
                variant=agent,
                workspace=workspace,
                session_id=session_id,
            )

        completed = run_command(command)
        parsed = adapter.parse_turn_output(stdout=completed.stdout, stderr=completed.stderr)
        session_id = parsed["session_id"]
        execution_duration += completed.duration_seconds

        turns.append(
            TurnResult(
                prompt_id=prompt.id,
                prompt_text=prompt.text,
                session_id=session_id,
                exit_code=completed.exit_code,
                duration_seconds=completed.duration_seconds,
                stdout=completed.stdout,
                stderr=completed.stderr,
                token_usage=TokenUsage(**parsed["token_usage"]),
                warnings=list(parsed["warnings"]),
            )
        )

        if completed.exit_code != 0:
            break

    status = "completed" if len(turns) == len(conversation.prompts) and all(turn.exit_code == 0 for turn in turns) else "partial"
    if turns and turns[-1].exit_code != 0:
        status = "failed"

    return SessionResult(
        run_id=run_id,
        conversation_name=conversation.name,
        agent_id=agent.id,
        frontend=agent.frontend,
        backend_model=agent.model,
        session_id=session_id,
        started_at=started_at,
        ended_at=started_at,
        duration_seconds=execution_duration,
        status=status,
        prompts_attempted=len(turns),
        prompts_completed=sum(1 for turn in turns if turn.exit_code == 0),
        turns=turns,
    )
```

- [ ] **Step 4: Run the runner tests to verify execution-only duration passes**

Run:

```bash
uv run pytest tests/test_runner.py -v
```

Expected: PASS for the timing assertions

- [ ] **Step 5: Commit the execution-timing slice**

Suggested commit text for the user:

```text
feat: record execution-only benchmark timing
Compute run duration strictly from agent subprocess execution so setup and artifact bookkeeping remain outside the primary benchmark metrics.
```

## Task 3: Introduce Timestamped Run Directories

**Files:**
- Modify: `src/agent_bencher/cli.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Write the failing parser and run-path test**

Append this test to `tests/test_report.py`:

```python
def test_build_parser_accepts_conversation_and_agent_args() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        [
            "bench",
            "run_configs/opencode.yaml",
            "conversations/sample.yaml",
            "--output-dir",
            "runs",
        ]
    )

    assert parsed.command == "bench"
    assert parsed.conversation == Path("conversations/sample.yaml")
    assert parsed.run_config == Path("run_configs/opencode.yaml")
    assert parsed.output_dir == Path("runs")
```

- [ ] **Step 2: Run the test to verify the current CLI still passes parsing but not run-id behavior**

Run:

```bash
uv run pytest tests/test_report.py::test_build_parser_accepts_conversation_and_agent_args -v
```

Expected: PASS

- [ ] **Step 3: Add a focused CLI helper test for timestamp-style run ids**

Append this test to `tests/test_report.py`:

```python
from agent_bencher.cli import format_run_id


def test_format_run_id_uses_cross_platform_timestamp() -> None:
    assert format_run_id("2026-05-31", "14:26:00") == "2026-05-31T14-26-00"
```

- [ ] **Step 4: Run the new test to verify it fails**

Run:

```bash
uv run pytest tests/test_report.py::test_format_run_id_uses_cross_platform_timestamp -v
```

Expected: FAIL because `format_run_id` does not exist yet

- [ ] **Step 5: Update the CLI to create one immutable run directory per invocation**

Replace `src/agent_bencher/cli.py` with:

```python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from agent_bencher.adapters import get_adapter
from agent_bencher.process import run_command
from agent_bencher.results import write_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import prepare_variant_workspace


def format_run_id(date_part: str, time_part: str) -> str:
    return f"{date_part}T{time_part.replace(':', '-')}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m agent_bencher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("run_config", type=Path)
    bench.add_argument("conversation", type=Path)
    bench.add_argument("--output-dir", type=Path, default=Path("runs"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")

    conversation = load_conversation(args.conversation)
    agent = load_agent_config(args.run_config)

    now = datetime.now(timezone.utc)
    run_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    started_at = now.isoformat()
    run_output_dir = args.output_dir / conversation.name / agent.id / run_id

    prepared = prepare_variant_workspace(
        source_workspace=conversation.source_workspace,
        run_root=args.output_dir,
        suite_name=conversation.name,
        variant_id=agent.id,
    )
    adapter = get_adapter(agent.frontend)
    session = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=prepared.variant_workspace,
        adapter=adapter,
        run_command=run_command,
        run_id=run_id,
        started_at=started_at,
    )

    write_results(sessions=[session], output_dir=run_output_dir)
    return 0
```

- [ ] **Step 6: Run the report-oriented tests**

Run:

```bash
uv run pytest tests/test_report.py -v
```

Expected: PASS for parser and run-id helper assertions

- [ ] **Step 7: Commit the immutable-run-directory slice**

Suggested commit text for the user:

```text
feat: write benchmark outputs into immutable run directories
Create one timestamped run directory per invocation so repeated benchmarks never overwrite prior results and future reporters can sweep historical runs safely.
```

## Task 4: Write Compact `run.json` And Per-Turn `turns.jsonl`

**Files:**
- Create: `tests/test_results.py`
- Modify: `src/agent_bencher/results.py`

- [ ] **Step 1: Write the failing artifact-shape test**

Create `tests/test_results.py`:

```python
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
    assert "stdout" not in run_payload["turns"][0]
    assert len(turns_lines) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_results.py::test_write_results_emits_compact_run_json_and_turns_jsonl -v
```

Expected: FAIL because `write_results()` still writes `json/<agent>.json` and does not emit `turns.jsonl`

- [ ] **Step 3: Refactor result writing to emit compact machine-readable artifacts**

Replace `src/agent_bencher/results.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.models import SessionResult, TurnResult
from agent_bencher.report import build_markdown_report


def _write_turn_transcripts(*, output_dir: Path, turn: TurnResult, turn_index: int) -> None:
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stdout.txt"
    stderr_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stderr.txt"

    stdout_path.write_text(turn.stdout)
    stderr_path.write_text(turn.stderr)

    turn.stdout_path = str(stdout_path)
    turn.stderr_path = str(stderr_path)


def _serialize_turn(turn: TurnResult, *, run_id: str, turn_index: int) -> dict:
    return {
        "run_id": run_id,
        "turn_index": turn_index,
        "prompt_id": turn.prompt_id,
        "prompt_text": turn.prompt_text,
        "session_id": turn.session_id,
        "exit_code": turn.exit_code,
        "duration_seconds": turn.duration_seconds,
        "input_tokens": turn.token_usage.input,
        "output_tokens": turn.token_usage.output,
        "reasoning_tokens": turn.token_usage.reasoning,
        "cache_read_tokens": turn.token_usage.cache_read,
        "cache_write_tokens": turn.token_usage.cache_write,
        "stdout_path": turn.stdout_path,
        "stderr_path": turn.stderr_path,
        "warnings": list(turn.warnings),
    }


def _serialize_run(session: SessionResult, *, conversation_path: str, transcript_dir: str) -> dict:
    return {
        "run_id": session.run_id,
        "conversation_name": session.conversation_name,
        "agent_id": session.agent_id,
        "frontend": session.frontend,
        "backend_model": session.backend_model,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "duration_seconds": session.duration_seconds,
        "prompts_attempted": session.prompts_attempted,
        "prompts_completed": session.prompts_completed,
        "session_id": session.session_id,
        "status": session.status,
        "total_input_tokens": sum(turn.token_usage.input for turn in session.turns),
        "total_output_tokens": sum(turn.token_usage.output for turn in session.turns),
        "total_reasoning_tokens": sum(turn.token_usage.reasoning for turn in session.turns),
        "total_cache_read_tokens": sum(turn.token_usage.cache_read for turn in session.turns),
        "total_cache_write_tokens": sum(turn.token_usage.cache_write for turn in session.turns),
        "conversation_path": conversation_path,
        "transcript_dir": transcript_dir,
    }


def _write_combined_conversation_artifact(*, output_dir: Path, session: SessionResult) -> Path:
    destination = output_dir / "conversation.md"
    destination.write_text(f"# {session.conversation_name}\n")
    return destination


def write_results(*, sessions: list[SessionResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        for turn_index, turn in enumerate(session.turns, start=1):
            _write_turn_transcripts(output_dir=output_dir, turn=turn, turn_index=turn_index)

        conversation_path = str(_write_combined_conversation_artifact(output_dir=output_dir, session=session))
        transcript_dir = str(output_dir / "transcripts")

        turns_destination = output_dir / "turns.jsonl"
        turns_destination.write_text(
            "\n".join(
                json.dumps(_serialize_turn(turn, run_id=session.run_id, turn_index=index))
                for index, turn in enumerate(session.turns, start=1)
            )
            + "\n"
        )

        run_destination = output_dir / "run.json"
        run_destination.write_text(
            json.dumps(_serialize_run(session, conversation_path=conversation_path, transcript_dir=transcript_dir), indent=2)
        )

    (output_dir / "summary.md").write_text(build_markdown_report(sessions))
```

- [ ] **Step 4: Run the result-writing test to verify it passes**

Run:

```bash
uv run pytest tests/test_results.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the machine-readable artifact slice**

Suggested commit text for the user:

```text
feat: emit reporting-friendly run artifacts
Write one compact run.json and one turns.jsonl per benchmark invocation so future reporting tools can ingest stable run and turn records without parsing human-facing files.
```

## Task 5: Update Human-Facing Summary To Match The New Artifact Layout

**Files:**
- Modify: `src/agent_bencher/report.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Write the failing summary expectation**

Append this test to `tests/test_report.py`:

```python
def test_build_markdown_report_points_to_run_artifacts() -> None:
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
        turns=[],
    )

    report = build_markdown_report([session])

    assert "conversation.md" in report
    assert "run.json" in report
    assert "turns.jsonl" in report
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_report.py::test_build_markdown_report_points_to_run_artifacts -v
```

Expected: FAIL because the current report does not mention `run.json` or `turns.jsonl`

- [ ] **Step 3: Update the Markdown summary format**

Replace `src/agent_bencher/report.py` with:

```python
from __future__ import annotations

from agent_bencher.models import SessionResult


def build_markdown_report(sessions: list[SessionResult]) -> str:
    lines = ["# Benchmark Summary", ""]

    for session in sessions:
        total_input = sum(turn.token_usage.input for turn in session.turns)
        total_output = sum(turn.token_usage.output for turn in session.turns)

        lines.extend(
            [
                f"## {session.agent_id}",
                f"- run id: {session.run_id}",
                f"- frontend: {session.frontend}",
                f"- backend model: {session.backend_model}",
                f"- conversation: {session.conversation_name}",
                f"- session id: {session.session_id}",
                f"- status: {session.status}",
                f"- completed {session.prompts_completed}/{session.prompts_attempted} prompts",
                f"- duration: {session.duration_seconds:.2f}s",
                f"- total input tokens: {total_input}",
                f"- total output tokens: {total_output}",
                f"- run summary: run.json",
                f"- turn records: turns.jsonl",
                f"- combined conversation: conversation.md",
                "",
                "| Turn | Prompt | Duration (s) | Input | Output | Stdout | Stderr |",
                "| --- | --- | ---: | ---: | ---: | --- | --- |",
            ]
        )

        for turn_index, turn in enumerate(session.turns, start=1):
            lines.append(
                f"| {turn_index} | {turn.prompt_id} | {turn.duration_seconds:.2f} | "
                f"{turn.token_usage.input} | {turn.token_usage.output} | "
                f"`{turn.stdout_path or 'transcripts/pending'}` | `{turn.stderr_path or 'transcripts/pending'}` |"
            )
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run the report tests**

Run:

```bash
uv run pytest tests/test_report.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the summary alignment slice**

Suggested commit text for the user:

```text
refactor: align summary markdown with new run artifacts
Point the human-facing summary at run.json, turns.jsonl, conversation.md, and transcript files so readers and future tooling see one consistent artifact layout.
```

## Self-Review Coverage

- Spec coverage:
  - immutable per-run directories: Task 3
  - compact `run.json`: Task 4
  - per-turn `turns.jsonl`: Task 4
  - timing excludes bookkeeping: Task 2
  - failed/partial status model: Task 2
  - human-facing artifacts remain alongside machine-facing ones: Tasks 4 and 5
- Placeholder scan:
  - no red-flag placeholder filler remains
- Type consistency:
  - `AgentConfig`, `Conversation`, `SessionResult`, `TurnResult`, `run_id`, `started_at`, `ended_at`, `status`, `run.json`, and `turns.jsonl` are named consistently throughout the plan
