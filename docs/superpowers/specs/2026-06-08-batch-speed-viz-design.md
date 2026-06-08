# Batch Speed Visualization Design

## Problem

Comparing agent run speeds across multiple configs requires reading batch.json files and computing statistics manually. The three speed metrics (completion time, output TPS, total throughput TPS) are muddy and hard to compare side-by-side.

## Solution

A `viz` CLI subcommand that reads run artifacts from `runs/<conversation>/` and generates three matplotlib bar charts as PNG files.

## CLI Interface

```
uv run python -m agent_bencher viz runs/sample-conversation
```

- Single positional argument: conversation directory under `runs/`
- Outputs to `runs/<conversation>/viz/`
- Three PNG files: `duration.png`, `output_tps.png`, `total_throughput_tps.png`

## Data Loading

For the given conversation directory:

1. Validate the path exists and is a directory; exit with error if not
2. Scan immediate subdirectories for agent config names
3. For each agent config, find the latest batch run (sorted by directory name, last alphabetically)
4. Read `batch.json` to get the agent ID
5. For each trial in `trials/`, read `trials/trial-NNN/run.json` to extract per-trial metric values
6. Compute mean and standard deviation across trials for each of the three metrics
7. If an agent has no `batch.json` or empty trials, skip it with a warning to stderr
8. If no valid agents are found, exit with an error

If only 1 trial exists for an agent, stddev error bars show 0.

## Chart Design

Three grouped bar charts, one per metric:

- **`duration.png`** — x-axis: agent IDs, y-axis: seconds. Lower bars = faster.
- **`output_tps.png`** — x-axis: agent IDs, y-axis: tokens/sec. Higher bars = faster generation.
- **`total_throughput_tps.png`** — x-axis: agent IDs, y-axis: tokens/sec. Higher bars = higher total throughput.

Each chart:
- One bar per agent config
- Bar height = mean value across trials
- Error bars = ±1 standard deviation
- Agent IDs on x-axis, rotated if names are long
- Clean matplotlib styling with no unnecessary grid lines

## Dependencies

Add `matplotlib>=3.8` to project dependencies in `pyproject.toml`.

## File Structure

```
src/agent_bencher/
├── cli.py              # Add 'viz' subcommand
├── viz.py              # New: data loading + chart generation
```

```
runs/sample-conversation/
├── claude-qwen35-122B-mtp/
│   └── 2026-06-06T00-15-43/
│       └── batch.json
├── claude-qwen36-35b/
│   └── 2026-06-06T01-20-00/
│       └── batch.json
└── viz/
    ├── duration.png
    ├── output_tps.png
    └── total_throughput_tps.png
```
