# Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `charts` subcommand that reads existing benchmark `batch.json` artifacts and generates comparative static charts for one conversation.

**Architecture:** Keep the implementation in a single `src/agent_bencher/charts.py` module, as the spec requests, plus a small CLI extension in `src/agent_bencher/cli.py`. The charts module should load the existing serialized batch schema, resolve one representative batch per agent, and plot directly from those batch summaries without re-aggregating already-aggregated metrics across multiple batch files.

**Tech Stack:** Python 3.12+, matplotlib as an optional `charts` extra, argparse, existing `agent_bencher` batch artifact schema.

---

## File Structure

**New files to create:**
- `src/agent_bencher/charts.py` — chart loading, batch selection, plotting, and orchestration
- `tests/test_charts.py` — unit and integration tests for chart behavior

**Files to modify:**
- `src/agent_bencher/cli.py` — add `charts` subcommand and command handler
- `pyproject.toml` — add `charts` optional dependency

**Design decisions locked in:**
- Stay with a single `charts.py` module because the spec explicitly calls for it and the current codebase is still small.
- Reuse the existing `batch.json` schema written by `agent_bencher.results`; do not introduce new persistent data models.
- When an agent has multiple batches, select one chart source batch per agent instead of plotting duplicate bars or averaging multiple `batch.json` summaries together.
- Batch selection policy: newest `status == "completed"` batch wins; if none are completed, newest batch with `successful_runs > 0` wins; otherwise that agent is skipped.
- Import matplotlib inside plotting helpers so `bench` users do not need the charts extra installed unless they invoke charts.

---

### Task 1: Add dependency and CLI parser surface

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/agent_bencher/cli.py`
- Test: `tests/test_charts.py`

- [ ] **Step 1: Write the failing parser and dispatch tests**

Add these tests to `tests/test_charts.py`:

```python
from pathlib import Path

from agent_bencher.cli import build_parser, main


def test_build_parser_accepts_charts_runs_directory() -> None:
    parser = build_parser()

    parsed = parser.parse_args(["charts", "runs/sample-conversation"])

    assert parsed.command == "charts"
    assert parsed.input == Path("runs/sample-conversation")
    assert parsed.output_dir is None
    assert parsed.metric is None
    assert parsed.format == "png"


def test_build_parser_accepts_charts_yaml_and_flags() -> None:
    parser = build_parser()

    parsed = parser.parse_args(
        [
            "charts",
            "conversations/sample.yaml",
            "--output-dir",
            "/tmp/charts",
            "--metric",
            "output_tps",
            "--format",
            "svg",
        ]
    )

    assert parsed.command == "charts"
    assert parsed.input == Path("conversations/sample.yaml")
    assert parsed.output_dir == Path("/tmp/charts")
    assert parsed.metric == "output_tps"
    assert parsed.format == "svg"


def test_main_dispatches_charts_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_cmd_charts(args) -> int:
        captured["command"] = args.command
        captured["input"] = args.input
        return 7

    monkeypatch.setattr("agent_bencher.cli._cmd_charts", fake_cmd_charts)

    exit_code = main(["charts", "runs/sample-conversation"])

    assert exit_code == 7
    assert captured["command"] == "charts"
    assert captured["input"] == Path("runs/sample-conversation")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_charts.py::test_build_parser_accepts_charts_runs_directory tests/test_charts.py::test_build_parser_accepts_charts_yaml_and_flags tests/test_charts.py::test_main_dispatches_charts_command -v`

Expected: FAIL with `argparse` rejecting `charts` or `AttributeError: module 'agent_bencher.cli' has no attribute '_cmd_charts'`

- [ ] **Step 3: Add the dependency extra**

Update `pyproject.toml` so the optional dependencies section becomes:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9.0",
]
charts = [
  "matplotlib>=3.8,<4.0",
]
```

- [ ] **Step 4: Add parser support and command dispatch**

Update `src/agent_bencher/cli.py` with these changes.

Add this helper below `positive_int()`:

```python
def _cmd_charts(args: argparse.Namespace) -> int:
    from agent_bencher.charts import generate_charts

    try:
        generated = generate_charts(
            input_path=args.input,
            output_dir=args.output_dir,
            metric_filter=args.metric,
            output_format=args.format,
        )
    except ImportError as exc:
        print(
            "charts support requires the optional dependency: uv pip install .[charts]",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not generated:
        print("No charts generated (no chartable batch data found)", file=sys.stderr)
        return 0

    print(f"Generated {len(generated)} chart(s):", file=sys.stderr)
    for path in generated:
        print(f"  {path}", file=sys.stderr)
    return 0
```

