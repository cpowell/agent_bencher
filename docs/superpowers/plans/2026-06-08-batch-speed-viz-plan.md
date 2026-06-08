# Batch Speed Viz Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `viz` CLI subcommand that generates matplotlib bar charts comparing agent run speeds across configs.

**Architecture:** A new `viz.py` module handles data loading and chart generation. The existing `cli.py` gets a `viz` subcommand that delegates to it. Charts are saved as PNG files in `runs/<conversation>/viz/`.

**Tech Stack:** Python 3.12+, matplotlib (new dependency), existing PyYAML-based JSON reading.

---

### Task 1: Add matplotlib dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add matplotlib to project dependencies**

Add `matplotlib>=3.8` to the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
  "PyYAML>=6.0,<7.0",
  "matplotlib>=3.8",
  "tqdm>=4.66,<5.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: matplotlib installed successfully, no errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add matplotlib for chart generation"
```

---

### Task 2: Create the viz module with data loading

**Files:**
- Create: `src/agent_bencher/viz.py`

- [ ] **Step 1: Write the viz module with data loading functions**

Create `src/agent_bencher/viz.py` with the following content:

```python
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import mean, stdev


def load_agent_runs(conversation_dir: Path) -> dict[str, dict[str, list[float]]]:
    """Load speed metrics from the latest batch of each agent config.

    Returns a dict mapping agent_id to a dict of metric_name -> list of trial values.
    """
    if not conversation_dir.is_dir():
        print(f"Error: '{conversation_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    agent_dirs = sorted(
        d for d in conversation_dir.iterdir() if d.is_dir() and d.name != "viz"
    )
    if not agent_dirs:
        print(f"Error: no agent configs found in '{conversation_dir}'", file=sys.stderr)
        sys.exit(1)

    # Metric paths: maps metric name to the JSON path within run.json
    metric_paths = {
        "duration_seconds": ["duration_seconds"],
        "effective_output_tps": ["effective_output_tps"],
        "effective_total_throughput_tps": ["effective_total_throughput_tps"],
    }

    agents: dict[str, dict[str, list[float]]] = {}

    for agent_dir in agent_dirs:
        batch_runs = sorted(d for d in agent_dir.iterdir() if d.is_dir())
        if not batch_runs:
            print(f"Warning: no batch runs in '{agent_dir}'", file=sys.stderr)
            continue

        latest_batch = batch_runs[-1]
        batch_json = latest_batch / "batch.json"

        if not batch_json.exists():
            print(f"Warning: no batch.json in '{latest_batch}'", file=sys.stderr)
            continue

        trials_dir = latest_batch / "trials"
        if not trials_dir.is_dir():
            print(f"Warning: no trials dir in '{latest_batch}'", file=sys.stderr)
            continue

        trial_dirs = sorted(d for d in trials_dir.iterdir() if d.is_dir())
        if not trial_dirs:
            print(f"Warning: no trials in '{latest_batch}'", file=sys.stderr)
            continue

        # Read batch.json for agent_id
        with open(batch_json) as f:
            batch_data = json.load(f)

        agent_id = batch_data.get("agent_id", agent_dir.name)

        # Collect per-trial metrics
        trial_metrics: dict[str, list[float]] = {m: [] for m in metric_paths}

        for trial_dir in trial_dirs:
            run_json = trial_dir / "run.json"
            if not run_json.exists():
                continue

            with open(run_json) as f:
                run_data = json.load(f)

            for metric_name, path in metric_paths.items():
                value = run_data
                for key in path:
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                if value is not None and isinstance(value, (int, float)):
                    trial_metrics[metric_name].append(float(value))

        # Skip agents with no valid trial data
        if not any(trial_metrics[m] for m in trial_metrics):
            print(f"Warning: no valid trial data for agent '{agent_id}'", file=sys.stderr)
            continue

        agents[agent_id] = trial_metrics

    if not agents:
        print("Error: no valid agent data found", file=sys.stderr)
        sys.exit(1)

    return agents
```

- [ ] **Step 2: Run syntax check**

Run: `python -c "import ast; ast.parse(open('src/agent_bencher/viz.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agent_bencher/viz.py
git commit -m "feat: add viz module with data loading"
```

---

### Task 3: Create the chart generation functions

**Files:**
- Modify: `src/agent_bencher/viz.py`

- [ ] **Step 1: Add chart generation functions to viz.py**

Append the following to `src/agent_bencher/viz.py`:

```python
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def _format_value(val: float, metric: str) -> str:
    """Format a numeric value for display on charts."""
    if metric == "duration_seconds":
        return f"{val:.1f}s"
    return f"{val:.1f}"


