# Dry-Run Mode and CLI Config Overrides

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--dry-run` to preview exact commands without execution, and `--override key=value` to tweak agent config from the CLI without editing YAML.

**Architecture:** `--dry-run` short-circuits after workspace prep and command building, printing the commands that would be executed. `--override` accepts `key=value` pairs that merge into the loaded `AgentConfig` (supports `model`, `args`, and `env.KEY`). The override logic lives in `suite.py` as `apply_overrides` to keep `cli.py` thin.

**Tech Stack:** `argparse`, `yaml`, dataclasses

**Dependencies:** If Improvement 1 (parallel trials) or Improvement 2 (reflink) have been merged, `_run_single_trial` must accept `dry_run` and `use_reflink` parameters. If neither has been merged, this plan works against the current sequential `for` loop.

---

### File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/agent_bencher/cli.py` | Add `--dry-run`, `--override` flags; dry-run output logic |
| Modify | `src/agent_bencher/suite.py` | Add `apply_overrides` function |
| Create | `tests/test_cli_dry_run.py` | Tests for dry-run output, override merging |

---

### Task 1: Add `apply_overrides` to suite.py

**Files:**
- Modify: `src/agent_bencher/suite.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_dry_run.py`:

```python
from agent_bencher.suite import apply_overrides
from agent_bencher.models import AgentConfig


def test_apply_overrides_changes_model() -> None:
    agent = AgentConfig(
        id="test-agent",
        frontend="opencode",
        model="original-model",
        args=["--format", "json"],
        env={"API_KEY": "secret"},
    )

    result = apply_overrides(agent, ["model=new-model"])

    assert result.model == "new-model"
    assert result.args == ["--format", "json"]
    assert result.env == {"API_KEY": "secret"}


def test_apply_overrides_replaces_args() -> None:
    agent = AgentConfig(
        id="test-agent",
        frontend="claude",
        model="gpt-4",
        args=["--verbose"],
        env={},
    )

    result = apply_overrides(agent, ["args=--format,json,--stream"])

    assert result.args == ["--format", "json", "--stream"]
    assert result.model == "gpt-4"


def test_apply_overrides_sets_env_var() -> None:
    agent = AgentConfig(
        id="test-agent",
        frontend="opencode",
        model="model-x",
        args=[],
        env={"EXISTING": "value"},
    )

    result = apply_overrides(agent, ["env.ANTHROPIC_API_KEY=skey-123"])

    assert result.env == {"EXISTING": "value", "ANTHROPIC_API_KEY": "skey-123"}
    assert result.model == "model-x"


def test_apply_overrides_handles_multiple_overrides() -> None:
    agent = AgentConfig(
        id="test-agent",
        frontend="claude",
        model="gpt-4",
        args=["--old"],
        env={"A": "1"},
    )

    result = apply_overrides(agent, [
        "model=new-model",
        "args=--format,json",
        "env.API_KEY=key-123",
    ])

    assert result.model == "new-model"
    assert result.args == ["--format", "json"]
    assert result.env == {"A": "1", "API_KEY": "key-123"}


def test_apply_overrides_rejects_unknown_key() -> None:
    agent = AgentConfig(id="x", frontend="opencode", model="m")

    try:
        apply_overrides(agent, ["unknown_key=value"])
    except ValueError as e:
        assert "unknown_key" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown override key")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_dry_run.py::test_apply_overrides_changes_model -v`
Expected: FAIL with `ImportError: cannot import name 'apply_overrides'`

- [ ] **Step 3: Implement `apply_overrides`**

Add to `src/agent_bencher/suite.py` after the existing functions:

```python
import copy


def apply_overrides(agent: AgentConfig, overrides: list[str]) -> AgentConfig:
    """Apply CLI --override key=value pairs to an AgentConfig.

    Supported keys:
      model=<value>          Replace the model name
      args=<comma-separated> Replace the CLI args list (commas split into list)
      env.KEY=value          Set or override an environment variable

    Raises ValueError for unknown keys.
    """
    result = copy.deepcopy(agent)

    for override in overrides:
        if "=" not in override:
            raise ValueError(f"override must be key=value, got: {override}")
        key, value = override.split("=", 1)

        if key == "model":
            result.model = value
        elif key == "args":
            result.args = [a.strip() for a in value.split(",") if a.strip()]
        elif key.startswith("env."):
            env_key = key[4:]
            result.env[env_key] = value
        else:
            raise ValueError(
                f"unknown override key: {key!r}. "
                f"Supported: model, args, env.NAME"
            )

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_dry_run.py -v`
Expected: All 5 `test_apply_overrides_*` tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/suite.py tests/test_cli_dry_run.py
git commit -m "feat: add apply_overrides for CLI config overrides"
```

---

### Task 2: Add `--dry-run` and `--override` CLI flags

**Files:**
- Modify: `src/agent_bencher/cli.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_cli_dry_run.py`:

```python
from pathlib import Path