Add this subparser inside `build_parser()` after the existing `bench` arguments:

```python
    charts = subparsers.add_parser(
        "charts",
        help="Generate comparative charts from benchmark batch artifacts.",
        description="Read benchmark batch.json files and generate comparative PNG or SVG charts.",
    )
    charts.add_argument(
        "input",
        type=Path,
        help="Path to a conversation YAML file or a runs/<conversation>/ directory.",
    )
    charts.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where chart files are written. Default: <conversation-runs>/charts",
    )
    charts.add_argument(
        "--metric",
        type=str,
        default=None,
        help="Generate only a specific metric.",
    )
    charts.add_argument(
        "--format",
        type=str,
        default="png",
        choices=["png", "svg"],
        help="Output format. Default: png",
    )
```

Replace the top of `main()` with this dispatch:

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "charts":
        return _cmd_charts(args)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_charts.py::test_build_parser_accepts_charts_runs_directory tests/test_charts.py::test_build_parser_accepts_charts_yaml_and_flags tests/test_charts.py::test_main_dispatches_charts_command -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/agent_bencher/cli.py tests/test_charts.py
git commit -m "feat: add charts CLI surface"
```

---

### Task 2: Create charts loading and batch-selection helpers

**Files:**
- Create: `src/agent_bencher/charts.py`
- Test: `tests/test_charts.py`

- [ ] **Step 1: Write the failing helper tests**

Append these tests to `tests/test_charts.py`:

```python
import json

from agent_bencher.charts import (
    _collect_chart_batches,
    _load_batch_data,
    _resolve_conversation_dir,
)


def _write_batch(
    batch_dir: Path,
    *,
    agent_id: str,
    batch_id: str,
    status: str = "completed",
    successful_runs: int = 1,
    duration_mean: float = 10.0,
) -> None:
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch.json").write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "conversation_name": "sample-conversation",
                "agent_id": agent_id,
                "frontend": "opencode",
                "backend_model": "model-x",
                "comment": "",
                "requested_runs": 1,
                "successful_runs": successful_runs,
                "failed_runs": 0 if successful_runs else 1,
                "started_at": "2026-06-01T00:00:00Z",
                "ended_at": "2026-06-01T00:00:01Z",
                "duration_seconds": duration_mean,
                "status": status,
                "run_metrics": {
                    "duration_seconds": {
                        "mean": duration_mean,
                        "min": duration_mean - 1.0,
                        "max": duration_mean + 1.0,
                        "stddev": 0.5,
                    },
                    "total_input_tokens": {
                        "mean": 100.0,
                        "min": 90.0,
                        "max": 110.0,
                        "stddev": 5.0,
                    },
                    "total_output_tokens": {
                        "mean": 50.0,
                        "min": 45.0,
                        "max": 55.0,
                        "stddev": 2.0,
                    },
                    "effective_output_tps": {
                        "mean": 5.0,
                        "min": 4.0,
                        "max": 6.0,
                        "stddev": 0.5,
                    },
                    "effective_total_throughput_tps": {
                        "mean": 15.0,
                        "min": 13.0,
                        "max": 17.0,
                        "stddev": 1.0,
                    },
                },
                "turn_metrics": [
                    {
                        "duration_seconds": {"mean": 2.0, "min": 1.5, "max": 2.5, "stddev": 0.1},
                        "output_tps": {"mean": 4.0, "min": 3.5, "max": 4.5, "stddev": 0.2},
                    },
                    {
                        "duration_seconds": {"mean": 3.0, "min": 2.5, "max": 3.5, "stddev": 0.1},
                        "output_tps": {"mean": 5.0, "min": 4.5, "max": 5.5, "stddev": 0.2},
                    },
                ],
            }
        )
    )


def test_load_batch_data_returns_none_for_missing_batch_json(tmp_path: Path) -> None:
    batch_dir = tmp_path / "missing"
    batch_dir.mkdir()

    assert _load_batch_data(batch_dir) is None


def test_load_batch_data_returns_dict_for_valid_batch_json(tmp_path: Path) -> None:
    batch_dir = tmp_path / "agent-a" / "2026-06-01T00-00-00"
    _write_batch(batch_dir, agent_id="agent-a", batch_id="2026-06-01T00-00-00")

    data = _load_batch_data(batch_dir)

    assert data is not None
    assert data["agent_id"] == "agent-a"
    assert data["run_metrics"]["duration_seconds"]["mean"] == 10.0


