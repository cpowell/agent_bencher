from __future__ import annotations

import argparse
from pathlib import Path

from agent_bencher.adapters import get_adapter
from agent_bencher.process import run_command
from agent_bencher.results import write_results
from agent_bencher.runner import run_conversation
from agent_bencher.suite import load_suite
from agent_bencher.workspace import prepare_variant_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-bencher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("suite_path", type=Path)
    bench.add_argument("--output-dir", type=Path, default=Path("runs"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "bench":
        parser.error(f"unsupported command: {args.command}")

    suite = load_suite(args.suite_path)
    sessions = []

    for variant in suite.variants:
        prepared = prepare_variant_workspace(
            source_workspace=suite.source_workspace,
            run_root=args.output_dir,
            suite_name=suite.name,
            variant_id=variant.id,
        )
        adapter = get_adapter(variant.frontend)
        session = run_conversation(
            suite=suite,
            variant=variant,
            workspace=prepared.variant_workspace,
            adapter=adapter,
            run_command=run_command,
        )
        sessions.append(session)

    write_results(sessions=sessions, output_dir=args.output_dir / suite.name)
    return 0
