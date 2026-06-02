# Parallel Trial Execution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run multiple benchmark trials concurrently instead of sequentially, reducing total wall-clock time by roughly the number of trials.

**Architecture:** Replace the `for` loop in `cli.py:main()` with `concurrent.futures.ThreadPoolExecutor`. Each trial is I/O-bound (subprocess execution, file I/O), so threading avoids GIL contention. Extract per-trial logic into a standalone `_run_single_trial` function for testability. All existing top-level imports in `cli.py` are reused (no local imports) so existing test monkeypatches continue to work.

**Tech Stack:** `concurrent.futures.ThreadPoolExecutor`, `argparse`, `pathlib`, `dataclasses`

---

### File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/agent_bencher/cli.py` | Extract trial loop into `_run_single_trial`, add `ThreadPoolExecutor`, add `--jobs` flag |
| Modify | `src/agent_bencher/models.py` | Add `_TrialResult` dataclass (or define in cli.py) |
| Create | `tests/test_cli_parallel.py` | Tests for parallel execution, `--jobs` flag, error propagation |

---

### Task 1: Extract `_run_single_trial` function

**Files:**
- Modify: `src/agent_bencher/cli.py` (add function, refactor `main`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_parallel.py`:

```python
from pathlib import Path
import pytest

from agent_bencher.cli import _run_single_trial, _TrialResult
from agent_bencher.models import AgentConfig, Conversation, Prompt, SessionResult, TokenUsage, TurnResult


def _make_session(*, run_id: str) -> SessionResult:
    return SessionResult(
        run_id=run_id,
        conversation_name="sample",
        agent_id="test-agent",
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


def test_run_single_trial_returns_session_and_workspace(tmp_path: Path, monkeypatch) -> None:
    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    workspaces_created: list[Path] = []

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id):
        root = tmp_path / f"trial-{len(workspaces_created)}"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        workspaces_created.append(ws.parent)
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)

    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", lambda **kw: _make_session(run_id="trial-1"))

    result = _run_single_trial(
        trial_index=0,
        conversation=Conversation(name="sample", source_workspace=tmp_path / "source", prompts=[Prompt(text="Do this")]),
        agent=AgentConfig(id="test-agent", frontend="opencode", model="model-x"),
        output_dir=tmp_path / "runs",
        comment="",
    )

    assert isinstance(result, _TrialResult)
    assert result.session.run_id == "trial-1"
    assert result.workspace is not None
    assert len(workspaces_created) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_parallel.py::test_run_single_trial_returns_session_and_workspace -v`
Expected: FAIL with `ImportError: cannot import name '_run_single_trial' from 'agent_bencher.cli'`

- [ ] **Step 3: Add `_TrialResult` dataclass and `_run_single_trial` function**

Add to `src/agent_bencher/cli.py` after the `positive_int` function (after line 27), before `build_parser`:

```python
@dataclass(slots=True)
class _TrialResult:
    session: SessionResult
    workspace: PreparedWorkspace | None


def _run_single_trial(
    *,
    trial_index: int,
    conversation: Conversation,
    agent: AgentConfig,
    output_dir: Path,
    comment: str,
) -> _TrialResult:
    trial_started_at = datetime.now(timezone.utc)
    trial_run_id = (
        f"{format_run_id(trial_started_at.strftime('%Y-%m-%d'), trial_started_at.strftime('%H:%M:%S'))}"
        f"-trial-{trial_index + 1:03d}"
    )
    prepared = prepare_variant_workspace(
        source_workspace=conversation.source_workspace,
        run_root=output_dir,
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
        run_id=trial_run_id,
        started_at=trial_started_at.isoformat(),
        comment=comment,
    )
    return _TrialResult(session=session, workspace=prepared)
```

Add `from dataclasses import dataclass` to the top imports.
Add `SessionResult` to the existing imports from `agent_bencher.models` (will be added in Step 4).

- [ ] **Step 3b: Add required imports**

Update the top of `cli.py` to include:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil

from agent_bencher.adapters import get_adapter
from agent_bencher.batch import build_batch_result
from agent_bencher.models import AgentConfig, Conversation, SessionResult
from agent_bencher.process import run_command
from agent_bencher.results import write_batch_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import PreparedWorkspace, prepare_variant_workspace
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_parallel.py::test_run_single_trial_returns_session_and_workspace -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/cli.py tests/test_cli_parallel.py
git commit -m "refactor: extract _run_single_trial from main loop for parallel execution"
```

---

### Task 2: Replace sequential loop with ThreadPoolExecutor + `--jobs` flag

**Files:**
- Modify: `src/agent_bencher/cli.py` (add `--jobs` flag, replace `for` loop in `main`)

- [ ] **Step 1: Add `--jobs` CLI flag**

In `build_parser`, add after the `--runs` argument (after line 56):

```python
    bench.add_argument(
        "--jobs",
        type=positive_int,
        default=1,
        help="Max concurrent trials. Default: 1 (sequential)",
    )
```

- [ ] **Step 2: Write tests for `--jobs`**

Add to `tests/test_cli_parallel.py`:

```python
import threading
import time

from agent_bencher.cli import build_parser, main


def test_build_parser_defaults_jobs_to_one() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["bench", "rc.yaml", "conv.yaml"])

    assert parsed.jobs == 1


def test_build_parser_accepts_jobs_arg() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["bench", "rc.yaml", "conv.yaml", "--jobs", "4"])

    assert parsed.jobs == 4


def test_main_runs_trials_in_parallel(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="test-agent", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    max_concurrent = 0
    current_concurrent = 0
    lock = threading.Lock()

    workspaces: list[Path] = []

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id):
        root = tmp_path / f"trial-{len(workspaces)}"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        workspaces.append(ws)
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)

    sessions = iter([_make_session(run_id="run-1"), _make_session(run_id="run-2")])

    def fake_run_conversation(**kwargs):
        nonlocal max_concurrent, current_concurrent
        with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        time.sleep(0.15)
        with lock:
            current_concurrent -= 1
        return next(sessions)

    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)

    captured = {}

    def fake_write(*, batch, output_dir):
        captured["batch"] = batch

    monkeypatch.setattr("agent_bencher.cli.write_batch_results", fake_write)

    exit_code = main([
        "bench", "rc.yaml", "conv.yaml",
        "--runs", "2", "--jobs", "2",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert exit_code == 0
    assert max_concurrent == 2, f"expected 2 concurrent trials, got {max_concurrent}"
    assert captured["batch"].requested_runs == 2
    assert len(captured["batch"].sessions) == 2


def test_main_sequential_when_jobs_is_one(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="test-agent", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    max_concurrent = 0
    current_concurrent = 0
    lock = threading.Lock()

    workspaces: list[Path] = []

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id):
        root = tmp_path / f"trial-{len(workspaces)}"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        workspaces.append(ws)
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)

    sessions = iter([_make_session(run_id="run-1"), _make_session(run_id="run-2")])

    def fake_run_conversation(**kwargs):
        nonlocal max_concurrent, current_concurrent
        with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        time.sleep(0.15)
        with lock:
            current_concurrent -= 1
        return next(sessions)

    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kw: None)

    exit_code = main([
        "bench", "rc.yaml", "conv.yaml",
        "--runs", "2",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert exit_code == 0
    assert max_concurrent == 1, f"expected 1 concurrent trial with jobs=1, got {max_concurrent}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_cli_parallel.py::test_build_parser_defaults_jobs_to_one tests/test_cli_parallel.py::test_main_runs_trials_in_parallel -v`
Expected: FAIL (flag doesn't exist, parallel logic doesn't exist)

- [ ] **Step 4: Replace the `for` loop in `main` with parallel execution**

Replace lines 78-100 of `cli.py` (the `for trial_index in range(args.runs):` block) with:

```python
    from concurrent.futures import ThreadPoolExecutor, as_completed

    trial_fns = [
        lambda idx=i: _run_single_trial(
            trial_index=idx,
            conversation=conversation,
            agent=agent,
            output_dir=args.output_dir,
            comment=args.comment,
        )
        for i in range(args.runs)
    ]

    if args.jobs == 1:
        results = [fn() for fn in trial_fns]
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            indexed = list(executor.map(
                    lambda fn: (fn(), trial_fns.index(fn)),
                    trial_fns,
                ))
        indexed.sort(key=lambda x: x[1])
        results = [r for r, _ in indexed]

    sessions = [r.session for r in results]

    for result in results:
        if result.session.status == "completed" and result.workspace:
            shutil.rmtree(result.workspace.variant_workspace.parent)
```

Wait, the `trial_fns.index(fn)` approach is O(n²) and fragile with lambdas. Let me use a cleaner pattern:

```python
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if args.jobs == 1:
        results = [
            _run_single_trial(
                trial_index=i,
                conversation=conversation,
                agent=agent,
                output_dir=args.output_dir,
                comment=args.comment,
            )
            for i in range(args.runs)
        ]
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_to_index = {
                executor.submit(
                    _run_single_trial,
                    trial_index=i,
                    conversation=conversation,
                    agent=agent,
                    output_dir=args.output_dir,
                    comment=args.comment,
                ): i
                for i in range(args.runs)
            }
            indexed_results = [
                (future.result(), idx)
                for future in as_completed(future_to_index)
                for idx in [future_to_index[future]]
            ]
            indexed_results.sort(key=lambda x: x[1])
            results = [r for r, _ in indexed_results]

    sessions = [r.session for r in results]

    for result in results:
        if result.session.status == "completed" and result.workspace:
            shutil.rmtree(result.workspace.variant_workspace.parent)
```

- [ ] **Step 5: Run parallel tests to verify they pass**

Run: `pytest tests/test_cli_parallel.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Run existing CLI tests for regression**

Run: `pytest tests/test_cli_repeat_runs.py -v`
Expected: All PASS (sequential behavior preserved when `--jobs` defaults to 1)

- [ ] **Step 7: Commit**

```bash
git add src/agent_bencher/cli.py tests/test_cli_parallel.py
git commit -m "feat: add parallel trial execution with --jobs flag"
```

---

### Task 3: Run full test suite

**Files:**
- Modify: any file that needs fixes

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Fix any failures**

If `test_cli_repeat_runs.py` tests fail because the `for` loop structure changed, the monkeypatches should still work since `_run_single_trial` uses the module-level names (`prepare_variant_workspace`, `get_adapter`, `run_command`, `run_conversation`) which are imported at the top of `cli.py`. The existing monkeypatches target `agent_bencher.cli.*` which is correct.

- [ ] **Step 3: Commit any fixes**

```bash
git add .
git commit -m "fix: adjust tests for parallel trial execution"
```