def test_resolve_conversation_dir_accepts_runs_directory(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    conversation_dir.mkdir(parents=True)

    result = _resolve_conversation_dir(conversation_dir)

    assert result == conversation_dir


def test_resolve_conversation_dir_accepts_yaml_input(tmp_path: Path) -> None:
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir()
    conversation_path = conversations_dir / "sample.yaml"
    conversation_path.write_text(
        "\n".join(
            [
                "name: sample-conversation",
                "source_workspace: ../workspace",
                "prompts:",
                "  - text: 'Prompt one'",
            ]
        )
    )
    runs_dir = tmp_path / "runs" / "sample-conversation"
    runs_dir.mkdir(parents=True)

    result = _resolve_conversation_dir(conversation_path)

    assert result == runs_dir


def test_collect_chart_batches_selects_latest_completed_batch_per_agent(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
        duration_mean=10.0,
    )
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T11-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T11-00-00",
        duration_mean=12.0,
    )
    _write_batch(
        conversation_dir / "agent-b" / "2026-06-01T09-00-00",
        agent_id="agent-b",
        batch_id="2026-06-01T09-00-00",
        duration_mean=20.0,
    )

    selected = _collect_chart_batches(conversation_dir)

    assert sorted(selected.keys()) == ["agent-a", "agent-b"]
    assert selected["agent-a"]["batch_id"] == "2026-06-01T11-00-00"
    assert selected["agent-a"]["run_metrics"]["duration_seconds"]["mean"] == 12.0


def test_collect_chart_batches_skips_agents_without_chartable_batches(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
        status="failed",
        successful_runs=0,
    )

    selected = _collect_chart_batches(conversation_dir)

    assert selected == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_charts.py::test_load_batch_data_returns_none_for_missing_batch_json tests/test_charts.py::test_load_batch_data_returns_dict_for_valid_batch_json tests/test_charts.py::test_resolve_conversation_dir_accepts_runs_directory tests/test_charts.py::test_resolve_conversation_dir_accepts_yaml_input tests/test_charts.py::test_collect_chart_batches_selects_latest_completed_batch_per_agent tests/test_charts.py::test_collect_chart_batches_skips_agents_without_chartable_batches -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_bencher.charts'`

- [ ] **Step 3: Create `src/agent_bencher/charts.py` with the loading and selection helpers**

Create `src/agent_bencher/charts.py` with this content:

```python
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from agent_bencher.suite import load_conversation


RUN_METRICS = [
    "duration_seconds",
    "total_input_tokens",
    "total_output_tokens",
    "effective_output_tps",
    "effective_total_throughput_tps",
]

TURN_METRICS = [
    "duration_seconds",
    "output_tps",
]

METRIC_LABELS = {
    "duration_seconds": "Duration (seconds)",
    "total_input_tokens": "Total Input Tokens",
    "total_output_tokens": "Total Output Tokens",
    "effective_output_tps": "Effective Output TPS",
    "effective_total_throughput_tps": "Effective Total Throughput TPS",
    "output_tps": "Output TPS",
}


def _load_batch_data(batch_dir: Path) -> dict[str, Any] | None:
    batch_path = batch_dir / "batch.json"
    if not batch_path.is_file():
        return None

    try:
        data = json.loads(batch_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    required_keys = {
        "batch_id",
        "agent_id",
        "status",
        "successful_runs",
        "run_metrics",
        "turn_metrics",
    }
    if not required_keys.issubset(data):
        return None

    if not isinstance(data["run_metrics"], dict) or not isinstance(data["turn_metrics"], list):
        return None

    return data


def _resolve_conversation_dir(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path

    if input_path.suffix not in {".yaml", ".yml"}:
        raise ValueError(f"input must be a conversation YAML file or runs directory: {input_path}")

    if not input_path.is_file():
        raise ValueError(f"input path not found: {input_path}")

    conversation = load_conversation(input_path)
    runs_dir = Path("runs") / conversation.name
    if not runs_dir.is_dir():
        raise ValueError(f"runs directory not found for conversation {conversation.name}: {runs_dir}")
    return runs_dir


def _batch_sort_key(batch: dict[str, Any]) -> tuple[str, str]:
    return (str(batch.get("batch_id", "")), str(batch.get("ended_at", "")))


def _is_chartable_batch(batch: dict[str, Any]) -> bool:
    return bool(batch.get("successful_runs", 0)) and bool(batch.get("run_metrics"))


def _select_chart_batch(agent_batches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not agent_batches:
        return None

    completed = [batch for batch in agent_batches if batch.get("status") == "completed" and _is_chartable_batch(batch)]
    if completed:
        return sorted(completed, key=_batch_sort_key)[-1]

    fallback = [batch for batch in agent_batches if _is_chartable_batch(batch)]
    if fallback:
        return sorted(fallback, key=_batch_sort_key)[-1]

    return None


def _collect_chart_batches(conversation_dir: Path) -> dict[str, dict[str, Any]]:
    if not conversation_dir.is_dir():
        return {}

    selected: dict[str, dict[str, Any]] = {}

    for agent_dir in sorted(conversation_dir.iterdir()):
        if not agent_dir.is_dir():
            continue

        agent_batches: list[dict[str, Any]] = []
        for batch_dir in sorted(agent_dir.iterdir()):
            if not batch_dir.is_dir():
                continue
            data = _load_batch_data(batch_dir)
            if data is not None:
                agent_batches.append(data)

        chosen = _select_chart_batch(agent_batches)
        if chosen is not None:
            selected[str(chosen["agent_id"])] = chosen

    return selected
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_charts.py::test_load_batch_data_returns_none_for_missing_batch_json tests/test_charts.py::test_load_batch_data_returns_dict_for_valid_batch_json tests/test_charts.py::test_resolve_conversation_dir_accepts_runs_directory tests/test_charts.py::test_resolve_conversation_dir_accepts_yaml_input tests/test_charts.py::test_collect_chart_batches_selects_latest_completed_batch_per_agent tests/test_charts.py::test_collect_chart_batches_skips_agents_without_chartable_batches -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/charts.py tests/test_charts.py
git commit -m "feat: add charts batch loading and selection helpers"
```

