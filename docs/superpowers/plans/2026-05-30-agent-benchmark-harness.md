# Agent Benchmark Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI harness that replays one ordered prompt suite as one continuing conversation per frontend/backend-model variant, using the real `OpenCode` and `Claude Code` CLIs and producing JSON plus Markdown benchmark artifacts.

**Architecture:** The codebase is a small `src/agent_bencher` package. The suite loader parses YAML into typed models, the workspace manager creates one copied run directory per variant, adapters start and continue real frontend sessions, the runner executes the conversation turn by turn, and the recorder/reporter persist turn-level and session-level artifacts.

**Tech Stack:** Python 3.12, `pytest`, `PyYAML`, standard library `dataclasses`, `subprocess`, `pathlib`, `tempfile`, `json`, `argparse`

---

## File Structure

### Project files

- Create: `pyproject.toml`
  - Dependency and packaging metadata, pytest config, console entrypoint
- Create: `.gitignore`
  - Ignore caches, virtualenvs, temp run artifacts

### Source package

- Create: `src/agent_bencher/__init__.py`
  - Package marker and version constant
- Create: `src/agent_bencher/__main__.py`
  - `python -m agent_bencher` entrypoint
- Create: `src/agent_bencher/cli.py`
  - Argument parsing and top-level command execution
- Create: `src/agent_bencher/models.py`
  - Typed dataclasses for suite, variants, turns, token usage, and session results
- Create: `src/agent_bencher/suite.py`
  - YAML loading, validation, and conversion into typed models
- Create: `src/agent_bencher/workspace.py`
  - Run-root creation and workspace copy helpers
- Create: `src/agent_bencher/process.py`
  - Thin subprocess wrapper with timing and captured output
- Create: `src/agent_bencher/runner.py`
  - Conversation orchestration across prompts in one session
- Create: `src/agent_bencher/results.py`
  - Result-directory creation and JSON persistence
- Create: `src/agent_bencher/report.py`
  - Markdown summary generation

### Adapter files

- Create: `src/agent_bencher/adapters/__init__.py`
  - Adapter exports and frontend registry
- Create: `src/agent_bencher/adapters/base.py`
  - Shared adapter interface and command-spec structures
- Create: `src/agent_bencher/adapters/opencode.py`
  - OpenCode command building and JSON event parsing
- Create: `src/agent_bencher/adapters/claude.py`
  - Claude Code command building and JSON output/session parsing

### Tests

- Create: `tests/test_suite.py`
  - Golden-path suite parsing and prompt ordering
- Create: `tests/test_workspace.py`
  - Workspace copy and variant run directory behavior
- Create: `tests/test_adapters.py`
  - Command construction and continuation semantics
- Create: `tests/test_runner.py`
  - Multi-turn conversation flow with a fake adapter
- Create: `tests/test_report.py`
  - JSON-to-Markdown summary formatting
- Create: `tests/fixtures/opencode-turn.jsonl`
  - Captured OpenCode sample output for parser coverage
- Create: `tests/fixtures/claude-turn.json`
  - Captured Claude Code sample output for parser coverage

## Task 1: Bootstrap The Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/agent_bencher/__init__.py`
- Create: `src/agent_bencher/__main__.py`
- Create: `tests/test_suite.py`

- [ ] **Step 1: Initialize git so the later checkpoints can actually commit**

Run:

```bash
git init
```

Expected: output contains `Initialized empty Git repository`

- [ ] **Step 2: Write the failing suite import test**

Create `tests/test_suite.py`:

```python
from agent_bencher import __version__


def test_package_import_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
pytest tests/test_suite.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_bencher'`

- [ ] **Step 4: Write the minimal package and tooling files**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-bencher"
version = "0.1.0"
description = "Benchmark real agent frontends over continuing conversations."
requires-python = ">=3.12"
dependencies = [
  "PyYAML>=6.0,<7.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9.0",
]

[project.scripts]
agent-bencher = "agent_bencher.cli:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `.gitignore`:

```gitignore
__pycache__/
.pytest_cache/
.venv/
dist/
build/
*.egg-info/
.DS_Store
runs/
```

