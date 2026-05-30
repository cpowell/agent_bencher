from __future__ import annotations

from dataclasses import dataclass
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


def run_command(command: CommandSpec) -> CompletedRun:
    env = os.environ.copy()
    env.update(command.env)

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

    return CompletedRun(
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        duration_seconds=duration,
    )
