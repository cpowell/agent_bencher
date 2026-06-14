from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

from agent_bencher.adapters import get_adapter
from agent_bencher.batch import build_batch_result
from agent_bencher.process import run_command
from agent_bencher.results import write_batch_results, write_trial_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.viz import generate_bar_chart, load_agent_runs
from agent_bencher.workspace import prepare_variant_workspace


def _write_available_batch_results(
    *,
    batch_id: str,
    requested_runs: int,
    comment: str,
    sessions: list,
    output_dir: Path,
) -> None:
    if not sessions:
        return

    batch = build_batch_result(
        batch_id=batch_id,
        requested_runs=requested_runs,
        comment=comment,
        sessions=sessions,
    )
    write_batch_results(batch=batch, output_dir=output_dir)


def format_run_id(date_part: str, time_part: str) -> str:
    return f"{date_part}T{time_part.replace(':', '-')}"


def format_display_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent_bencher",
        description="Benchmark real agent frontends over a multi-turn conversation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser(
        "bench",
        help="Run one conversation against one run config.",
        description="Copy the source workspace, replay the conversation turn by turn, and write artifacts under the output directory.",
    )
    bench.add_argument("run_config", type=Path, help="Path to a run config YAML file.")
    bench.add_argument("conversation", type=Path, help="Path to a conversation YAML file.")
    bench.add_argument(
        "--comment",
        default="",
        help="Optional human note to include in run artifacts.",
    )
    bench.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run artifacts are written. Default: runs",
    )
    bench.add_argument(
        "--runs",
        type=positive_int,
        default=1,
        help="Number of repeated trials to execute. Default: 1",
    )

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

    bench.set_defaults(func=bench_cmd)

    return parser


def bench_cmd(args: argparse.Namespace) -> int:
    """Run one conversation against one run config."""
    conversation = load_conversation(args.conversation)
    agent = load_agent_config(args.run_config)
    now = datetime.now(timezone.utc)
    adapter = get_adapter(agent.frontend)
    batch_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    batch_output_dir = args.output_dir / conversation.name / agent.id / batch_id
    sessions = []
    interrupted = False
    print(f"Run started at {format_display_time(now)}", file=sys.stderr, flush=True)
    try:
        for trial_index in range(args.runs):
            trial_started_at = datetime.now(timezone.utc)
            trial_run_id = (
                f"{format_run_id(trial_started_at.strftime('%Y-%m-%d'), trial_started_at.strftime('%H:%M:%S'))}"
                f"-trial-{trial_index + 1:03d}"
            )
            prepared = prepare_variant_workspace(
                source_workspace=conversation.source_workspace,
                run_root=args.output_dir,
                suite_name=conversation.name,
                variant_id=agent.id,
            )
            session = run_conversation(
                conversation=conversation,
                agent=agent,
                workspace=prepared.variant_workspace,
                adapter=adapter,
                run_command=run_command,
                run_id=trial_run_id,
                started_at=trial_started_at.isoformat(),
                comment=args.comment,
                on_turn_completed=lambda checkpoint_session: write_trial_results(
                    session=checkpoint_session,
                    output_dir=prepared.artifacts_dir,
                ),
            )
            sessions.append(session)
            _write_available_batch_results(
                batch_id=batch_id,
                requested_runs=args.runs,
                comment=args.comment,
                sessions=sessions,
                output_dir=batch_output_dir,
            )
            if session.status == "completed":
                shutil.rmtree(prepared.variant_workspace.parent)
    except KeyboardInterrupt:
        interrupted = True
        print("Terminating early at user request", file=sys.stderr, flush=True)
        _write_available_batch_results(
            batch_id=batch_id,
            requested_runs=args.runs,
            comment=args.comment,
            sessions=sessions,
            output_dir=batch_output_dir,
        )
    else:
        _write_available_batch_results(
            batch_id=batch_id,
            requested_runs=args.runs,
            comment=args.comment,
            sessions=sessions,
            output_dir=batch_output_dir,
        )
        return 0
    finally:
        print(
            f"Run concluded at {format_display_time(datetime.now(timezone.utc))}",
            file=sys.stderr,
            flush=True,
        )
    return 130 if interrupted else 0


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)
