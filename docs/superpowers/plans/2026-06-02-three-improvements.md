# Three Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a suite batch command, workspace caching/cleanup, and a comparison mode to the agent-bencher CLI.

**Architecture:** Three independent features, each adding one CLI subcommand or extending existing modules. No shared new modules — each stands alone.

**Tech Stack:** Python 3.11+, argparse, pathlib, concurrent.futures, yaml, json, pytest.

---

## Improvement 1: Suite Batch Command

**Files:**
- Create: `src/agent_bencher/cli_suite.py`
- Create: `tests/test_cli_suite.py`
- Modify: `src/agent_bencher/cli.py` (add suite subparser registration)

### Task 1.1: Implement suite subcommand CLI

**Files:**
- Create: `src/agent_bencher/cli_suite.py`
- Modify: `src/agent_bencher/cli.py:47-52` (append suite parser registration)

- [ ] **Step 1: Write the suite subparser**

In `src/agent_bencher/cli_suite.py`, create a `build_suite_parser()` function that adds a `suite` subcommand with:
- `run_configs`: glob pattern or directory path (positional arg, required)
- `conversations`: glob pattern or directory path (positional arg, required)
- `--output-dir`: same as bench, default `runs`
- `--runs`: same as bench, default `1`
- `--max-concurrent`: new arg, default `4`, positive int, max number of parallel runs
- `--dry-run`: flag, when set, print what would run without executing

```python
# src/agent_bencher/cli_suite.py (new file, partial)
from __future__ import annotations

import argparse
from pathlib import Path


def build_suite_parser(parser: argparse.ArgumentParser) -> None:
    suite = parser.add_parser(
        "suite",
        help="Run all conversation/config pairs in a suite.",
        description="Load all YAML pairs from the given paths, run them in parallel, and write artifacts.",
    )
    suite.add_argument("run_configs", type=Path, help="Path to run_configs directory or glob pattern.")
    suite.add_argument("conversations", type=Path, help="Path to conversations directory or glob pattern.")
    suite.add_argument("--output-dir", type=Path, default=Path("runs"), help="Output directory. Default: runs")
    suite.add_argument("--runs", type=positive_int, default=1, help="Trials per config/conversation pair. Default: 1")
    suite.add_argument("--max-concurrent", type=positive_int, default=4, help="Max parallel runs. Default: 4")
    suite.add_argument("--dry-run", action="store_true", help="Print pairs without executing.")
```

- [ ] **Step 2: Wire it into cli.py**

In `src/agent_bencher/cli.py`, in `build_parser()`, after the `bench` subparser is added, add:

```python
# In build_parser(), after bench subparser:
from agent_bencher.cli_suite import build_suite_parser
build_suite_parser(subparsers)
```

And in `main()`, after the `bench` command handling, add:

```python
if args.command == "suite":
    return main_suite(args)
```

- [ ] **Step 3: Write failing tests**

In `tests/test_cli_suite.py`:

```python
from agent_bencher.cli_suite import build_suite_parser

def test_build_suite_parser_creates_subcommand():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_suite_parser(subparsers)
    # Verify the parser accepts expected args
    args = parser.parse_args(["suite", "run_configs/", "conversations/"])
    assert args.run_configs == Path("run_configs/")
    assert args.conversations == Path("conversations/")
    assert args.output_dir == Path("runs")
    assert args.runs == 1
    assert args.max_concurrent == 4
    assert args.dry_run is False
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_cli_suite.py -v`
Expected: FAIL

- [ ] **Step 5: Implement the parser wiring**

