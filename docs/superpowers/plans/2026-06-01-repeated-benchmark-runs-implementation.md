# Repeated Benchmark Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--runs` to `agent-bencher bench` so one invocation executes repeated trials and writes a batch-first artifact layout with aggregate statistics across successful trials.

**Architecture:** Keep one-trial execution centered on the existing `SessionResult` flow, then add a batch layer above it that orchestrates repeated trials, computes aggregate metrics, and writes batch-level artifacts. Preserve current per-trial artifacts under `trials/trial-XXX/` while making the batch root the new primary report location.

**Tech Stack:** Python 3.12+, argparse, dataclasses, pathlib, pytest, PyYAML, tqdm

---

### Task 1: Add Batch Data Models And Aggregate Calculations

**Files:**
- Modify: `src/agent_bencher/models.py`
- Create: `src/agent_bencher/batch.py`
- Test: `tests/test_batch.py`

- [x] **Step 1: Write the failing tests**

```python
from agent_bencher.batch import build_batch_result
from agent_bencher.models import SessionResult, TokenUsage, TurnResult


def make_session(*, run_id: str, status: str, duration: float, input_tokens: int, output_tokens: int) -> SessionResult:
    return SessionResult(
        run_id=run_id,
        conversation_name="sample",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="model-x",
        session_id=f"session-{run_id}",
        started_at="2026-06-01T00:00:00Z",
        ended_at="2026-06-01T00:00:01Z",
        duration_seconds=duration,
        status=status,
        prompts_attempted=1,
        prompts_completed=1 if status == "completed" else 0,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id=f"session-{run_id}",
                exit_code=0 if status == "completed" else 1,
                duration_seconds=duration,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=input_tokens, output=output_tokens),
            )
        ],
        comment="",
    )


def test_build_batch_result_aggregates_successful_trials_only() -> None:
    batch = build_batch_result(
        batch_id="2026-06-01T12-00-00",
        requested_runs=3,
        comment="",
        sessions=[
            make_session(run_id="r1", status="completed", duration=10.0, input_tokens=100, output_tokens=50),
            make_session(run_id="r2", status="failed", duration=20.0, input_tokens=999, output_tokens=1),
            make_session(run_id="r3", status="completed", duration=14.0, input_tokens=140, output_tokens=70),
        ],
    )

    assert batch.status == "partial"
    assert batch.successful_runs == 2
    assert batch.failed_runs == 1
    assert batch.run_metrics["duration_seconds"]["mean"] == 12.0
    assert batch.run_metrics["total_input_tokens"]["min"] == 100
    assert batch.run_metrics["total_input_tokens"]["max"] == 140
    assert batch.turn_metrics[0]["input_tokens"]["mean"] == 120.0


def test_build_batch_result_uses_zero_stddev_for_single_success() -> None:
    batch = build_batch_result(
        batch_id="2026-06-01T12-00-00",
        requested_runs=2,
        comment="",
        sessions=[
            make_session(run_id="r1", status="completed", duration=10.0, input_tokens=100, output_tokens=50),
            make_session(run_id="r2", status="failed", duration=20.0, input_tokens=999, output_tokens=1),
        ],
    )

    assert batch.run_metrics["duration_seconds"]["stddev"] == 0.0
    assert batch.turn_metrics[0]["output_tokens"]["stddev"] == 0.0
```

- [x] **Step 2: Run test to verify it fails**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_batch.py -q`
Expected: FAIL with `ModuleNotFoundError` for `agent_bencher.batch` or missing batch result symbols.

- [x] **Step 3: Write minimal implementation**

```python
# src/agent_bencher/models.py
@dataclass(slots=True)
class MetricSummary:
    mean: float
    min: float
    max: float
    stddev: float


@dataclass(slots=True)
class BatchResult:
    batch_id: str
    conversation_name: str
    agent_id: str
    frontend: str
    backend_model: str
    comment: str
    requested_runs: int
    successful_runs: int
    failed_runs: int
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    sessions: list[SessionResult]
    run_metrics: dict[str, MetricSummary]
    turn_metrics: list[dict[str, MetricSummary]]
```

```python
# src/agent_bencher/batch.py
from __future__ import annotations

import math

from agent_bencher.models import BatchResult, MetricSummary, SessionResult


def _summary(values: list[float]) -> MetricSummary:
    if len(values) == 1:
        return MetricSummary(mean=values[0], min=values[0], max=values[0], stddev=0.0)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return MetricSummary(mean=mean, min=min(values), max=max(values), stddev=math.sqrt(variance))


