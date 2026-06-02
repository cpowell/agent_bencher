from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

from agent_bencher.adapters import get_adapter
from agent_bencher.batch import build_batch_result
from agent_bencher.process import run_command
from agent_bencher.results import write_batch_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import prepare_variant_workspace


def format_run_id(date_part: str, time_part: str) -> str:
    return f"{date_part}T{time_part.replace(':', '-')}"


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")

    conversation = load_conversation(args.conversation)
    agent = load_agent_config(args.run_config)
    now = datetime.now(timezone.utc)
    adapter = get_adapter(agent.frontend)
    batch_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    batch_output_dir = args.output_dir / conversation.name / agent.id / batch_id
    sessions = []

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
        )
        sessions.append(session)
        if session.status == "completed":
            shutil.rmtree(prepared.variant_workspace.parent)

    batch = build_batch_result(
        batch_id=batch_id,
        requested_runs=args.runs,
        comment=args.comment,
        sessions=sessions,
    )
    write_batch_results(batch=batch, output_dir=batch_output_dir)
    return 0