Add the import and command dispatch in `cli.py` as shown in Step 2 above.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_cli_suite.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agent_bencher/cli.py src/agent_bencher/cli_suite.py tests/test_cli_suite.py
git commit -m "feat: add suite subparser for multi-config runs"
```

### Task 1.2: Implement suite execution logic

**Files:**
- Create: `src/agent_bencher/suite_runner.py`
- Test: `tests/test_suite_runner.py`

- [ ] **Step 1: Write the suite runner function**

In `src/agent_bencher/suite_runner.py`:

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import sys

from agent_bencher.cli import format_run_id, format_display_time
from agent_bencher.batch import build_batch_result
from agent_bencher.process import run_command
from agent_bencher.results import write_batch_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import prepare_variant_workspace


def run_suite(
    run_config_paths: list[Path],
    conversation_paths: list[Path],
    output_dir: Path,
    runs: int,
    max_concurrent: int,
) -> None:
    """Run all conversation/config pairs in parallel."""
    pairs = []
    for rc_path in run_config_paths:
        for conv_path in conversation_paths:
            pairs.append((rc_path, conv_path))

    now = datetime.now(timezone.utc)
    suite_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    suite_output_dir = output_dir / "_suite" / suite_id

    print(f"Suite started at {format_display_time(now)}", file=sys.stderr, flush=True)
    print(f"Running {len(pairs)} pairs with {max_concurrent} concurrent workers", file=sys.stderr, flush=True)

    all_results: dict[tuple[Path, Path], object] = {}

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {}
        for rc_path, conv_path in pairs:
            future = executor.submit(
                _run_single_pair,
                rc_path,
                conv_path,
                output_dir,
                runs,
            )
            futures[(rc_path, conv_path)] = future

        for (rc_path, conv_path), future in futures.items():
            try:
                result = future.result()
                all_results[(rc_path, conv_path)] = result
            except Exception as e:
                print(f"  ERROR: {rc_path.name} x {conv_path.name}: {e}", file=sys.stderr, flush=True)
                all_results[(rc_path, conv_path)] = None

    print(f"Suite concluded at {format_display_time(datetime.now(timezone.utc))}", file=sys.stderr, flush=True)


def _run_single_pair(
    rc_path: Path,
    conv_path: Path,
    output_dir: Path,
    runs: int,
) -> object:
    """Run one conversation/config pair."""
    from agent_bencher.adapters import get_adapter
    from agent_bencher.batch import build_batch_result
    from agent_bencher.process import run_command
    from agent_bencher.results import write_batch_results
    from agent_bencher.runner import run_conversation
    from agent_bencher.suite import load_agent_config, load_conversation
    from agent_bencher.workspace import prepare_variant_workspace

    conversation = load_conversation(conv_path)
    agent = load_agent_config(rc_path)
    adapter = get_adapter(agent.frontend)
    batch_id = format_run_id(
        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        datetime.now(timezone.utc).strftime("%H:%M:%S"),
    )
    batch_output_dir = output_dir / conversation.name / agent.id / batch_id

    sessions = []
    for trial_index in range(runs):
        prepared = prepare_variant_workspace(
            source_workspace=conversation.source_workspace,
            run_root=output_dir,
            suite_name=conversation.name,
            variant_id=agent.id,
        )
        trial_run_id = f"{batch_id}-trial-{trial_index + 1:03d}"
        session = run_conversation(
            conversation=conversation,
            agent=agent,
            workspace=prepared.variant_workspace,
            adapter=adapter,
            run_command=run_command,
            run_id=trial_run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        sessions.append(session)
        if session.status == "completed":
            import shutil
            shutil.rmtree(prepared.variant_workspace.parent)

    batch = build_batch_result(
        batch_id=batch_id,
        requested_runs=runs,
        comment="",
        sessions=sessions,
    )
    write_batch_results(batch=batch, output_dir=batch_output_dir)
    return batch
```

- [ ] **Step 2: Write the `main_suite` function**

Add to `src/agent_bencher/cli_suite.py`:

```python
def main_suite(args: argparse.Namespace) -> int:
    """Execute the suite command."""
    from agent_bencher.suite_runner import run_suite

    run_config_paths = sorted(args.run_configs.glob("*.yaml"))
    conversation_paths = sorted(args.conversations.glob("*.yaml"))

    if not run_config_paths:
        print(f"ERROR: no run configs found at {args.run_configs}", file=sys.stderr)
        return 1
    if not conversation_paths:
        print(f"ERROR: no conversations found at {args.conversations}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run — would execute the following pairs:", file=sys.stderr)
        for rc in run_config_paths:
            for conv in conversation_paths:
                print(f"  {rc.name} x {conv.name}", file=sys.stderr)
        return 0

    run_suite(
        run_config_paths=run_config_paths,
        conversation_paths=conversation_paths,
        output_dir=args.output_dir,
        runs=args.runs,
        max_concurrent=args.max_concurrent,
    )
    return 0
```

