from __future__ import annotations

import argparse
from pathlib import Path

from agent_bencher.adapters import get_adapter
from agent_bencher.process import run_command
from agent_bencher.results import write_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_agent_config, load_conversation
from agent_bencher.workspace import prepare_variant_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-bencher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--conversation", type=Path, required=True)
    bench.add_argument("--agent", type=Path, required=True)
    bench.add_argument("--output-dir", type=Path, default=Path("runs"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")

    conversation = load_conversation(args.conversation)
    agent = load_agent_config(args.agent)

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
    )

    write_results(sessions=[session], output_dir=args.output_dir / conversation.name / agent.id)
    return 0