def _set_ylabel(ax: plt.Axes, metric: str) -> None:
    """Set descriptive y-axis label based on metric."""
    labels = {
        "duration_seconds": "Wall Clock Duration (seconds)",
        "effective_output_tps": "Output Tokens/sec",
        "effective_total_throughput_tps": "Total Throughput (tokens/sec)",
    }
    ax.set_ylabel(labels[metric])


def _set_title(metric: str) -> str:
    """Return chart title for the given metric."""
    titles = {
        "duration_seconds": "Completion Time",
        "effective_output_tps": "Output Throughput (TPS)",
        "effective_total_throughput_tps": "Total Throughput (TPS)",
    }
    return titles[metric]


def generate_bar_chart(
    agents: dict[str, dict[str, list[float]]],
    metric: str,
    output_path: Path,
) -> None:
    """Generate a grouped bar chart with error bars for a single metric.

    Args:
        agents: Mapping of agent_id -> {metric_name: [trial_values]}
        metric: Which metric to chart
        output_path: Where to save the PNG file
    """
    agent_ids = list(agents.keys())
    means = []
    stds = []
    has_error = []

    for agent_id in agent_ids:
        values = agents[agent_id].get(metric, [])
        if not values:
            means.append(0.0)
            stds.append(0.0)
            has_error.append(False)
        elif len(values) == 1:
            means.append(values[0])
            stds.append(0.0)
            has_error.append(False)
        else:
            means.append(mean(values))
            stds.append(stdev(values))
            has_error.append(True)

    x = range(len(agent_ids))
    bars = plt.bar(x, means, yerr=[stds if h else [0.0] * len(stds) for h in has_error],
                   capsize=4, width=0.6, edgecolor="black", linewidth=0.5)

    plt.xticks(x, agent_ids, rotation=45, ha="right", fontsize=8)
    _set_ylabel(plt.gca(), metric)
    plt.title(_set_title(metric))
    plt.gca().yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.1f}"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
```

- [ ] **Step 2: Run syntax check**

Run: `python -c "import ast; ast.parse(open('src/agent_bencher/viz.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agent_bencher/viz.py
git commit -m "feat: add matplotlib chart generation functions"
```

---

### Task 4: Wire up the CLI subcommand

**Files:**
- Modify: `src/agent_bencher/cli.py`

- [ ] **Step 1: Add viz subcommand to cli.py**

Add the import at the top of `cli.py` (after the existing imports):

```python
from agent_bencher.viz import generate_bar_chart, load_agent_runs
```

Add a `viz` function before `main()`:

```python
def viz(args: argparse.Namespace) -> int:
    """Generate speed comparison charts from run artifacts."""
    conversation_dir = args.conversation_dir
    if not conversation_dir.is_absolute():
        conversation_dir = Path.cwd() / conversation_dir

    agents = load_agent_runs(conversation_dir)

    viz_dir = conversation_dir / "viz"
    viz_dir.mkdir(exist_ok=True)

    metrics = [
        ("duration_seconds", "duration.png"),
        ("effective_output_tps", "output_tps.png"),
        ("effective_total_throughput_tps", "total_throughput_tps.png"),
    ]

    for metric_key, filename in metrics:
        output_path = viz_dir / filename
        generate_bar_chart(agents, metric_key, output_path)
        print(f"Generated: {output_path}", file=sys.stderr)

    return 0
```

Add the `viz` subparser in `build_parser()`, inside the `subparsers = parser.add_subparsers(...)` block:

```python
    viz_parser = subparsers.add_parser(
        "viz",
        help="Generate speed comparison charts from run artifacts.",
        description="Read batch runs from a conversation directory and generate matplotlib bar charts.",
    )
    viz_parser.add_argument(
        "conversation_dir",
        type=Path,
        help="Path to a conversation directory under runs/ (e.g., runs/sample-conversation).",
    )
    viz_parser.set_defaults(func=viz)
```

Add the dispatch in `main()`, after `args = parser.parse_args(argv)`:

```python
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)
```

- [ ] **Step 2: Run syntax check**

Run: `python -c "import ast; ast.parse(open('src/agent_bencher/cli.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Test the CLI help**

Run: `uv run python -m agent_bencher viz --help`
Expected: Shows help text for the viz subcommand with description and arguments.

- [ ] **Step 4: Test with real data**

