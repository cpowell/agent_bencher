from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import NamedTuple


def _filter_trial_rows(
    *,
    trial_rows: list[dict[str, float]],
    exclude_slowest: bool,
    only_slowest: bool,
) -> list[dict[str, float]]:
    if not trial_rows or (not exclude_slowest and not only_slowest):
        return trial_rows

    slowest_index = max(
        range(len(trial_rows)),
        key=lambda index: trial_rows[index]["duration_seconds"],
    )

    if only_slowest:
        return [trial_rows[slowest_index]]

    return [row for index, row in enumerate(trial_rows) if index != slowest_index]


def load_agent_runs(
    conversation_dir: Path,
    *,
    exclude_slowest: bool = False,
    only_slowest: bool = False,
) -> dict[str, dict[str, list[float]]]:
    """Load speed metrics from all batches of each agent config.

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

        agent_id = agent_dir.name
        trial_rows: list[dict[str, float]] = []

        for batch_dir in batch_runs:
            batch_json = batch_dir / "batch.json"
            if not batch_json.exists():
                print(f"Warning: no batch.json in '{batch_dir}'", file=sys.stderr)
                continue

            with open(batch_json) as f:
                batch_data = json.load(f)

            agent_id = batch_data.get("agent_id", agent_id)

            trials_dir = batch_dir / "trials"
            if not trials_dir.is_dir():
                print(f"Warning: no trials dir in '{batch_dir}'", file=sys.stderr)
                continue

            trial_dirs = sorted(d for d in trials_dir.iterdir() if d.is_dir())
            if not trial_dirs:
                print(f"Warning: no trials in '{batch_dir}'", file=sys.stderr)
                continue

            for trial_dir in trial_dirs:
                run_json = trial_dir / "run.json"
                if not run_json.exists():
                    continue

                with open(run_json) as f:
                    run_data = json.load(f)

                row: dict[str, float] = {}
                for metric_name, path in metric_paths.items():
                    value = run_data
                    for key in path:
                        if isinstance(value, dict):
                            value = value.get(key)
                        else:
                            value = None
                            break
                    if value is not None and isinstance(value, (int, float)):
                        row[metric_name] = float(value)

                if row.get("duration_seconds") is not None:
                    trial_rows.append(row)

        filtered_rows = _filter_trial_rows(
            trial_rows=trial_rows,
            exclude_slowest=exclude_slowest,
            only_slowest=only_slowest,
        )

        # Collect per-trial metrics
        trial_metrics: dict[str, list[float]] = {m: [] for m in metric_paths}
        for row in filtered_rows:
            for metric_name in metric_paths:
                value = row.get(metric_name)
                if value is not None:
                    trial_metrics[metric_name].append(value)

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
from matplotlib.patches import Patch
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


class AgentStyle(NamedTuple):
    agent_id: str
    group_key: str
    group_label: str
    short_label: str
    color: str
    color_label: str


GROUP_COLORS = {
    "claude": "#4C6EF5",
    "lmstudio": "#F08C00",
    "mtplx": "#2F9E44",
    "omlx": "#C92A2A",
    "other": "#5C677D",
}


def _split_agent_id(agent_id: str) -> tuple[str, str, str]:
    parts = agent_id.split("-")
    frontend = parts[0] if parts else "other"

    if frontend == "opencode" and len(parts) >= 3:
        short_label = "-".join(parts[2:])
    elif frontend == "claude":
        short_label = "-".join(parts[1:]) or agent_id
    else:
        short_label = "-".join(parts[1:]) or agent_id

    return frontend, short_label, agent_id


def _normalize_model_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _extract_model_family(agent_id: str, short_label: str) -> str:
    normalized = _normalize_model_key(agent_id)
    for family in ("qwen36-27b", "qwen36-35b-a3b", "qwen35-122b"):
        if _normalize_model_key(family) in normalized:
            return family

    parts = short_label.split("-")
    if len(parts) >= 4 and parts[0].startswith("qwen") and parts[2].endswith("b") and parts[3] == "a3b":
        return "-".join(parts[:4])
    if len(parts) >= 3 and parts[0].startswith("qwen") and parts[2].endswith("b"):
        return "-".join(parts[:3])
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return short_label


def _extract_server_key(frontend: str, agent_id: str) -> str:
    parts = agent_id.split("-")
    if frontend == "opencode" and len(parts) >= 2:
        return parts[1]
    if frontend == "claude":
        return "claude"
    return frontend


def _group_label(group_key: str) -> str:
    if group_key == "qwen36-27b":
        return "Qwen 3.6 27B"
    if group_key == "qwen36-35b-a3b":
        return "Qwen 3.6 35B A3B"
    if group_key == "qwen35-122b":
        return "Qwen 3.5 122B"
    return group_key


def _color_label(group_key: str, frontend: str) -> str:
    if group_key == "claude":
        return "Claude"
    if group_key == "lmstudio":
        return "OpenCode / LM Studio"
    if group_key == "mtplx":
        return "OpenCode / MTPLX"
    if group_key == "omlx":
        return "OpenCode / oMLX"
    return frontend.capitalize()


def _build_agent_styles(agent_ids: list[str]) -> list[AgentStyle]:
    styles: list[AgentStyle] = []
    for agent_id in agent_ids:
        frontend, short_label, raw_agent_id = _split_agent_id(agent_id)
        group_key = _extract_model_family(raw_agent_id, short_label)
        color_key = _extract_server_key(frontend, raw_agent_id)
        color = GROUP_COLORS.get(color_key, GROUP_COLORS["other"])
        styles.append(
            AgentStyle(
                agent_id=agent_id,
                group_key=group_key,
                group_label=_group_label(group_key),
                short_label=f"{color_key}: {short_label}",
                color=color,
                color_label=_color_label(color_key, frontend),
            )
        )
    return styles


def _compute_positions(styles: list[AgentStyle], group_gap: float = 0.9) -> tuple[list[float], list[float]]:
    positions: list[float] = []
    separators: list[float] = []
    current_x = 0.0
    previous_group: str | None = None

    for style in styles:
        if previous_group is not None and style.group_key != previous_group:
            separators.append(current_x - 0.5 + (group_gap / 2))
            current_x += group_gap
        positions.append(current_x)
        current_x += 1.0
        previous_group = style.group_key

    return positions, separators


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
    agent_ids = sorted(
        agents.keys(),
        key=lambda agent_id: (
            _extract_model_family(agent_id, _split_agent_id(agent_id)[1]),
            _extract_server_key(_split_agent_id(agent_id)[0], agent_id),
            _split_agent_id(agent_id)[1],
            agent_id,
        ),
    )
    styles = _build_agent_styles(agent_ids)
    means = []
    stds = []

    for agent_id in agent_ids:
        values = agents[agent_id].get(metric, [])
        if not values:
            means.append(0.0)
            stds.append(0.0)
        elif len(values) == 1:
            means.append(values[0])
            stds.append(0.0)
        else:
            means.append(mean(values))
            stds.append(stdev(values))

    positions, separators = _compute_positions(styles)

    fig, ax = plt.subplots(figsize=(max(9, len(agent_ids) * 1.2), 5.8))
    ax.bar(
        positions,
        means,
        yerr=stds,
        capsize=4,
        width=0.72,
        color=[style.color for style in styles],
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )

    for separator in separators:
        ax.axvline(separator, color="#CED4DA", linewidth=1.0, linestyle="--", zorder=1)

    ax.set_xticks(positions, [style.short_label for style in styles], rotation=35, ha="right", fontsize=8)
    _set_ylabel(ax, metric)
    ax.set_title(_set_title(metric))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.1f}"))
    ax.grid(axis="y", color="#E9ECEF", linewidth=0.8, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_entries: dict[str, Patch] = {}
    for style in styles:
        if style.color_label not in legend_entries:
            legend_entries[style.color_label] = Patch(
                facecolor=style.color,
                edgecolor="black",
                linewidth=0.5,
                label=style.color_label,
            )
    ax.legend(
        handles=list(legend_entries.values()),
        loc="lower center",
        bbox_to_anchor=(0.5, 1.14),
        frameon=False,
        ncols=max(1, min(4, len(legend_entries))),
    )

    if styles:
        ymin, ymax = ax.get_ylim()
        label_y = ymax * 1.02 if ymax > 0 else 0.1
        cluster_centers: list[tuple[float, str]] = []
        current_group = styles[0].group_key
        current_positions = [positions[0]]
        for style, position in zip(styles[1:], positions[1:], strict=True):
            if style.group_key == current_group:
                current_positions.append(position)
                continue
            cluster_centers.append((sum(current_positions) / len(current_positions), _group_label(current_group)))
            current_group = style.group_key
            current_positions = [position]
        cluster_centers.append((sum(current_positions) / len(current_positions), _group_label(current_group)))

        for center, label in cluster_centers:
            ax.text(center, label_y, label, ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.set_ylim(ymin, ymax * 1.12 if ymax > 0 else 1.0)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
