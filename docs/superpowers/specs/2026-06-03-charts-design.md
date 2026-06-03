# Charts Module Design

## Purpose

Generate comparative static charts from agent-bencher benchmark runs for internal analysis. The goal is to quickly spot performance patterns, outliers, and tradeoffs between agent configurations.

## Scope

- Reads from existing `batch.json` files produced by `agent-bencher bench`
- Generates side-by-side bar charts with error bars (min/max range) for run-level metrics
- Generates per-turn line charts showing how each agent performs across turns
- Outputs static PNG files to a configurable directory

## Module Structure

```
src/agent_bencher/
├── charts.py          # Core chart generation (matplotlib)
└── cli.py             # (existing) + new "charts" subcommand
```

A single `charts.py` module. No new top-level package.

## Components

### `generate_charts(batch_dir: Path, output_dir: Path | None = None) -> list[Path]`

Orchestrator. Scans `runs/<conversation>/` for agent subdirectories, finds all `batch.json` files, and generates chart PNGs. Returns list of generated file paths.

### `_load_batch_data(batch_dir: Path) -> dict`

Reads and validates a single `batch.json` file. Returns the parsed dict.

### `_plot_bar_chart(data: list[dict], metric_name: str, title: str, y_label: str, output_path: Path, *, log_scale: bool = False) -> Path`

Generates a side-by-side bar chart with error bars (min/max range) for a single metric across agents.

### `_plot_grouped_bar_chart(all_batches: list[dict], metric_name: str, title: str, y_label: str, output_path: Path) -> Path`

Compares the same metric across multiple agents (multiple batch.json files).

### `_plot_per_turn_line_chart(all_batches: list[dict], metric_name: str, title: str, y_label: str, output_path: Path) -> Path`

Generates a per-turn line chart showing how each agent's performance changes across turns.

## Data Flow

```
runs/<conversation>/<agent-id>/<batch-id>/batch.json
    │
    │  _load_batch_data()
    ▼
dict with run_metrics, turn_metrics
    │
    │  generate_charts() collects across all agents
    ▼
_plot_grouped_bar_chart()  →  charts/<metric>.png
_plot_per_turn_line_chart() →  charts/per_turn/<metric>.png
```

1. `generate_charts()` scans `runs/<conversation>/` for agent subdirectories
2. For each agent, finds ALL `batch.json` files (not just the latest)
3. Extracts `run_metrics` and `turn_metrics` from each
4. Calls `_plot_grouped_bar_chart()` for each run-level metric (one chart per metric, all agents side-by-side)
5. Calls `_plot_per_turn_line_chart()` for key metrics (duration, output_tps) across all 5 turns

## CLI Interface

```bash
# Generate charts for a single conversation
agent-bencher charts conversations/sample-conversation.yaml

# Generate charts and save to a custom directory
agent-bencher charts conversations/sample-conversation.yaml --output-dir /tmp/charts

# Generate charts from existing run artifacts (no YAML needed)
agent-bencher charts runs/sample-conversation/
```

**Flags:**
- `--output-dir` — where to write PNGs (default: `runs/<conversation>/charts/`)
- `--metric` — generate only a specific metric (e.g., `--metric output_tps`)
- `--format` — output format: `png` (default) or `svg`

**Subcommand registration in `cli.py`:**
```python
charts = subparsers.add_parser(
    "charts",
    help="Generate comparative bar/line charts from benchmark runs.",
)
charts.add_argument("input", help="Path to conversation YAML or runs/<conversation>/ directory.")
charts.add_argument("--output-dir", type=Path, default=None)
charts.add_argument("--metric", type=str, default=None)
charts.add_argument("--format", type=str, default="png", choices=["png", "svg"])
```

## Error Handling

- Missing `batch.json` — skip that agent, log a warning, continue with others
- Incomplete metrics (e.g., a batch with no `turn_metrics`) — skip per-turn charts, still generate run-level charts
- No completed runs in a batch — skip that agent entirely
- All agents fail — return empty list, exit 0 (not an error, just no data to chart)
- Invalid metric name in `--metric` flag — exit 1 with usage hint

## Testing

- Unit tests for `_load_batch_data()` with valid/missing/invalid batch.json
- Unit tests for `_plot_bar_chart()` and `_plot_grouped_bar_chart()` — verify matplotlib figure creation, axis labels, error bar rendering (use `matplotlib.use("Agg")` for headless testing)
- Integration test: feed real `batch.json` from `runs/`, verify PNG files are created with expected names
- Test that charts render correctly with 1 agent (edge case) and 4+ agents

## Dependencies

- `matplotlib` — added to `[project.optional-dependencies]` as `charts` extra
  - `uv pip install .[charts]` or `uv pip install matplotlib`

## Output Example

```
runs/sample-conversation/charts/
├── output_tps.png              ← grouped bar: all agents, one metric
├── duration_seconds.png        ← grouped bar: all agents, one metric
├── total_throughput_tps.png
├── input_tokens.png
├── output_tokens.png
└── per_turn/
    ├── output_tps.png          ← per-turn line: each turn, all agents
    └── duration_seconds.png
```
