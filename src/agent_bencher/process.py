from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time

from agent_bencher.adapters.base import CommandSpec


@dataclass(slots=True)
class CompletedRun:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    started_at: str
    ended_at: str


def run_command(command: CommandSpec) -> CompletedRun:
    env = os.environ.copy()
    env.update(command.env)

    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    completed = subprocess.run(
        command.argv,
        cwd=Path(command.cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    duration = time.monotonic() - started
    ended_at = datetime.now(timezone.utc).isoformat()

    return CompletedRun(
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        duration_seconds=duration,
        started_at=started_at,
        ended_at=ended_at,
    )