Run: `uv run python -m agent_bencher viz runs/sample-conversation`
Expected: Three PNG files generated in `runs/sample-conversation/viz/` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/cli.py
git commit -m "feat: add viz CLI subcommand for speed comparison charts"
```

---

### Task 5: Add tests

**Files:**
- Create: `tests/test_viz.py`

- [ ] **Step 1: Write tests for viz module**

Create `tests/test_viz.py`:

```python
from pathlib import Path
import json
import tempfile
from unittest.mock import patch

import pytest

from agent_bencher.viz import load_agent_runs, generate_bar_chart


def _write_run_json(dir_path: Path, duration: float, output_tps: float, total_tps: float) -> None:
    """Helper to write a minimal run.json for testing."""
    run_data = {
        "run_id": "test-run",
        "duration_seconds": duration,
        "effective_output_tps": output_tps,
        "effective_total_throughput_tps": total_tps,
        "prompts_attempted": 3,
        "prompts_completed": 3,
        "status": "completed",
    }
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "run.json").write_text(json.dumps(run_data))


def _write_batch_json(batch_dir: Path, agent_id: str) -> None:
    """Helper to write a minimal batch.json for testing."""
    batch_data = {
        "batch_id": "test-batch",
        "agent_id": agent_id,
        "trials": [
            {"trial_id": "trial-001", "path": "trials/trial-001"},
            {"trial_id": "trial-002", "path": "trials/trial-002"},
        ],
    }
    (batch_dir / "batch.json").write_text(json.dumps(batch_data))


