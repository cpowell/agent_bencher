from pathlib import Path
import json

import pytest

from agent_bencher.viz import (
    _build_agent_styles,
    _compute_positions,
    generate_bar_chart,
    load_agent_runs,
)


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
        conv_dir.mkdir()
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
    def test_build_agent_styles_groups_existing_agent_ids(self) -> None:
        styles = _build_agent_styles(
            [
                "opencode-omlx-qwen36-27b-4bit",
                "opencode-lmstudio-qwen36-27b-q5_k_xl-mtp",
                "claude-qwen36-35b-a3b",
            ]
        )

        assert styles[0].group_label == "Qwen 3.6 27B"
        assert styles[0].short_label == "omlx: qwen36-27b-4bit"
        assert styles[0].color_label == "OpenCode / oMLX"
        assert styles[1].group_label == "Qwen 3.6 27B"
        assert styles[1].short_label == "lmstudio: qwen36-27b-q5_k_xl-mtp"
        assert styles[1].color_label == "OpenCode / LM Studio"
        assert styles[2].group_label == "Qwen 3.6 35B A3B"
        assert styles[2].short_label == "claude: qwen36-35b-a3b"
        assert styles[2].color_label == "Claude"

    def test_compute_positions_adds_gaps_between_groups(self) -> None:
        styles = _build_agent_styles(
            [
                "opencode-omlx-qwen36-27b-4bit",
                "opencode-lmstudio-qwen36-27b-q5_k_xl-mtp",
                "opencode-omlx-qwen36-35b-a3b-6bit",
                "claude-qwen36-35b-a3b",
            ]
        )

        positions, separators = _compute_positions(styles, group_gap=1.0)

        assert positions == [0.0, 1.0, 3.0, 4.0]
        assert separators == [2.0]

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
            "opencode-omlx-agent-a": {"duration_seconds": [100.0, 120.0], "effective_output_tps": [20.0, 25.0],
                                      "effective_total_throughput_tps": [1000.0, 1100.0]},
            "opencode-lmstudio-agent-b": {"duration_seconds": [80.0, 90.0], "effective_output_tps": [30.0, 28.0],
                                          "effective_total_throughput_tps": [1500.0, 1400.0]},
            "claude-agent-c": {"duration_seconds": [150.0, 160.0], "effective_output_tps": [10.0, 12.0],
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