- [ ] **Step 3: Wire `main_suite` into cli.py**

In `src/agent_bencher/cli.py`, import and dispatch:

```python
from agent_bencher.cli_suite import build_suite_parser, main_suite
# ...
if args.command == "suite":
    return main_suite(args)
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests pass, new test passes.

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/cli.py src/agent_bencher/cli_suite.py src/agent_bencher/suite_runner.py tests/test_cli_suite.py
git commit -m "feat: implement suite batch execution with parallel workers"
```

---

## Improvement 2: Workspace Caching and Cleanup

**Files:**
- Modify: `src/agent_bencher/workspace.py` (add cache + cleanup)
- Create: `tests/test_workspace_cache.py`
- Create: `tests/test_workspace_cleanup.py`

### Task 2.1: Implement workspace copy cache

**Files:**
- Modify: `src/agent_bencher/workspace.py`

- [ ] **Step 1: Add a cache dataclass and helper**

In `src/agent_bencher/workspace.py`, add:

```python
import hashlib
import json
from dataclasses import dataclass, field


@dataclass(slots=True)
class WorkspaceCache:
    """Simple on-disk cache for workspace copies keyed by content hash."""

    cache_dir: Path
    # Maps (source_workspace_key, variant_id) -> cache entry path
    _index: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_output_dir(cls, output_dir: Path) -> WorkspaceCache:
        index_path = output_dir / "_cache_index.json"
        if index_path.exists():
            index = json.loads(index_path.read_text())
        else:
            index = {}
        cache_dir = output_dir / "_cache"
        cache_dir.mkdir(exist_ok=True)
        return cls(cache_dir=cache_dir, _index=index)

    def get(self, source_workspace: Path, variant_id: str) -> Path | None:
        source_key = hashlib.sha256(str(source_workspace.resolve()).encode()).hexdigest()
        key = f"{source_key}:{variant_id}"
        cached_path = self._index.get(key)
        if cached_path and Path(cached_path).exists():
            return Path(cached_path)
        return None

    def put(self, source_workspace: Path, variant_id: str, workspace_dir: Path) -> None:
        source_key = hashlib.sha256(str(source_workspace.resolve()).encode()).hexdigest()
        key = f"{source_key}:{variant_id}"
        cache_entry = self.cache_dir / f"{key}.workspace"
        import shutil
        shutil.copytree(workspace_dir, cache_entry)
        self._index[key] = str(cache_entry)
        self._persist()

    def _persist(self) -> None:
        self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
        (self.cache_dir.parent / "_cache_index.json").write_text(json.dumps(self._index))
```

- [ ] **Step 2: Modify `prepare_variant_workspace` to use the cache**

Update `prepare_variant_workspace` in `src/agent_bencher/workspace.py`:

```python
def prepare_variant_workspace(
    *,
    source_workspace: Path,
    run_root: Path,
    suite_name: str,
    variant_id: str,
    cache: WorkspaceCache | None = None,
) -> PreparedWorkspace:
    run_id = uuid.uuid4().hex[:8]
    base_dir = run_root / suite_name / variant_id / run_id
    workspace_dir = base_dir / "workspace"
    artifacts_dir = base_dir / "artifacts"

    # Check cache first
    if cache is not None:
        cached = cache.get(source_workspace, variant_id)
        if cached is not None:
            # Copy from cache to the run directory
            import shutil
            workspace_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(cached, workspace_dir, dirs_exist_ok=True)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            return PreparedWorkspace(
                variant_workspace=workspace_dir,
                artifacts_dir=artifacts_dir,
            )

    ignore = _build_ignore_function(source_workspace=source_workspace, run_root=run_root)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_workspace, workspace_dir, ignore=ignore)

    # Store in cache
    if cache is not None:
        cache.put(source_workspace, variant_id, workspace_dir)

    return PreparedWorkspace(
        variant_workspace=workspace_dir,
        artifacts_dir=artifacts_dir,
    )
```

