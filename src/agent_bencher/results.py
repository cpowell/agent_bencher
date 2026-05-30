from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from agent_bencher.models import SessionResult


def write_session_result(session: SessionResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{session.variant_id}.json"
    destination.write_text(json.dumps(asdict(session), indent=2))
    return destination