def build_batch_result(*, batch_id: str, requested_runs: int, comment: str, sessions: list[SessionResult]) -> BatchResult:
    successful = [session for session in sessions if session.status == "completed"]
    failed = [session for session in sessions if session.status != "completed"]
    first = sessions[0]
    run_metrics = {
        "duration_seconds": _summary([session.duration_seconds for session in successful]),
        "total_input_tokens": _summary([sum(turn.token_usage.input for turn in session.turns) for session in successful]),
        "total_output_tokens": _summary([sum(turn.token_usage.output for turn in session.turns) for session in successful]),
        "effective_output_tps": _summary([
            0.0 if session.duration_seconds == 0 else sum(turn.token_usage.output for turn in session.turns) / session.duration_seconds
            for session in successful
        ]),
        "effective_total_throughput_tps": _summary([
            0.0 if session.duration_seconds == 0 else (
                sum(turn.token_usage.input + turn.token_usage.output for turn in session.turns) / session.duration_seconds
            )
            for session in successful
        ]),
    }
    turn_metrics = []
    if successful:
        for turn_index in range(len(successful[0].turns)):
            turns = [session.turns[turn_index] for session in successful]
            turn_metrics.append(
                {
                    "duration_seconds": _summary([turn.duration_seconds for turn in turns]),
                    "input_tokens": _summary([turn.token_usage.input for turn in turns]),
                    "output_tokens": _summary([turn.token_usage.output for turn in turns]),
                    "output_tps": _summary([
                        0.0 if turn.duration_seconds == 0 else turn.token_usage.output / turn.duration_seconds for turn in turns
                    ]),
                    "total_throughput_tps": _summary([
                        0.0 if turn.duration_seconds == 0 else (
                            turn.token_usage.input + turn.token_usage.output
                        ) / turn.duration_seconds
                        for turn in turns
                    ]),
                }
            )
    return BatchResult(
        batch_id=batch_id,
        conversation_name=first.conversation_name,
        agent_id=first.agent_id,
        frontend=first.frontend,
        backend_model=first.backend_model,
        comment=comment,
        requested_runs=requested_runs,
        successful_runs=len(successful),
        failed_runs=len(failed),
        started_at=sessions[0].started_at,
        ended_at=sessions[-1].ended_at,
        duration_seconds=sum(session.duration_seconds for session in sessions),
        status="completed" if len(successful) == requested_runs else "partial" if successful else "failed",
        sessions=sessions,
        run_metrics=run_metrics,
        turn_metrics=turn_metrics,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_batch.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add tests/test_batch.py src/agent_bencher/models.py src/agent_bencher/batch.py
git commit -m "feat: add batch result aggregation"
```

### Task 2: Add Batch And Trial Result Writers

**Files:**
- Modify: `src/agent_bencher/results.py`
- Modify: `src/agent_bencher/report.py`
- Test: `tests/test_results.py`
- Test: `tests/test_report.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path
import json

from agent_bencher.batch import build_batch_result
from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.results import write_batch_results


def test_write_batch_results_uses_batch_first_layout(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="run-1",
        conversation_name="sample-conversation",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-1",
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
                session_id="session-1",
                exit_code=0,
                duration_seconds=1.0,
                stdout="assistant output",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            )
        ],
        comment="",
    )
    batch = build_batch_result(batch_id="batch-1", requested_runs=1, comment="", sessions=[session])

    write_batch_results(batch=batch, output_dir=tmp_path)

    assert (tmp_path / "batch.json").exists()
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "trials" / "trial-001" / "run.json").exists()


def test_batch_report_lists_failed_trials_and_aggregate_metrics() -> None:
    report = build_batch_markdown_report(batch)
    assert "successful runs: 1/2" in report
    assert "failed runs: 1" in report
    assert "duration_seconds" in report
```

- [x] **Step 2: Run test to verify it fails**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_results.py tests/test_report.py -q`
Expected: FAIL with missing `write_batch_results` or missing batch report support.

- [x] **Step 3: Write minimal implementation**

```python
# src/agent_bencher/results.py
def write_trial_results(*, session: SessionResult, output_dir: Path) -> None:
    ...


def write_batch_results(*, batch: BatchResult, output_dir: Path) -> None:
    trials_dir = output_dir / "trials"
    for index, session in enumerate(batch.sessions, start=1):
        write_trial_results(session=session, output_dir=trials_dir / f"trial-{index:03d}")
    (output_dir / "batch.json").write_text(json.dumps(_serialize_batch(batch), indent=2) + "\n")
    (output_dir / "summary.md").write_text(build_batch_markdown_report(batch))
```

```python
# src/agent_bencher/report.py
def build_batch_markdown_report(batch: BatchResult) -> str:
    ...
```

- [x] **Step 4: Run test to verify it passes**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_results.py tests/test_report.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/agent_bencher/results.py src/agent_bencher/report.py tests/test_results.py tests/test_report.py
git commit -m "feat: write batch benchmark artifacts"
```

### Task 3: Add CLI Support For Repeated Trials

**Files:**
- Modify: `src/agent_bencher/cli.py`
- Modify: `tests/test_report.py`
- Create: `tests/test_cli_repeat_runs.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

from agent_bencher.cli import build_parser


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
```

- [x] **Step 2: Run test to verify it fails**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_cli_repeat_runs.py -q`
Expected: FAIL because `--runs` is not defined.

- [x] **Step 3: Write minimal implementation**

```python
# src/agent_bencher/cli.py
bench.add_argument(
    "--runs",
    type=int,
    default=1,
    help="Number of repeated trials to execute. Default: 1",
)
...
batch_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
sessions = []
for trial_index in range(args.runs):
    trial_started = datetime.now(timezone.utc)
    run_id = format_run_id(trial_started.strftime("%Y-%m-%d"), trial_started.strftime("%H:%M:%S"))
    prepared = prepare_variant_workspace(...)
    session = run_conversation(...)
    sessions.append(session)
batch = build_batch_result(batch_id=batch_id, requested_runs=args.runs, comment=args.comment, sessions=sessions)
write_batch_results(batch=batch, output_dir=args.output_dir / conversation.name / agent.id / batch_id)
```

- [x] **Step 4: Run test to verify it passes**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest tests/test_cli_repeat_runs.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/agent_bencher/cli.py tests/test_cli_repeat_runs.py tests/test_report.py
git commit -m "feat: add repeated benchmark cli runs"
```

### Task 4: Run Full Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-06-01-repeated-benchmark-runs-implementation.md`

- [x] **Step 1: Run the full test suite**

Run: `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync pytest -q`
Expected: PASS with all tests green.

- [x] **Step 2: Mark completed items in this plan**

```markdown
- [x] Completed during implementation
```

- [x] **Step 3: Commit final implementation**

```bash
git add docs/superpowers/plans/2026-06-01-repeated-benchmark-runs-implementation.md
git commit -m "docs: mark repeated benchmark runs plan complete"
```