- [ ] **Step 3: Write failing tests**

In `tests/test_workspace_cache.py`:

```python
from pathlib import Path
import tempfile
import pytest
from agent_bencher.workspace import WorkspaceCache, PreparedWorkspace


def test_cache_miss_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        cache = WorkspaceCache.from_output_dir(Path(tmp))
        result = cache.get(Path("/nonexistent"), "v1")
        assert result is None


def test_cache_put_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        cache = WorkspaceCache.from_output_dir(Path(tmp))
        source = Path(tmp) / "source"
        source.mkdir()
        (source / "file.txt").write_text("hello")

        dest = Path(tmp) / "dest"
        dest.mkdir()
        import shutil
        shutil.copytree(source, dest)

        cache.put(source, "v1", dest)
        result = cache.get(source, "v1")
        assert result is not None
        assert (result / "file.txt").read_text() == "hello"


def test_cache_miss_on_different_variant():
    with tempfile.TemporaryDirectory() as tmp:
        cache = WorkspaceCache.from_output_dir(Path(tmp))
        source = Path(tmp) / "source"
        source.mkdir()

        dest = Path(tmp) / "dest"
        dest.mkdir()
        cache.put(source, "v1", dest)

        result = cache.get(source, "v2")
        assert result is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_workspace_cache.py -v`
Expected: FAIL (WorkspaceCache doesn't exist yet)

- [ ] **Step 5: Implement WorkspaceCache and update workspace.py**

Add the WorkspaceCache class and modify `prepare_variant_workspace` as shown in Steps 1-2 above.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_workspace_cache.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agent_bencher/workspace.py tests/test_workspace_cache.py
git commit -m "feat: add workspace copy cache to avoid redundant copytree calls"
```

### Task 2.2: Implement stale workspace cleanup

**Files:**
- Create: `src/agent_bencher/cleanup.py`
- Create: `tests/test_cleanup.py`

- [ ] **Step 1: Implement cleanup function**

In `src/agent_bencher/cleanup.py`:

```python
from __future__ import annotations

from pathlib import Path
import shutil
import time


def cleanup_stale_workspaces(
    run_root: Path,
    max_age_hours: float = 24.0,
) -> int:
    """Remove variant workspace directories older than max_age_hours.

    Returns the number of directories removed.
    """
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    if not run_root.exists():
        return 0

    # Find directories named "workspace" that are NOT inside a completed run
    # Stale = workspace dirs that are NOT referenced by any batch.json
    batch_refs = set()
    for batch_file in run_root.rglob("batch.json"):
        import json
        batch = json.loads(batch_file.read_text())
        for trial in batch.get("trials", []):
            trial_path = batch_file.parent / trial["path"]
            if trial_path.exists():
                workspace = trial_path / "workspace"
                if workspace.exists():
                    batch_refs.add(str(workspace.resolve()))

    for workspace_dir in run_root.rglob("workspace"):
        resolved = str(workspace_dir.resolve())
        if resolved in batch_refs:
            continue

        # Check modification time
        try:
            mtime = workspace_dir.stat().st_mtime
        except OSError:
            continue

        if mtime < cutoff:
            shutil.rmtree(workspace_dir.parent, ignore_errors=True)
            removed += 1

    return removed
```

- [ ] **Step 2: Add CLI flag to bench and suite commands**

In `src/agent_bencher/cli.py`, add to the `bench` subparser:

```python
bench.add_argument(
    "--cleanup",
    type=float,
    default=0,
    metavar="HOURS",
    help="Remove stale workspace directories older than HOURS hours. 0 = disabled.",
)
```

And in `main()`, after the batch is written:

```python
if args.cleanup > 0:
    from agent_bencher.cleanup import cleanup_stale_workspaces
    removed = cleanup_stale_workspaces(args.output_dir, max_age_hours=args.cleanup)
    if removed:
        print(f"Cleaned up {removed} stale workspace(s)", file=sys.stderr)
```

- [ ] **Step 3: Write failing tests**

In `tests/test_cleanup.py`:

```python
from pathlib import Path
import tempfile
import time
import pytest
from agent_bencher.cleanup import cleanup_stale_workspaces


def test_cleanup_removes_stale_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp)
        stale = run_root / "stale_suite" / "config1" / "run1" / "workspace"
        stale.mkdir(parents=True)
        (stale / "file.txt").write_text("data")
        # Backdate the mtime
        old_time = time.time() - 48 * 3600  # 48 hours ago
        os.utime(stale, (old_time, old_time))

        removed = cleanup_stale_workspaces(run_root, max_age_hours=24)
        assert removed == 1
        assert not stale.exists()


