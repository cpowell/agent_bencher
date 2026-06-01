from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from agent_bencher.adapters import get_adapter
from agent_bencher.process import run_command
from agent_bencher.results import write_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import prepare_variant_workspace


def format_run_id(date_part: str, time_part: str) -> str:
    return f"{date_part}T{time_part.replace(':', '-')}"


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")

    conversation = load_conversation(args.conversation)
    agent = load_agent_config(args.run_config)
    now = datetime.now(timezone.utc)
    run_id = format_run_id(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    started_at = now.isoformat()
    run_output_dir = args.output_dir / conversation.name / agent.id / run_id

    prepared = prepare_variant_workspace(
        source_workspace=conversation.source_workspace,
        run_root=args.output_dir,
        suite_name=conversation.name,
        variant_id=agent.id,
    )
    adapter = get_adapter(agent.frontend)
    session = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=prepared.variant_workspace,
        adapter=adapter,
        run_command=run_command,
        run_id=run_id,
        started_at=started_at,
        comment=args.comment,
    )

    write_results(sessions=[session], output_dir=run_output_dir)
    return 0