class TestLoadAgentRuns:
    def test_loads_multiple_agents(self, tmp_path: Path) -> None:
        conv_dir = tmp_path / "test-conv"

        # Agent A: two trials
        agent_a = conv_dir / "agent-a" / "batch-1" / "trials" / "trial-001"
        _write_run_json(agent_a, duration=100.0, output_tps=20.0, total_tps=1000.0)
        agent_a2 = conv_dir / "agent-a" / "batch-1" / "trials" / "trial-002"
        _write_run_json(agent_a2, duration=120.0, output_tps=25.0, total_tps=1100.0)
        _write_batch_json(conv_dir / "agent-a" / "batch-1", "agent-a")

        # Agent B: two trials
        agent_b = conv_dir / "agent-b" / "batch-1" / "trials" / "trial-001"
        _write_run_json(agent_b, duration=80.0, output_tps=30.0, total_tps=1500.0)
        agent_b2 = conv_dir / "agent-b" / "batch-1" / "trials" / "trial-002"
        _write_run_json(agent_b2, duration=90.0, output_tps=28.0, total_tps=1400.0)
        _write_batch_json(conv_dir / "agent-b" / "batch-1", "agent-b")

        result = load_agent_runs(conv_dir)

        assert "agent-a" in result
        assert "agent-b" in result
        assert len(result["agent-a"]["duration_seconds"]) == 2
        assert len(result["agent-b"]["duration_seconds"]) == 2

    def test_selects_latest_batch(self, tmp_path: Path) -> None:
        conv_dir = tmp_path / "test-conv"

        # Older batch (should be ignored)
        old = conv_dir / "agent-x" / "batch-1" / "trials" / "trial-001"
        _write_run_json(old, duration=500.0, output_tps=5.0, total_tps=500.0)
        _write_batch_json(conv_dir / "agent-x" / "batch-1", "agent-x")

        # Newer batch (should be used)
        new = conv_dir / "agent-x" / "batch-2" / "trials" / "trial-001"
        _write_run_json(new, duration=100.0, output_tps=20.0, total_tps=1000.0)
        _write_batch_json(conv_dir / "agent-x" / "batch-2", "agent-x")

        result = load_agent_runs(conv_dir)

        assert result["agent-x"]["duration_seconds"] == [100.0]

    def test_excludes_viz_directory(self, tmp_path: Path) -> None:
        conv_dir = tmp_path / "test-conv"
        viz_dir = conv_dir / "viz"
        viz_dir.mkdir()

        agent = conv_dir / "agent-y" / "batch-1" / "trials" / "trial-001"
        _write_run_json(agent, duration=100.0, output_tps=20.0, total_tps=1000.0)
        _write_batch_json(conv_dir / "agent-y" / "batch-1", "agent-y")

        result = load_agent_runs(conv_dir)
        assert "viz" not in result

    def test_error_on_nonexistent_directory(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            load_agent_runs(tmp_path / "nonexistent")

    def test_error_on_empty_directory(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            load_agent_runs(tmp_path)

    def test_skips_agent_with_no_batch_json(self, tmp_path: Path) -> None:
        conv_dir = tmp_path / "test-conv"
        agent_dir = conv_dir / "agent-no-batch" / "batch-1" / "trials" / "trial-001"
        agent_dir.mkdir(parents=True)
        _write_run_json(agent_dir, duration=100.0, output_tps=20.0, total_tps=1000.0)
        # No batch.json written

        with pytest.raises(SystemExit):
            load_agent_runs(conv_dir)


class TestGenerateBarChart:
    def test_generates_png_file(self, tmp_path: Path) -> None:
        agents = {
            "agent-a": {"duration_seconds": [100.0, 120.0], "effective_output_tps": [20.0, 25.0],
                        "effective_total_throughput_tps": [1000.0, 1100.0]},
            "agent-b": {"duration_seconds": [80.0, 90.0], "effective_output_tps": [30.0, 28.0],
                        "effective_total_throughput_tps": [1500.0, 1400.0]},
        }
        output = tmp_path / "test_chart.png"

        generate_bar_chart(agents, "duration_seconds", output)

        assert output.exists()
        assert output.stat().st_size > 1000  # Reasonable minimum file size

    def test_single_trial_no_error_bar(self, tmp_path: Path) -> None:
        agents = {
            "agent-single": {"duration_seconds": [200.0], "effective_output_tps": [15.0],
                             "effective_total_throughput_tps": [900.0]},
        }
        output = tmp_path / "single_trial.png"

        generate_bar_chart(agents, "duration_seconds", output)

        assert output.exists()

    def test_chart_has_correct_number_of_bars(self, tmp_path: Path) -> None:
        agents = {
            "agent-a": {"duration_seconds": [100.0, 120.0], "effective_output_tps": [20.0, 25.0],
                        "effective_total_throughput_tps": [1000.0, 1100.0]},
            "agent-b": {"duration_seconds": [80.0, 90.0], "effective_output_tps": [30.0, 28.0],
                        "effective_total_throughput_tps": [1500.0, 1400.0]},
            "agent-c": {"duration_seconds": [150.0, 160.0], "effective_output_tps": [10.0, 12.0],
                        "effective_total_throughput_tps": [600.0, 650.0]},
        }
        output = tmp_path / "three_agents.png"

        generate_bar_chart(agents, "duration_seconds", output)

        assert output.exists()
        assert output.stat().st_size > 1000

    def test_chart_with_single_trial_no_stddev(self, tmp_path: Path) -> None:
        agents = {
            "agent-single": {"duration_seconds": [200.0], "effective_output_tps": [15.0],
                             "effective_total_throughput_tps": [900.0]},
        }
        output = tmp_path / "single_trial.png"

        generate_bar_chart(agents, "duration_seconds", output)

        assert output.exists()


class TestVizCLI:
    def test_viz_command_generates_files(self, tmp_path: Path) -> None:
        from agent_bencher.cli import build_parser

        conv_dir = tmp_path / "test-conv"

        # Set up test data
        agent = conv_dir / "agent-fast" / "batch-1" / "trials" / "trial-001"
        _write_run_json(agent, duration=50.0, output_tps=40.0, total_tps=2000.0)
        agent2 = conv_dir / "agent-fast" / "batch-1" / "trials" / "trial-002"
        _write_run_json(agent2, duration=60.0, output_tps=35.0, total_tps=1800.0)
        _write_batch_json(conv_dir / "agent-fast" / "batch-1", "agent-fast")

        agent_slow = conv_dir / "agent-slow" / "batch-1" / "trials" / "trial-001"
        _write_run_json(agent_slow, duration=200.0, output_tps=10.0, total_tps=500.0)
        _write_batch_json(conv_dir / "agent-slow" / "batch-1", "agent-slow")

        parser = build_parser()
        args = parser.parse_args(["viz", str(conv_dir)])

        # Call the viz function directly (it's now imported in cli.py)
        from agent_bencher.cli import viz
        result = viz(args)

        assert result == 0
        viz_dir = conv_dir / "viz"
        assert (viz_dir / "duration.png").exists()
        assert (viz_dir / "output_tps.png").exists()
        assert (viz_dir / "total_throughput_tps.png").exists()
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_viz.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_viz.py
git commit -m "test: add tests for viz module"
```

---

### Task 6: Run full test suite

**Files:**
- Modify: (none - verification only)

- [ ] **Step 1: Run all existing tests**

Run: `uv run pytest`
Expected: All tests pass, including the new viz tests.

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: verify full test suite passes"
```