---

### Task 3: Implement grouped bar and per-turn line plotting

**Files:**
- Modify: `src/agent_bencher/charts.py`
- Test: `tests/test_charts.py`

- [ ] **Step 1: Write the failing plotting tests**

Append these tests to `tests/test_charts.py`:

```python
from agent_bencher.charts import _plot_grouped_bar_chart, _plot_per_turn_line_chart
def test_plot_grouped_bar_chart_creates_png_for_selected_agents(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    batch_a_dir = conversation_dir / "agent-a" / "2026-06-01T10-00-00"
    batch_b_dir = conversation_dir / "agent-b" / "2026-06-01T10-00-00"
    _write_batch(batch_a_dir, agent_id="agent-a", batch_id="2026-06-01T10-00-00", duration_mean=10.0)
    _write_batch(batch_b_dir, agent_id="agent-b", batch_id="2026-06-01T10-00-00", duration_mean=20.0)

    selected = _collect_chart_batches(conversation_dir)
    output_path = tmp_path / "duration.png"

    result = _plot_grouped_bar_chart(
        chart_batches=selected,
        metric_name="duration_seconds",
        title="Duration by Agent",
        y_label="Duration (seconds)",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 1000


def test_plot_grouped_bar_chart_raises_for_missing_metric(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    batch_a_dir = conversation_dir / "agent-a" / "2026-06-01T10-00-00"
    _write_batch(batch_a_dir, agent_id="agent-a", batch_id="2026-06-01T10-00-00")

    selected = _collect_chart_batches(conversation_dir)

    with pytest.raises(KeyError, match="nonexistent_metric"):
        _plot_grouped_bar_chart(
            chart_batches=selected,
            metric_name="nonexistent_metric",
            title="Missing",
            y_label="Missing",
            output_path=tmp_path / "missing.png",
        )


def test_plot_per_turn_line_chart_creates_png(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    batch_a_dir = conversation_dir / "agent-a" / "2026-06-01T10-00-00"
    batch_b_dir = conversation_dir / "agent-b" / "2026-06-01T10-00-00"
    _write_batch(batch_a_dir, agent_id="agent-a", batch_id="2026-06-01T10-00-00", duration_mean=10.0)
    _write_batch(batch_b_dir, agent_id="agent-b", batch_id="2026-06-01T10-00-00", duration_mean=20.0)

    selected = _collect_chart_batches(conversation_dir)
    output_path = tmp_path / "per-turn-output-tps.png"

    result = _plot_per_turn_line_chart(
        chart_batches=selected,
        metric_name="output_tps",
        title="Output TPS by Turn",
        y_label="Output TPS",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 1000


def test_plot_per_turn_line_chart_raises_when_metric_missing_from_all_turns(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    batch_a_dir = conversation_dir / "agent-a" / "2026-06-01T10-00-00"
    _write_batch(batch_a_dir, agent_id="agent-a", batch_id="2026-06-01T10-00-00")

    selected = _collect_chart_batches(conversation_dir)

    with pytest.raises(KeyError, match="input_tokens"):
        _plot_per_turn_line_chart(
            chart_batches=selected,
            metric_name="input_tokens",
            title="Input Tokens",
            y_label="Input Tokens",
            output_path=tmp_path / "missing-line.png",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_charts.py::test_plot_grouped_bar_chart_creates_png_for_selected_agents tests/test_charts.py::test_plot_grouped_bar_chart_raises_for_missing_metric tests/test_charts.py::test_plot_per_turn_line_chart_creates_png tests/test_charts.py::test_plot_per_turn_line_chart_raises_when_metric_missing_from_all_turns -v`