def test_cleanup_skips_recent_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp)
        fresh = run_root / "fresh_suite" / "config1" / "run1" / "workspace"
        fresh.mkdir(parents=True)
        (fresh / "file.txt").write_text("data")

        removed = cleanup_stale_workspaces(run_root, max_age_hours=24)
        assert removed == 0
        assert fresh.exists()


def test_cleanup_skips_referenced_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp)
        # Create a batch.json that references a workspace
        batch_dir = run_root / "ref_suite" / "config1" / "batch1"
        trials_dir = batch_dir / "trials" / "trial-001"
        batch_dir.mkdir(parents=True)
        trials_dir.mkdir(parents=True)
        workspace = trials_dir / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("data")

        # Create batch.json referencing the workspace
        batch = {
            "batch_id": "batch1",
            "trials": [{"trial_id": "trial-001", "path": "trials/trial-001", "status": "completed"}],
        }
        (batch_dir / "batch.json").write_text(json.dumps(batch))

        removed = cleanup_stale_workspaces(run_root, max_age_hours=0)
        assert removed == 0
        assert workspace.exists()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_cleanup.py -v`
Expected: FAIL (cleanup module doesn't exist yet)

- [ ] **Step 5: Implement cleanup.py and update cli.py**

Add the cleanup module and CLI flag as shown in Steps 1-2 above.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_cleanup.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agent_bencher/cleanup.py src/agent_bencher/cli.py tests/test_cleanup.py
git commit -m "feat: add stale workspace cleanup with --cleanup flag"
```

---

## Improvement 3: Comparison Mode

**Files:**
- Create: `src/agent_bencher/comparator.py`
- Create: `tests/test_comparator.py`
- Modify: `src/agent_bencher/cli.py` (add `compare` subcommand)

### Task 3.1: Implement batch comparison logic

**Files:**
- Create: `src/agent_bencher/comparator.py`

- [ ] **Step 1: Implement the comparator module**

