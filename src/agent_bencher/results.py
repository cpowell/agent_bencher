from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from agent_bencher.models import SessionResult
from agent_bencher.report import build_markdown_report


def write_results(*, sessions: list[SessionResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = output_dir / "json"
    raw_dir.mkdir(exist_ok=True)

    for session in sessions:
        destination = raw_dir / f"{session.variant_id}.json"
        destination.write_text(json.dumps(asdict(session), indent=2))

    (output_dir / "summary.md").write_text(build_markdown_report(sessions))