Create `src/agent_bencher/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/agent_bencher/__main__.py`:

```python
from agent_bencher.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Add a minimal CLI stub so the console script target resolves**

Create `src/agent_bencher/cli.py`:

```python
def main() -> int:
    return 0
```

- [ ] **Step 6: Run the test to verify it passes**

Run:

```bash
pytest tests/test_suite.py -v
```

Expected: PASS

- [ ] **Step 7: Commit the bootstrap**

Run:

```bash
git add .gitignore pyproject.toml src/agent_bencher/__init__.py src/agent_bencher/__main__.py src/agent_bencher/cli.py tests/test_suite.py
git commit -m "chore: bootstrap agent benchmark project"
```

Expected: commit created successfully

## Task 2: Add Typed Models And YAML Suite Loading

**Files:**
- Create: `src/agent_bencher/models.py`
- Create: `src/agent_bencher/suite.py`
- Modify: `tests/test_suite.py`

- [ ] **Step 1: Write the failing suite loader test**

Replace `tests/test_suite.py` with:

```python
from pathlib import Path

from agent_bencher.suite import load_suite


def test_load_suite_preserves_prompt_order_and_variant_config(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        "\n".join(
            [
                "name: sample-suite",
                "source_workspace: /tmp/source-project",
                "prompts:",
                "  - id: intro",
                "    text: 'Do this'",
                "  - id: explain",
                "    text: 'Explain that'",
                "variants:",
                "  - id: opencode-fast",
                "    frontend: opencode",
                "    model: mtplx/mtplx-qwen36-27b-optimized-speed",
                "    args: ['--format', 'json']",
                "    env: {}",
            ]
        )
    )

    suite = load_suite(suite_path)

    assert suite.name == "sample-suite"
    assert suite.source_workspace == Path("/tmp/source-project")
    assert [prompt.id for prompt in suite.prompts] == ["intro", "explain"]
    assert suite.variants[0].frontend == "opencode"
    assert suite.variants[0].model == "mtplx/mtplx-qwen36-27b-optimized-speed"
    assert suite.variants[0].args == ["--format", "json"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_suite.py::test_load_suite_preserves_prompt_order_and_variant_config -v
```

Expected: FAIL with `ModuleNotFoundError` for `agent_bencher.suite`

- [ ] **Step 3: Implement the models and suite loader**

Create `src/agent_bencher/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Prompt:
    id: str
    text: str


@dataclass(slots=True)
class Variant:
    id: str
    frontend: str
    model: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Suite:
    name: str
    source_workspace: Path
    prompts: list[Prompt]
    variants: list[Variant]
```

Create `src/agent_bencher/suite.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from agent_bencher.models import Prompt, Suite, Variant


def load_suite(path: Path) -> Suite:
    data = yaml.safe_load(path.read_text())

    prompts = [Prompt(id=item["id"], text=item["text"]) for item in data["prompts"]]
    variants = [
        Variant(
            id=item["id"],
            frontend=item["frontend"],
            model=item["model"],
            args=list(item.get("args", [])),
            env={key: str(value) for key, value in item.get("env", {}).items()},
        )
        for item in data["variants"]
    ]

    return Suite(
        name=data["name"],
        source_workspace=Path(data["source_workspace"]),
        prompts=prompts,
        variants=variants,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest tests/test_suite.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the suite loading slice**

Run:

```bash
git add src/agent_bencher/models.py src/agent_bencher/suite.py tests/test_suite.py
git commit -m "feat: load benchmark suites from yaml"
```

Expected: commit created successfully

## Task 3: Add Workspace Copying And Run Directories

**Files:**
- Create: `src/agent_bencher/workspace.py`
- Create: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing workspace isolation test**

Create `tests/test_workspace.py`:

```python
from pathlib import Path

from agent_bencher.workspace import prepare_variant_workspace


def test_prepare_variant_workspace_copies_source_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.txt").write_text("hello")

    run_root = tmp_path / "runs"

    prepared = prepare_variant_workspace(
        source_workspace=source,
        run_root=run_root,
        suite_name="sample-suite",
        variant_id="opencode-fast",
    )

    assert prepared.variant_workspace.exists()
    assert prepared.variant_workspace != source
    assert (prepared.variant_workspace / "README.txt").read_text() == "hello"
    assert prepared.artifacts_dir.exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_workspace.py::test_prepare_variant_workspace_copies_source_tree -v
```

Expected: FAIL with `ModuleNotFoundError` for `agent_bencher.workspace`

- [ ] **Step 3: Implement workspace preparation**

Create `src/agent_bencher/workspace.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import uuid


@dataclass(slots=True)
class PreparedWorkspace:
    variant_workspace: Path
    artifacts_dir: Path


def prepare_variant_workspace(
    *,
    source_workspace: Path,
    run_root: Path,
    suite_name: str,
    variant_id: str,
) -> PreparedWorkspace:
    run_id = uuid.uuid4().hex[:8]
    base_dir = run_root / suite_name / variant_id / run_id
    workspace_dir = base_dir / "workspace"
    artifacts_dir = base_dir / "artifacts"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_workspace, workspace_dir)

    return PreparedWorkspace(
        variant_workspace=workspace_dir,
        artifacts_dir=artifacts_dir,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest tests/test_workspace.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the workspace slice**

Run:

```bash
git add src/agent_bencher/workspace.py tests/test_workspace.py
git commit -m "feat: isolate each benchmark variant workspace"
```

Expected: commit created successfully

## Task 4: Add Adapter Contracts And Command Construction

**Files:**
- Create: `src/agent_bencher/adapters/__init__.py`
- Create: `src/agent_bencher/adapters/base.py`
- Create: `src/agent_bencher/adapters/opencode.py`
- Create: `src/agent_bencher/adapters/claude.py`
- Create: `tests/test_adapters.py`

- [ ] **Step 1: Write the failing adapter command tests**

Create `tests/test_adapters.py`:

```python
from pathlib import Path

from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter
from agent_bencher.models import Prompt, Variant


def test_opencode_start_command_uses_real_cli_shape(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    variant = Variant(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={},
    )

    command = adapter.build_start_command(
        prompt=Prompt(id="intro", text="Reply with exactly OK"),
        variant=variant,
        workspace=tmp_path,
    )

    assert command.argv == [
        "opencode",
        "run",
        "--format",
        "json",
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "Reply with exactly OK",
    ]
    assert command.cwd == tmp_path


def test_claude_start_command_keeps_env_and_model_flag(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    variant = Variant(
        id="claude-opus",
        frontend="claude",
        model="Qwen3.6-27B-4bit",
        args=["--output-format", "json", "--permission-mode", "bypassPermissions", "--model", "opus"],
        env={
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
            "ANTHROPIC_AUTH_TOKEN": "cbp8",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "Qwen3.6-27B-4bit",
        },
    )

    command = adapter.build_start_command(
        prompt=Prompt(id="intro", text="Reply with exactly OK"),
        variant=variant,
        workspace=tmp_path,
    )

    assert command.argv == [
        "claude",
        "-p",
        "Reply with exactly OK",
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        "opus",
    ]
    assert command.env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "Qwen3.6-27B-4bit"
    assert command.cwd == tmp_path
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_adapters.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `agent_bencher.adapters`

- [ ] **Step 3: Implement the adapter contract and frontend-specific command builders**

Create `src/agent_bencher/adapters/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from agent_bencher.models import Prompt, Variant


@dataclass(slots=True)
class CommandSpec:
    argv: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)


class FrontendAdapter(Protocol):
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec: ...

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec: ...
```

Create `src/agent_bencher/adapters/opencode.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class OpenCodeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["opencode", "run", *variant.args, "-m", variant.model, prompt.text],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=[
                "opencode",
                "run",
                *variant.args,
                "-m",
                variant.model,
                "--session",
                session_id,
                prompt.text,
            ],
            cwd=workspace,
            env=variant.env,
        )
```

Create `src/agent_bencher/adapters/claude.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class ClaudeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, "--resume", session_id, *variant.args],
            cwd=workspace,
            env=variant.env,
        )
```

Create `src/agent_bencher/adapters/__init__.py`:

```python
from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter


def get_adapter(frontend: str):
    registry = {
        "claude": ClaudeAdapter,
        "opencode": OpenCodeAdapter,
    }
    return registry[frontend]()
```

- [ ] **Step 4: Run the adapter tests to verify they pass**

Run:

```bash
pytest tests/test_adapters.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the adapter slice**

Run:

```bash
git add src/agent_bencher/adapters/__init__.py src/agent_bencher/adapters/base.py src/agent_bencher/adapters/opencode.py src/agent_bencher/adapters/claude.py tests/test_adapters.py
git commit -m "feat: add frontend adapter command builders"
```

Expected: commit created successfully

## Task 5: Add Process Execution And Conversation Runner

**Files:**
- Create: `src/agent_bencher/process.py`
- Create: `src/agent_bencher/runner.py`
- Create: `tests/test_runner.py`
- Modify: `src/agent_bencher/models.py`

- [ ] **Step 1: Write the failing multi-turn runner test**

Create `tests/test_runner.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from agent_bencher.models import Prompt, Suite, Variant
from agent_bencher.runner import run_conversation


@dataclass
class FakeCompletedRun:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def build_start_command(self, *, prompt, variant, workspace):
        self.calls.append(("start", None))
        return object()

    def build_continue_command(self, *, prompt, variant, workspace, session_id):
        self.calls.append(("continue", session_id))
        return object()

    def parse_turn_output(self, *, stdout: str, stderr: str):
        return {
            "session_id": "session-123",
            "token_usage": {"input": 10, "output": 5},
            "warnings": [],
        }


def test_run_conversation_reuses_session_id_across_prompts(tmp_path: Path) -> None:
    suite = Suite(
        name="sample",
        source_workspace=tmp_path,
        prompts=[
            Prompt(id="one", text="Do this"),
            Prompt(id="two", text="Explain that"),
        ],
        variants=[
            Variant(
                id="open-fast",
                frontend="opencode",
                model="mtplx/mtplx-qwen36-27b-optimized-speed",
            )
        ],
    )
    adapter = FakeAdapter()

    def fake_runner(_command):
        return FakeCompletedRun(
            stdout='{"session_id":"session-123"}',
            stderr="",
            exit_code=0,
            duration_seconds=1.5,
        )

    result = run_conversation(
        suite=suite,
        variant=suite.variants[0],
        workspace=tmp_path,
        adapter=adapter,
        run_command=fake_runner,
    )

    assert adapter.calls == [("start", None), ("continue", "session-123")]
    assert result.prompts_attempted == 2
    assert result.prompts_completed == 2
    assert result.turns[1].session_id == "session-123"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_runner.py::test_run_conversation_reuses_session_id_across_prompts -v
```

Expected: FAIL with `ModuleNotFoundError` for `agent_bencher.runner`

- [ ] **Step 3: Extend the models for turn and session results**

Replace `src/agent_bencher/models.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Prompt:
    id: str
    text: str


@dataclass(slots=True)
class Variant:
    id: str
    frontend: str
    model: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Suite:
    name: str
    source_workspace: Path
    prompts: list[Prompt]
    variants: list[Variant]


@dataclass(slots=True)
class TokenUsage:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


@dataclass(slots=True)
class TurnResult:
    prompt_id: str
    prompt_text: str
    session_id: str
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    token_usage: TokenUsage
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionResult:
    suite_name: str
    variant_id: str
    frontend: str
    backend_model: str
    session_id: str
    prompts_attempted: int
    prompts_completed: int
    turns: list[TurnResult]
```

- [ ] **Step 4: Implement subprocess execution and the conversation runner**

Create `src/agent_bencher/process.py`:

```python
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
```

Create `src/agent_bencher/runner.py`:

```python
from __future__ import annotations

from agent_bencher.models import SessionResult, Suite, TokenUsage, TurnResult, Variant


def run_conversation(*, suite: Suite, variant: Variant, workspace, adapter, run_command):
    turns: list[TurnResult] = []
    session_id = ""

    for index, prompt in enumerate(suite.prompts):
        if index == 0:
            command = adapter.build_start_command(prompt=prompt, variant=variant, workspace=workspace)
        else:
            command = adapter.build_continue_command(
                prompt=prompt,
                variant=variant,
                workspace=workspace,
                session_id=session_id,
            )

        completed = run_command(command)
        parsed = adapter.parse_turn_output(stdout=completed.stdout, stderr=completed.stderr)
        session_id = parsed["session_id"]

        turns.append(
            TurnResult(
                prompt_id=prompt.id,
                prompt_text=prompt.text,
                session_id=session_id,
                exit_code=completed.exit_code,
                duration_seconds=completed.duration_seconds,
                stdout=completed.stdout,
                stderr=completed.stderr,
                token_usage=TokenUsage(**parsed["token_usage"]),
                warnings=list(parsed["warnings"]),
            )
        )

        if completed.exit_code != 0:
            break

    return SessionResult(
        suite_name=suite.name,
        variant_id=variant.id,
        frontend=variant.frontend,
        backend_model=variant.model,
        session_id=session_id,
        prompts_attempted=len(turns),
        prompts_completed=sum(1 for turn in turns if turn.exit_code == 0),
        turns=turns,
    )
```

- [ ] **Step 5: Add the minimal parser hooks the runner expects**

Modify `src/agent_bencher/adapters/opencode.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class OpenCodeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["opencode", "run", *variant.args, "-m", variant.model, prompt.text],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=[
                "opencode",
                "run",
                *variant.args,
                "-m",
                variant.model,
                "--session",
                session_id,
                prompt.text,
            ],
            cwd=workspace,
            env=variant.env,
        )

    def parse_turn_output(self, *, stdout: str, stderr: str):
        lines = [line for line in stdout.splitlines() if line.strip()]
        payload = json.loads(lines[-1]) if lines else {}
        return {
            "session_id": payload.get("session_id", ""),
            "token_usage": payload.get("token_usage", {"input": 0, "output": 0}),
            "warnings": [],
        }
```

Modify `src/agent_bencher/adapters/claude.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class ClaudeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=["claude", "-p", prompt.text, "--resume", session_id, *variant.args],
            cwd=workspace,
            env=variant.env,
        )

    def parse_turn_output(self, *, stdout: str, stderr: str):
        payload = json.loads(stdout) if stdout.strip() else {}
        result = payload.get("result", payload)
        usage = result.get("usage", {})
        return {
            "session_id": result.get("session_id", payload.get("session_id", "")),
            "token_usage": {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "reasoning": usage.get("reasoning_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
            "warnings": [],
        }
```

- [ ] **Step 6: Run the runner test to verify it passes**

Run:

```bash
pytest tests/test_runner.py -v
```

Expected: PASS

- [ ] **Step 7: Commit the runner slice**

Run:

```bash
git add src/agent_bencher/models.py src/agent_bencher/process.py src/agent_bencher/runner.py src/agent_bencher/adapters/opencode.py src/agent_bencher/adapters/claude.py tests/test_runner.py
git commit -m "feat: run multi-turn benchmark conversations"
```

Expected: commit created successfully

## Task 6: Add Real Parser Fixtures And Markdown Reporting

**Files:**
- Create: `src/agent_bencher/results.py`
- Create: `src/agent_bencher/report.py`
- Create: `tests/test_report.py`
- Create: `tests/fixtures/opencode-turn.jsonl`
- Create: `tests/fixtures/claude-turn.json`
- Modify: `tests/test_adapters.py`

- [ ] **Step 1: Add failing parser and report tests**

Replace `tests/test_adapters.py` with:

```python
from pathlib import Path

from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter
from agent_bencher.models import Prompt, Variant


def test_opencode_start_command_uses_real_cli_shape(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    variant = Variant(
        id="open-fast",
        frontend="opencode",
        model="mtplx/mtplx-qwen36-27b-optimized-speed",
        args=["--format", "json"],
        env={},
    )

    command = adapter.build_start_command(
        prompt=Prompt(id="intro", text="Reply with exactly OK"),
        variant=variant,
        workspace=tmp_path,
    )

    assert command.argv == [
        "opencode",
        "run",
        "--format",
        "json",
        "-m",
        "mtplx/mtplx-qwen36-27b-optimized-speed",
        "Reply with exactly OK",
    ]


def test_claude_parser_reads_usage_and_session_id_from_json_fixture() -> None:
    payload = Path("tests/fixtures/claude-turn.json").read_text()

    parsed = ClaudeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "claude-session-123"
    assert parsed["token_usage"]["input"] == 120
    assert parsed["token_usage"]["output"] == 45


def test_opencode_parser_reads_usage_and_session_id_from_jsonl_fixture() -> None:
    payload = Path("tests/fixtures/opencode-turn.jsonl").read_text()

    parsed = OpenCodeAdapter().parse_turn_output(stdout=payload, stderr="")

    assert parsed["session_id"] == "opencode-session-123"
    assert parsed["token_usage"]["input"] == 210
    assert parsed["token_usage"]["output"] == 80
```

Create `tests/test_report.py`:

```python
from agent_bencher.models import SessionResult, TokenUsage, TurnResult
from agent_bencher.report import build_markdown_report


def test_build_markdown_report_includes_session_summary() -> None:
    session = SessionResult(
        suite_name="sample-suite",
        variant_id="open-fast",
        frontend="opencode",
        backend_model="mtplx/mtplx-qwen36-27b-optimized-speed",
        session_id="opencode-session-123",
        prompts_attempted=2,
        prompts_completed=2,
        turns=[
            TurnResult(
                prompt_id="intro",
                prompt_text="Do this",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=1.2,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            ),
            TurnResult(
                prompt_id="explain",
                prompt_text="Explain that",
                session_id="opencode-session-123",
                exit_code=0,
                duration_seconds=2.3,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=210, output=80),
            ),
        ],
    )

    report = build_markdown_report([session])

    assert "# Benchmark Summary" in report
    assert "open-fast" in report
    assert "completed 2/2 prompts" in report
    assert "mtplx/mtplx-qwen36-27b-optimized-speed" in report
```

- [ ] **Step 2: Add the parser fixtures**

Create `tests/fixtures/claude-turn.json`:

```json
{
  "session_id": "claude-session-123",
  "result": {
    "session_id": "claude-session-123",
    "usage": {
      "input_tokens": 120,
      "output_tokens": 45,
      "reasoning_tokens": 10,
      "cache_read_input_tokens": 0,
      "cache_creation_input_tokens": 0
    }
  }
}
```

Create `tests/fixtures/opencode-turn.jsonl`:

```json
{"type":"session.started","session_id":"opencode-session-123"}
{"type":"response.completed","session_id":"opencode-session-123","token_usage":{"input":210,"output":80,"reasoning":0,"cache_read":0,"cache_write":0}}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_adapters.py tests/test_report.py -v
```

Expected: FAIL because report functions and richer OpenCode parser behavior do not exist yet

- [ ] **Step 4: Implement result persistence and Markdown reporting**

Create `src/agent_bencher/results.py`:

```python
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
```

Create `src/agent_bencher/report.py`:

```python
from __future__ import annotations

from agent_bencher.models import SessionResult


def build_markdown_report(sessions: list[SessionResult]) -> str:
    lines = ["# Benchmark Summary", ""]

    for session in sessions:
        total_input = sum(turn.token_usage.input for turn in session.turns)
        total_output = sum(turn.token_usage.output for turn in session.turns)
        total_duration = sum(turn.duration_seconds for turn in session.turns)

        lines.extend(
            [
                f"## {session.variant_id}",
                f"- frontend: {session.frontend}",
                f"- backend model: {session.backend_model}",
                f"- session id: {session.session_id}",
                f"- completed {session.prompts_completed}/{session.prompts_attempted} prompts",
                f"- total duration: {total_duration:.2f}s",
                f"- total input tokens: {total_input}",
                f"- total output tokens: {total_output}",
                "",
            ]
        )

    return "\n".join(lines)
```

Replace `src/agent_bencher/adapters/opencode.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from agent_bencher.adapters.base import CommandSpec
from agent_bencher.models import Prompt, Variant


class OpenCodeAdapter:
    def build_start_command(self, *, prompt: Prompt, variant: Variant, workspace: Path) -> CommandSpec:
        return CommandSpec(
            argv=["opencode", "run", *variant.args, "-m", variant.model, prompt.text],
            cwd=workspace,
            env=variant.env,
        )

    def build_continue_command(
        self,
        *,
        prompt: Prompt,
        variant: Variant,
        workspace: Path,
        session_id: str,
    ) -> CommandSpec:
        return CommandSpec(
            argv=[
                "opencode",
                "run",
                *variant.args,
                "-m",
                variant.model,
                "--session",
                session_id,
                prompt.text,
            ],
            cwd=workspace,
            env=variant.env,
        )

    def parse_turn_output(self, *, stdout: str, stderr: str):
        session_id = ""
        token_usage = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}

        for line in stdout.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            session_id = payload.get("session_id", session_id)
            if payload.get("type") == "response.completed":
                token_usage = payload.get("token_usage", token_usage)

        return {
            "session_id": session_id,
            "token_usage": token_usage,
            "warnings": [],
        }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_adapters.py tests/test_report.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the reporting slice**

Run:

```bash
git add src/agent_bencher/results.py src/agent_bencher/report.py src/agent_bencher/adapters/opencode.py tests/test_adapters.py tests/test_report.py tests/fixtures/claude-turn.json tests/fixtures/opencode-turn.jsonl
git commit -m "feat: parse token fixtures and write benchmark summaries"
```

Expected: commit created successfully

## Task 7: Wire The CLI End To End

**Files:**
- Modify: `src/agent_bencher/cli.py`
- Modify: `src/agent_bencher/__main__.py`
- Modify: `src/agent_bencher/adapters/__init__.py`
- Modify: `src/agent_bencher/results.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Append this test to `tests/test_report.py`:

```python
from pathlib import Path

from agent_bencher.cli import build_parser


def test_build_parser_accepts_suite_and_output_args() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["bench", "suite.yaml", "--output-dir", "runs"])

    assert parsed.command == "bench"
    assert parsed.suite_path == Path("suite.yaml")
    assert parsed.output_dir == Path("runs")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_report.py::test_build_parser_accepts_suite_and_output_args -v
```

Expected: FAIL because `build_parser` does not exist yet

- [ ] **Step 3: Expand the result writer and implement the CLI**

Replace `src/agent_bencher/results.py` with:

```python
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
```

Replace `src/agent_bencher/cli.py` with:

```python
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
    parser = argparse.ArgumentParser(prog="python -m agent_bencher")
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
```

Replace `src/agent_bencher/adapters/__init__.py` with:

```python
from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter


def get_adapter(frontend: str):
    registry = {
        "claude": ClaudeAdapter,
        "opencode": OpenCodeAdapter,
    }

    if frontend not in registry:
        raise ValueError(f"unsupported frontend: {frontend}")

    return registry[frontend]()
```

- [ ] **Step 4: Run the CLI smoke test and the full test suite**

Run:

```bash
pytest -v
```

Expected: PASS for all tests

Run:

```bash
python -m agent_bencher --help
```

Expected: output shows the `bench` subcommand

- [ ] **Step 5: Commit the CLI slice**

Run:

```bash
git add src/agent_bencher/cli.py src/agent_bencher/results.py src/agent_bencher/adapters/__init__.py tests/test_report.py
git commit -m "feat: wire benchmark cli end to end"
```

Expected: commit created successfully

## Self-Review Coverage

- Spec coverage:
  - continuing conversation per variant: Task 5
  - one copied workspace per variant: Task 3
  - real frontend command shapes for OpenCode and Claude Code: Task 4
  - token/session parsing from CLI output: Task 6
  - JSON and Markdown artifacts: Tasks 6 and 7
  - top-level runnable CLI: Task 7
- Placeholder scan:
  - no red-flag placeholder filler remains
- Type consistency:
  - `Suite`, `Variant`, `Prompt`, `SessionResult`, `TurnResult`, `TokenUsage`, `CommandSpec`, and `run_conversation()` use the same names throughout the plan