Expected: FAIL with `ImportError` or `AttributeError` because the plotting helpers do not exist yet

- [ ] **Step 3: Add plotting helpers to `src/agent_bencher/charts.py`**

Append these helpers to `src/agent_bencher/charts.py`:

```python
def _import_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _metric_summary(batch: dict[str, Any], metric_name: str) -> dict[str, float]:
    summary = batch["run_metrics"].get(metric_name)
    if summary is None:
        raise KeyError(metric_name)
    return summary


def _turn_metric_summary(batch: dict[str, Any], turn_index: int, metric_name: str) -> dict[str, float]:
    turn_metrics = batch["turn_metrics"]
    if turn_index >= len(turn_metrics):
        raise KeyError(metric_name)
    summary = turn_metrics[turn_index].get(metric_name)
    if summary is None:
        raise KeyError(metric_name)
    return summary


def _plot_grouped_bar_chart(
    chart_batches: dict[str, dict[str, Any]],
    metric_name: str,
    title: str,
    y_label: str,
    output_path: Path,
) -> Path:
    if not chart_batches:
        raise ValueError("no chart batches available")

    plt = _import_pyplot()

    agent_ids = sorted(chart_batches.keys())
    means: list[float] = []
    error_low: list[float] = []
    error_high: list[float] = []

    for agent_id in agent_ids:
        summary = _metric_summary(chart_batches[agent_id], metric_name)
        means.append(float(summary["mean"]))
        error_low.append(float(summary["mean"]) - float(summary["min"]))
        error_high.append(float(summary["max"]) - float(summary["mean"]))

    fig, ax = plt.subplots(figsize=(max(8, len(agent_ids) * 1.6), 5))
    x_positions = list(range(len(agent_ids)))
    ax.bar(
        x_positions,
        means,
        yerr=[error_low, error_high],
        capsize=4,
        color="#4C6EF5",
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(agent_ids, rotation=20, ha="right")
    ax.set_title(title)
    ax.set_ylabel(y_label)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def _plot_per_turn_line_chart(
    chart_batches: dict[str, dict[str, Any]],
    metric_name: str,
    title: str,
    y_label: str,
    output_path: Path,
) -> Path:
    if not chart_batches:
        raise ValueError("no chart batches available")

    plt = _import_pyplot()

    any_metric_found = False
    fig, ax = plt.subplots(figsize=(9, 5))

    for agent_id in sorted(chart_batches.keys()):
        batch = chart_batches[agent_id]
        means: list[float] = []
        error_low: list[float] = []
        error_high: list[float] = []
        x_values: list[int] = []

        for turn_index, turn_metrics in enumerate(batch["turn_metrics"]):
            summary = turn_metrics.get(metric_name)
            if summary is None:
                continue
            any_metric_found = True
            x_values.append(turn_index + 1)
            means.append(float(summary["mean"]))
            error_low.append(float(summary["mean"]) - float(summary["min"]))
            error_high.append(float(summary["max"]) - float(summary["mean"]))

        if not x_values:
            continue

        ax.errorbar(
            x_values,
            means,
            yerr=[error_low, error_high],
            marker="o",
            linewidth=1.5,
            capsize=3,
            label=agent_id,
        )

    if not any_metric_found:
        plt.close(fig)
        raise KeyError(metric_name)

    ax.set_title(title)
    ax.set_xlabel("Turn")
    ax.set_ylabel(y_label)
    ax.legend()
    ax.set_xticks(sorted({turn for batch in chart_batches.values() for turn in range(1, len(batch["turn_metrics"]) + 1)}))

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_charts.py::test_plot_grouped_bar_chart_creates_png_for_selected_agents tests/test_charts.py::test_plot_grouped_bar_chart_raises_for_missing_metric tests/test_charts.py::test_plot_per_turn_line_chart_creates_png tests/test_charts.py::test_plot_per_turn_line_chart_raises_when_metric_missing_from_all_turns -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/charts.py tests/test_charts.py
git commit -m "feat: add charts plotting helpers"
```