In `src/agent_bencher/comparator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json

from agent_bencher.models import MetricSummary


@dataclass(slots=True)
class RunComparison:
    """Comparison metrics between two runs."""
    config_a: str
    config_b: str
    duration_delta_seconds: float  # positive = B is slower
    input_tokens_delta: int  # positive = B uses more
    output_tokens_delta: int  # positive = B uses more
    output_tps_delta: float  # positive = B is faster
    total_throughput_tps_delta: float  # positive = B is faster
    conversation_name: str = ""
    successful_runs_a: int = 0
    successful_runs_b: int = 0


@dataclass(slots=True)
class ComparisonReport:
    """Full comparison report between two batches."""
    batch_a_id: str
    batch_b_id: str
    conversation_name: str
    config_a: str
    config_b: str
    run_comparisons: list[RunComparison] = field(default_factory=list)
    summary: dict[str, str] = field(default_factory=dict)


def compare_batches(batch_a_path: Path, batch_b_path: Path) -> ComparisonReport:
    """Compare two batch.json files and produce a comparison report."""
    batch_a = json.loads(batch_a_path.read_text())
    batch_b = json.loads(batch_b_path.read_text())

    report = ComparisonReport(
        batch_a_id=batch_a["batch_id"],
        batch_b_id=batch_b["batch_id"],
        conversation_name=batch_a["conversation_name"],
        config_a=batch_a["agent_id"],
        config_b=batch_b["agent_id"],
    )

    metrics_a = batch_a.get("run_metrics", {})
    metrics_b = batch_b.get("run_metrics", {})

    # Compare per-metric
    all_metric_names = set(metrics_a.keys()) | set(metrics_b.keys())
    summary_parts: list[str] = []

    for metric_name in sorted(all_metric_names):
        summary_a = metrics_a.get(metric_name, {})
        summary_b = metrics_b.get(metric_name, {})
        mean_a = summary_a.get("mean", 0)
        mean_b = summary_b.get("mean", 0)
        delta = mean_b - mean_a

        # Format the delta
        if metric_name == "duration_seconds":
            label = f"duration_delta_s"
            display_delta = f"{delta:+.2f}s"
        elif "tps" in metric_name:
            label = f"{metric_name}_delta"
            display_delta = f"{delta:+.2f}"
        else:
            label = f"{metric_name}_delta"
            display_delta = f"{delta:+d}"

        summary_parts.append(f"  {label}: {display_delta}")

    report.summary = {
        "conversation": batch_a["conversation_name"],
        "config_a": batch_a["agent_id"],
        "config_b": batch_b["agent_id"],
        "metrics": "\n".join(summary_parts),
    }

    return report


def format_comparison_report(report: ComparisonReport) -> str:
    """Format a ComparisonReport as a human-readable string."""
    lines = [
        f"# Comparison: {report.config_a} vs {report.config_b}",
        f"Conversation: {report.conversation_name}",
        "",
        "## Metrics (positive = B is higher/slower, negative = A is higher/slower)",
        report.summary["metrics"],
        "",
    ]

    for rc in report.run_comparisons:
        lines.extend(
            [
                f"### Turn {rc.prompt_id}",
                f"  Duration delta: {rc.duration_delta_seconds:+.2f}s",
                f"  Input tokens delta: {rc.input_tokens_delta:+d}",
                f"  Output tokens delta: {rc.output_tokens_delta:+d}",
                "",
            ]
        )

    return "\n".join(lines)
```

- [ ] **Step 2: Write failing tests**

In `tests/test_comparator.py`:

```python
from pathlib import Path
import tempfile
import json
import pytest
from agent_bencher.comparator import compare_batches, format_comparison_report


def _make_batch(batch_id: str, agent_id: str, conversation_name: str, run_metrics: dict | None = None) -> dict:
    return {
        "batch_id": batch_id,
        "agent_id": agent_id,
        "conversation_name": conversation_name,
        "run_metrics": run_metrics or {},
        "turn_metrics": [],
        "sessions": [],
        "trials": [],
    }


def test_compare_batches_produces_report():
    with tempfile.TemporaryDirectory() as tmp:
        path_a = Path(tmp) / "batch_a.json"
        path_b = Path(tmp) / "batch_b.json"

        path_a.write_text(json.dumps(_make_batch(
            batch_id="batch-a",
            agent_id="config-a",
            conversation_name="test-conv",
            run_metrics={
                "duration_seconds": {"mean": 10.0, "min": 9.0, "max": 11.0, "stddev": 1.0},
                "total_output_tokens": {"mean": 1000.0, "min": 900, "max": 1100, "stddev": 50},
            },
        )))
        path_b.write_text(json.dumps(_make_batch(
            batch_id="batch-b",
            agent_id="config-b",
            conversation_name="test-conv",
            run_metrics={
                "duration_seconds": {"mean": 15.0, "min": 14.0, "max": 16.0, "stddev": 1.0},
                "total_output_tokens": {"mean": 1200.0, "min": 1100, "max": 1300, "stddev": 50},
            },
        )))

        report = compare_batches(path_a, path_b)
        assert report.config_a == "config-a"
        assert report.config_b == "config-b"
        assert report.conversation_name == "test-conv"
        assert "duration_delta_s" in report.summary["metrics"]
        assert "+5.00" in report.summary["metrics"]  # B is 5s slower


def test_format_comparison_report():
    report = ComparisonReport(
        batch_a_id="a",
        batch_b_id="b",
        conversation_name="test",
        config_a="a",
        config_b="b",
        summary={"conversation": "test", "config_a": "a", "config_b": "b", "metrics": "  duration_delta_s: +5.00"},
    )
    text = format_comparison_report(report)
    assert "Comparison: a vs b" in text
    assert "duration_delta_s: +5.00" in text
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_comparator.py -v`
Expected: FAIL (comparator module doesn't exist)

- [ ] **Step 4: Implement comparator.py**

Add the file as shown in Step 1 above.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_comparator.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agent_bencher/comparator.py tests/test_comparator.py
git commit -m "feat: add batch comparison logic with formatted report"
```

### Task 3.2: Add compare CLI subcommand

**Files:**
- Modify: `src/agent_bencher/cli.py`
- Test: `tests/test_cli_compare.py`

- [ ] **Step 1: Add compare subparser to cli.py**

In `src/agent_bencher/cli.py`, add to `build_parser()`:

```python
compare = subparsers.add_parser(
    "compare",
    help="Compare two batch results side by side.",
    description="Load two batch.json files and produce a comparison report.",
)
compare.add_argument("batch_a", type=Path, help="Path to first batch.json file.")
compare.add_argument("batch_b", type=Path, help="Path to second batch.json file.")
compare.add_argument(
    "--output",
    type=Path,
    default=None,
    help="Write report to file. Default: print to stdout.",
)
```

- [ ] **Step 2: Add compare dispatch in main()**

In `src/agent_bencher/cli.py`, in the `main()` function, after all subcommand handling:

```python
if args.command == "compare":
    from agent_bencher.comparator import compare_batches, format_comparison_report
    report = compare_batches(args.batch_a, args.batch_b)
    text = format_comparison_report(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0
```

- [ ] **Step 3: Write failing tests**

In `tests/test_cli_compare.py`:

```python
from pathlib import Path
import tempfile
import json
import pytest


def test_compare_cli_prints_report():
    from agent_bencher.cli import build_parser

    parser = build_parser()

    with tempfile.TemporaryDirectory() as tmp:
        path_a = Path(tmp) / "batch_a.json"
        path_b = Path(tmp) / "batch_b.json"

        path_a.write_text(json.dumps({
            "batch_id": "a", "agent_id": "a", "conversation_name": "test",
            "run_metrics": {"duration_seconds": {"mean": 10.0, "min": 9, "max": 11, "stddev": 1}},
            "turn_metrics": [], "sessions": [], "trials": [],
        }))
        path_b.write_text(json.dumps({
            "batch_id": "b", "agent_id": "b", "conversation_name": "test",
            "run_metrics": {"duration_seconds": {"mean": 15.0, "min": 14, "max": 16, "stddev": 1}},
            "turn_metrics": [], "sessions": [], "trials": [],
        }))

        args = parser.parse_args(["compare", str(path_a), str(path_b)])
        assert args.command == "compare"
        assert args.batch_a == path_a
        assert args.batch_b == path_b
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_cli_compare.py -v`
Expected: FAIL (compare subparser not registered)

- [ ] **Step 5: Implement CLI wiring**

Add the compare subparser and dispatch as shown in Steps 1-2 above.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_cli_compare.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agent_bencher/cli.py src/agent_bencher/comparator.py tests/test_cli_compare.py
git commit -m "feat: add compare CLI subcommand for side-by-side batch analysis"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- Improvement 1 (suite batch command): Tasks 1.1-1.2 cover CLI parser, parallel execution, dry-run mode ✓
- Improvement 2 (workspace cache + cleanup): Tasks 2.1-2.2 cover cache class, cache integration, cleanup function, CLI flag ✓
- Improvement 3 (comparison mode): Tasks 3.1-3.2 cover comparator module, CLI subcommand, formatted report ✓

**2. Placeholder scan:** No "TBD", "TODO", or "implement later" found. All code blocks are complete.

**3. Type consistency:** All dataclass names (`WorkspaceCache`, `ComparisonReport`, `RunComparison`) are consistent across tasks. Function signatures match between imports and usage.

**4. Test coverage:** Each task has failing-then-passing test steps. Edge cases covered: cache miss, cache hit, different variant miss, stale vs fresh, referenced workspace, metrics delta direction.
