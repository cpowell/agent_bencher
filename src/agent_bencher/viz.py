from __future__ import annotations

import json
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


import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


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
    bars = plt.bar(x, means, yerr=stds, capsize=4, width=0.6, edgecolor="black", linewidth=0.5)

    plt.xticks(x, agent_ids, rotation=45, ha="right", fontsize=8)
    _set_ylabel(plt.gca(), metric)
    plt.title(_set_title(metric))
    plt.gca().yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.1f}"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