from agent_bencher.cli import build_parser, main
from agent_bencher.models import AgentConfig, Conversation, Prompt, SessionResult, TokenUsage, TurnResult


def _make_session(*, run_id: str) -> SessionResult:
    return SessionResult(
        run_id=run_id,
        conversation_name="sample",
        agent_id="test-agent",
        frontend="opencode",
        backend_model="model-x",
        session_id=f"session-{run_id}",
        started_at="2026-06-01T00:00:00Z",
        ended_at="2026-06-01T00:00:01Z",
        duration_seconds=1.0,
        status="completed",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id=f"session-{run_id}",
                exit_code=0,
                duration_seconds=1.0,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=100, output=40),
            )
        ],
        comment="",
    )


def test_build_parser_accepts_dry_run() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["bench", "rc.yaml", "conv.yaml", "--dry-run"])

    assert parsed.dry_run is True


def test_build_parser_accepts_override() -> None:
    parser = build_parser()
    parsed = parser.parse_args([
        "bench", "rc.yaml", "conv.yaml",
        "--override", "model=new-model",
        "--override", "env.API_KEY=key-123",
    ])

    assert parsed.overrides == ["model=new-model", "env.API_KEY=key-123"]


def test_dry_run_prints_commands_without_executing(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this"), Prompt(text="Explain")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="test-agent", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id, **kw):
        root = tmp_path / "trial-0"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)

    commands_built: list[str] = []

    class FakeAdapter:
        def build_start_command(self, *, prompt, variant, workspace):
            commands_built.append(f"start: {prompt.text}")
            return object()

        def build_continue_command(self, *, prompt, variant, workspace, session_id):
            commands_built.append(f"continue: {prompt.text}")
            return object()

    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: FakeAdapter())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kw: None)

    exit_code = main([
        "bench", "rc.yaml", "conv.yaml",
        "--dry-run",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert len(commands_built) == 2


def test_override_is_applied_to_agent_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )

    loaded_agent = AgentConfig(id="test-agent", frontend="opencode", model="original-model")

    def fake_load_config(path):
        return loaded_agent

    monkeypatch.setattr("agent_bencher.cli.load_agent_config", fake_load_config)

    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    agents_seen: list[AgentConfig] = []

    def fake_run_conversation(*, agent, **kw):
        agents_seen.append(agent)
        return _make_session(run_id="run-1")

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id, **kw):
        root = tmp_path / "trial-0"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)
    monkeypatch.setattr("agent_bencher.cli.run_conversation", fake_run_conversation)
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kw: None)

    exit_code = main([
        "bench", "rc.yaml", "conv.yaml",
        "--override", "model=overridden-model",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert exit_code == 0
    assert agents_seen[0].model == "overridden-model"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_dry_run.py::test_build_parser_accepts_dry_run -v`
Expected: FAIL (flag doesn't exist)

- [ ] **Step 3: Add CLI flags**

In `build_parser`, add after the last existing flag:

```python
    bench.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands that would be executed without running them.",
    )
    bench.add_argument(
        "--override",
        action="append",
        default=[],
        help="Override agent config: model=X, args=a,b,c, or env.KEY=val. Can be repeated.",
    )
```

- [ ] **Step 3b: Wire overrides in `main`**

Add `apply_overrides` to the imports from `agent_bencher.suite`:

```python
from agent_bencher.suite import load_agent_config, load_conversation, apply_overrides
```

After `agent = load_agent_config(args.run_config)` in `main`, add:

```python
    if args.overrides:
        agent = apply_overrides(agent, args.overrides)
```

- [ ] **Step 3c: Implement dry-run logic**

Add `_dry_run_trial` function after `positive_int`:

```python
def _dry_run_trial(
    *,
    trial_index: int,
    conversation: Conversation,
    agent: AgentConfig,
    run_id: str,
) -> _TrialResult:
    """Build and print commands that would be executed, without running them."""
    adapter = get_adapter(agent.frontend)

    print(f"\n=== DRY RUN: trial {trial_index + 1} ({run_id}) ===")
    print(f"  agent: {agent.id} ({agent.frontend} / {agent.model})")
    print(f"  workspace: {conversation.source_workspace}")
    print(f"  prompts: {len(conversation.prompts)}")

    for index, prompt in enumerate(conversation.prompts):
        if index == 0:
            cmd = adapter.build_start_command(
                prompt=prompt, variant=agent, workspace=conversation.source_workspace
            )
        else:
            cmd = adapter.build_continue_command(
                prompt=prompt,
                variant=agent,
                workspace=conversation.source_workspace,
                session_id="",
            )
        print(f"\n  Turn {index + 1}: {prompt.text}")
        print(f"    cmd: {' '.join(cmd.argv)}")
        print(f"    cwd: {cmd.cwd}")
        if cmd.env:
            safe_env = {k: v for k, v in cmd.env.items()
                      if not any(s in k.lower() for s in ("key", "token", "secret"))}
            if safe_env:
                print(f"    env: {safe_env}")

    now = datetime.now(timezone.utc).isoformat()
    session = SessionResult(
        run_id=run_id,
        conversation_name=conversation.name,
        agent_id=agent.id,
        frontend=agent.frontend,
        backend_model=agent.model,
        session_id="",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        status="completed",
        prompts_attempted=len(conversation.prompts),
        prompts_completed=len(conversation.prompts),
        turns=[],
        comment="[dry-run]",
    )
    return _TrialResult(session=session, workspace=None)
```

- [ ] **Step 3d: Wire dry-run into `main`**

**Case A: If parallel execution (Improvement 1) has been merged**, update `_run_single_trial` to accept `dry_run` and `use_reflink`:

```python
def _run_single_trial(
    *,
    trial_index: int,
    conversation: Conversation,
    agent: AgentConfig,
    output_dir: Path,
    comment: str,
    dry_run: bool = False,
    use_reflink: bool = False,
) -> _TrialResult:
    trial_started_at = datetime.now(timezone.utc)
    trial_run_id = (
        f"{format_run_id(trial_started_at.strftime('%Y-%m-%d'), trial_started_at.strftime('%H:%M:%S'))}"
        f"-trial-{trial_index + 1:03d}"
    )

    if dry_run:
        return _dry_run_trial(
            trial_index=trial_index,
            conversation=conversation,
            agent=agent,
            run_id=trial_run_id,
        )

    prepared = prepare_variant_workspace(
        source_workspace=conversation.source_workspace,
        run_root=output_dir,
        suite_name=conversation.name,
        variant_id=agent.id,
        use_reflink=use_reflink,
    )
    adapter = get_adapter(agent.frontend)
    session = run_conversation(
        conversation=conversation,
        agent=agent,
        workspace=prepared.variant_workspace,
        adapter=adapter,
        run_command=run_command,
        run_id=trial_run_id,
        started_at=trial_started_at.isoformat(),
        comment=comment,
    )
    return _TrialResult(session=session, workspace=prepared)
```

And in `main`, pass `dry_run=args.dry_run` and `use_reflink=args.reflink` to `_run_single_trial`.

**Case B: If parallel execution has NOT been merged**, replace the `for` loop in `main`:

```python
    if args.dry_run:
        for trial_index in range(args.runs):
            trial_started_at = datetime.now(timezone.utc)
            trial_run_id = (
                f"{format_run_id(trial_started_at.strftime('%Y-%m-%d'), trial_started_at.strftime('%H:%M:%S'))}"
                f"-trial-{trial_index + 1:03d}"
            )
            result = _dry_run_trial(
                trial_index=trial_index,
                conversation=conversation,
                agent=agent,
                run_id=trial_run_id,
            )
            sessions.append(result.session)
        print("\n=== Dry run complete. No artifacts written. ===")
        return 0

    # ... existing for loop unchanged ...
```

Also guard batch output:

```python
    if args.dry_run:
        print("\n=== Dry run complete. No artifacts written. ===")
        return 0

    batch = build_batch_result(...)
    write_batch_results(...)
```

- [ ] **Step 3e: Skip workspace cleanup for dry-run**

In the workspace cleanup loop, the `result.workspace is None` check from `_TrialResult` handles this naturally. Add the guard:

```python
    for result in results:
        if result.workspace and result.session.status == "completed":
            shutil.rmtree(result.workspace.variant_workspace.parent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_dry_run.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing CLI tests for regression**

Run: `pytest tests/test_cli_repeat_runs.py -v`
Expected: All PASS (defaults preserve existing behavior)

- [ ] **Step 6: Commit**

```bash
git add src/agent_bencher/cli.py src/agent_bencher/suite.py tests/test_cli_dry_run.py
git commit -m "feat: add --dry-run and --override CLI flags"
```

---

### Task 3: Run full test suite

**Files:**
- Modify: any file that needs fixes

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "fix: adjust tests for dry-run and CLI overrides"
```