---

### Task 4: Implement orchestration and metric filtering

**Files:**
- Modify: `src/agent_bencher/charts.py`
- Test: `tests/test_charts.py`

- [ ] **Step 1: Write the failing orchestration tests**

Append these tests to `tests/test_charts.py`:

```python
from agent_bencher.charts import generate_charts


def test_generate_charts_creates_expected_default_files(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
        duration_mean=10.0,
    )
    _write_batch(
        conversation_dir / "agent-b" / "2026-06-01T10-00-00",
        agent_id="agent-b",
        batch_id="2026-06-01T10-00-00",
        duration_mean=20.0,
    )

    output_dir = tmp_path / "charts"
    generated = generate_charts(conversation_dir, output_dir=output_dir)

    names = {path.relative_to(output_dir).as_posix() for path in generated}
    assert names == {
        "duration_seconds.png",
        "total_input_tokens.png",
        "total_output_tokens.png",
        "effective_output_tps.png",
        "effective_total_throughput_tps.png",
        "per_turn/duration_seconds.png",
        "per_turn/output_tps.png",
    }


def test_generate_charts_honors_metric_filter(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
    )

    generated = generate_charts(
        conversation_dir,
        output_dir=tmp_path / "charts",
        metric_filter="output_tps",
    )

    names = {path.relative_to(tmp_path / "charts").as_posix() for path in generated}
    assert names == {"per_turn/output_tps.png"}


def test_generate_charts_rejects_unknown_metric_filter(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    conversation_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="unknown metric"):
        generate_charts(conversation_dir, metric_filter="not_a_metric")


def test_generate_charts_accepts_yaml_input(tmp_path: Path) -> None:
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir()
    conversation_path = conversations_dir / "sample.yaml"
    conversation_path.write_text(
        "\n".join(
            [
                "name: sample-conversation",
                "source_workspace: ../workspace",
                "prompts:",
                "  - text: 'Prompt one'",
            ]
        )
    )
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
    )

    generated = generate_charts(conversation_path, output_dir=tmp_path / "charts")

    assert generated


def test_generate_charts_returns_empty_when_no_chartable_batches_exist(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"
    _write_batch(
        conversation_dir / "agent-a" / "2026-06-01T10-00-00",
        agent_id="agent-a",
        batch_id="2026-06-01T10-00-00",
        status="failed",
        successful_runs=0,
    )

    generated = generate_charts(conversation_dir, output_dir=tmp_path / "charts")

    assert generated == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_charts.py::test_generate_charts_creates_expected_default_files tests/test_charts.py::test_generate_charts_honors_metric_filter tests/test_charts.py::test_generate_charts_rejects_unknown_metric_filter tests/test_charts.py::test_generate_charts_accepts_yaml_input tests/test_charts.py::test_generate_charts_returns_empty_when_no_chartable_batches_exist -v`

Expected: FAIL with `ImportError` or `AttributeError` because `generate_charts` is not implemented

- [ ] **Step 3: Implement `generate_charts`**

Append this code to `src/agent_bencher/charts.py`:

```python
def _validate_metric_filter(metric_filter: str | None) -> None:
    if metric_filter is None:
        return

    allowed = set(RUN_METRICS) | set(TURN_METRICS)
    if metric_filter not in allowed:
        raise ValueError(f"unknown metric: {metric_filter}")


def generate_charts(
    input_path: Path,
    output_dir: Path | None = None,
    metric_filter: str | None = None,
    output_format: str = "png",
) -> list[Path]:
    _validate_metric_filter(metric_filter)
    conversation_dir = _resolve_conversation_dir(input_path)
    chart_batches = _collect_chart_batches(conversation_dir)
    if not chart_batches:
        return []

    if output_dir is None:
        output_dir = conversation_dir / "charts"

    generated: list[Path] = []

    run_metrics = [metric_filter] if metric_filter in RUN_METRICS else RUN_METRICS
    turn_metrics = [metric_filter] if metric_filter in TURN_METRICS else TURN_METRICS

    for metric_name in run_metrics:
        if metric_name is None:
            continue
        try:
            generated.append(
                _plot_grouped_bar_chart(
                    chart_batches=chart_batches,
                    metric_name=metric_name,
                    title=f"{METRIC_LABELS.get(metric_name, metric_name)} by Agent",
                    y_label=METRIC_LABELS.get(metric_name, metric_name),
                    output_path=output_dir / f"{metric_name}.{output_format}",
                )
            )
        except KeyError:
            continue

    per_turn_dir = output_dir / "per_turn"
    for metric_name in turn_metrics:
        if metric_name is None:
            continue
        try:
            generated.append(
                _plot_per_turn_line_chart(
                    chart_batches=chart_batches,
                    metric_name=metric_name,
                    title=f"{METRIC_LABELS.get(metric_name, metric_name)} by Turn",
                    y_label=METRIC_LABELS.get(metric_name, metric_name),
                    output_path=per_turn_dir / f"{metric_name}.{output_format}",
                )
            )
        except KeyError:
            continue

    return generated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_charts.py::test_generate_charts_creates_expected_default_files tests/test_charts.py::test_generate_charts_honors_metric_filter tests/test_charts.py::test_generate_charts_rejects_unknown_metric_filter tests/test_charts.py::test_generate_charts_accepts_yaml_input tests/test_charts.py::test_generate_charts_returns_empty_when_no_chartable_batches_exist -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/charts.py tests/test_charts.py
git commit -m "feat: implement charts orchestration"
```

---

### Task 5: Add command-handler behavior tests and edge cases

**Files:**
- Modify: `src/agent_bencher/cli.py`
- Modify: `tests/test_charts.py`

- [ ] **Step 1: Write the failing command-handler tests**

Append these tests to `tests/test_charts.py`:

```python
def test_cmd_charts_returns_error_for_unknown_metric(monkeypatch, tmp_path: Path, capsys) -> None:
    from agent_bencher.cli import _cmd_charts

    class Args:
        input = tmp_path / "runs" / "sample-conversation"
        output_dir = None
        metric = "bad-metric"
        format = "png"

    monkeypatch.setattr(
        "agent_bencher.charts.generate_charts",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("unknown metric: bad-metric")),
    )

    exit_code = _cmd_charts(Args())

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown metric: bad-metric" in captured.err


def test_cmd_charts_reports_missing_optional_dependency(monkeypatch, tmp_path: Path, capsys) -> None:
    from agent_bencher.cli import _cmd_charts

    class Args:
        input = tmp_path / "runs" / "sample-conversation"
        output_dir = None
        metric = None
        format = "png"

    monkeypatch.setattr(
        "agent_bencher.charts.generate_charts",
        lambda **kwargs: (_ for _ in ()).throw(ImportError("No module named matplotlib")),
    )

    exit_code = _cmd_charts(Args())

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "uv pip install .[charts]" in captured.err


def test_cmd_charts_reports_generated_files(monkeypatch, tmp_path: Path, capsys) -> None:
    from agent_bencher.cli import _cmd_charts

    class Args:
        input = tmp_path / "runs" / "sample-conversation"
        output_dir = tmp_path / "charts"
        metric = None
        format = "png"

    chart_paths = [tmp_path / "charts" / "duration_seconds.png", tmp_path / "charts" / "per_turn" / "output_tps.png"]
    monkeypatch.setattr("agent_bencher.charts.generate_charts", lambda **kwargs: chart_paths)

    exit_code = _cmd_charts(Args())

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Generated 2 chart(s):" in captured.err
    assert "duration_seconds.png" in captured.err
    assert "per_turn/output_tps.png" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_charts.py::test_cmd_charts_returns_error_for_unknown_metric tests/test_charts.py::test_cmd_charts_reports_missing_optional_dependency tests/test_charts.py::test_cmd_charts_reports_generated_files -v`

Expected: FAIL because `_cmd_charts` output or error handling does not yet match

- [ ] **Step 3: Tighten `_cmd_charts` output handling if needed**

Ensure `src/agent_bencher/cli.py` uses exactly this helper body:

```python
def _cmd_charts(args: argparse.Namespace) -> int:
    from agent_bencher.charts import generate_charts

    try:
        generated = generate_charts(
            input_path=args.input,
            output_dir=args.output_dir,
            metric_filter=args.metric,
            output_format=args.format,
        )
    except ImportError as exc:
        print(
            "charts support requires the optional dependency: uv pip install .[charts]",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not generated:
        print("No charts generated (no chartable batch data found)", file=sys.stderr)
        return 0

    print(f"Generated {len(generated)} chart(s):", file=sys.stderr)
    for path in generated:
        print(f"  {path}", file=sys.stderr)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_charts.py::test_cmd_charts_returns_error_for_unknown_metric tests/test_charts.py::test_cmd_charts_reports_missing_optional_dependency tests/test_charts.py::test_cmd_charts_reports_generated_files -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/cli.py tests/test_charts.py
git commit -m "test: cover charts command handler behavior"
```

---

### Task 6: Add end-to-end integration coverage for real directory shape

**Files:**
- Modify: `tests/test_charts.py`

- [ ] **Step 1: Write the failing integration test**

Append this test to `tests/test_charts.py`:

```python
def test_generate_charts_uses_one_batch_per_agent_in_realistic_layout(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "runs" / "sample-conversation"

    _write_batch(
        conversation_dir / "agent-one" / "2026-06-01T10-00-00",
        agent_id="agent-one",
        batch_id="2026-06-01T10-00-00",
        duration_mean=10.0,
    )
    _write_batch(
        conversation_dir / "agent-one" / "2026-06-01T11-00-00",
        agent_id="agent-one",
        batch_id="2026-06-01T11-00-00",
        duration_mean=12.0,
    )
    _write_batch(
        conversation_dir / "agent-two" / "2026-06-01T09-00-00",
        agent_id="agent-two",
        batch_id="2026-06-01T09-00-00",
        duration_mean=25.0,
    )

    generated = generate_charts(conversation_dir, output_dir=tmp_path / "charts")

    assert len(generated) == 7
    assert (tmp_path / "charts" / "duration_seconds.png").exists()
    assert (tmp_path / "charts" / "per_turn" / "output_tps.png").exists()

    selected = _collect_chart_batches(conversation_dir)
    assert selected["agent-one"]["batch_id"] == "2026-06-01T11-00-00"
    assert selected["agent-two"]["batch_id"] == "2026-06-01T09-00-00"
```

- [ ] **Step 2: Run the integration test to verify it fails if selection/orchestration regresses**

Run: `pytest tests/test_charts.py::test_generate_charts_uses_one_batch_per_agent_in_realistic_layout -v`

Expected: PASS if previous tasks are complete; if it fails, fix the selection/orchestration code before continuing

- [ ] **Step 3: Run the full targeted test file**

Run: `pytest tests/test_charts.py -v`

Expected: PASS

- [ ] **Step 4: Verify against the sample run artifacts in the repository**

Run: `python -m agent_bencher charts runs/sample-conversation --output-dir /tmp/sample-charts`

Expected: output lists generated chart files under `/tmp/sample-charts`

Run: `ls -1 /tmp/sample-charts`

Expected:

```text
duration_seconds.png
effective_output_tps.png
effective_total_throughput_tps.png
per_turn
total_input_tokens.png
total_output_tokens.png
```

Run: `ls -1 /tmp/sample-charts/per_turn`

Expected:

```text
duration_seconds.png
output_tps.png
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_charts.py
git commit -m "test: add end-to-end charts integration coverage"
```

---

## Self-Review

**1. Spec coverage:**
- Single `charts.py` module: covered by Tasks 2-4
- Reads `batch.json` produced by `bench`: covered by Task 2 helper tests and implementation
- Grouped bar charts with min/max error bars: covered by Task 3
- Per-turn line charts: covered by Task 3
- CLI `charts` subcommand with `--output-dir`, `--metric`, and `--format`: covered by Task 1
- YAML or runs-directory input: covered by Task 2 and Task 4
- Multiple batches per agent: covered explicitly by Task 2 selection logic and Task 6 integration
- Optional matplotlib dependency: covered by Task 1 and Task 5

**2. Placeholder scan:**
- No `TODO`, `TBD`, or “similar to above” steps remain
- Every code-changing step includes concrete code
- Every verification step includes an exact command and expected result

**3. Type consistency:**
- CLI always calls `generate_charts(input_path=..., output_dir=..., metric_filter=..., output_format=...)`
- Internal chart data shape stays `dict[str, Any]` loaded from `batch.json`
- Multi-batch handling always means “select one representative batch per agent,” not “average multiple batch summaries together”

---

Plan complete and saved to `docs/superpowers/plans/2026-06-04-charts-superior.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
