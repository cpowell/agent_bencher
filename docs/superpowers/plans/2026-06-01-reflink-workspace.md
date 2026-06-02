# Copy-on-Write Workspace Setup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace full `shutil.copytree` with copy-on-write (reflink) workspace copies, reducing per-trial workspace setup from seconds to milliseconds on APFS/Btrfs.

**Architecture:** Add a `_reflink_copy_file` function that calls `shutil.copyfile` with `reflink='always'` (APFS clonefile syscall on macOS, btrfs reflink on Linux), falling back to `shutil.copy2` when reflink is unavailable. Wire it into `prepare_variant_workspace` via `shutil.copytree`'s `copy_function` parameter. The existing `ignore` function continues to work since `copytree` supports both `ignore` and `copy_function` simultaneously.

**Tech Stack:** `shutil.copyfile(reflink='always')`, `shutil.copystat`, `shutil.copytree(copy_function=...)`

---

### File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/agent_bencher/workspace.py` | Add `_reflink_copy_file`, add `use_reflink` parameter to `prepare_variant_workspace` |
| Modify | `src/agent_bencher/cli.py` | Add `--reflink` CLI flag, pass to `prepare_variant_workspace` |
| Create | `tests/test_workspace_reflink.py` | Tests for reflink copy, fallback behavior |

---

### Task 1: Add `_reflink_copy_file` helper

**Files:**
- Modify: `src/agent_bencher/workspace.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_workspace_reflink.py`:

```python
from pathlib import Path
import stat

from agent_bencher.workspace import _reflink_copy_file


def test_reflink_copy_file_copies_content(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello world")

    _reflink_copy_file(src, dst)

    assert dst.read_text() == "hello world"
    assert dst.stat().st_size == src.stat().st_size


def test_reflink_copy_file_preserves_metadata(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello world")
    src.chmod(0o644)

    _reflink_copy_file(src, dst)

    assert dst.stat().st_mode & 0o777 == src.stat().st_mode & 0o777


def test_reflink_copy_file_fallback_on_unsupported_filesystem(monkeypatch, tmp_path: Path) -> None:
    import shutil

    original_copyfile = shutil.copyfile

    def fake_copyfile(*args, **kwargs):
        if kwargs.get("reflink"):
            raise ValueError("reflink not supported")
        return original_copyfile(*args, **kwargs)

    monkeypatch.setattr("agent_bencher.workspace.shutil.copyfile", fake_copyfile)

    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello world")

    _reflink_copy_file(src, dst)

    assert dst.read_text() == "hello world"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workspace_reflink.py -v`
Expected: FAIL with `ImportError: cannot import name '_reflink_copy_file'`

- [ ] **Step 3: Implement `_reflink_copy_file`**

Add to `src/agent_bencher/workspace.py` after the imports, before `PreparedWorkspace`:

```python
def _reflink_copy_file(src: Path, dst: Path, *, follow_symlinks: bool = True) -> None:
    """Copy a single file using copy-on-write reflink if available, falling back to copy2.

    On macOS (APFS), uses the clonefile syscall via shutil.copyfile(reflink='always').
    On Linux (btrfs/xfs), uses reflink via the same mechanism.
    Falls back to shutil.copy2 + copystat if reflink is not supported.
    """
    try:
        shutil.copyfile(str(src), str(dst), follow_symlinks=follow_symlinks, reflink="always")
    except (OSError, ValueError):
        shutil.copyfile(str(src), str(dst), follow_symlinks=follow_symlinks)
    shutil.copystat(str(src), str(dst), follow_symlinks=follow_symlinks)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workspace_reflink.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/workspace.py tests/test_workspace_reflink.py
git commit -m "feat: add _reflink_copy_file for copy-on-write workspace setup"
```

---

### Task 2: Wire reflink into `prepare_variant_workspace`

**Files:**
- Modify: `src/agent_bencher/workspace.py` (add `use_reflink` parameter)

- [ ] **Step 1: Write the test**

Add to `tests/test_workspace_reflink.py`:

```python
from agent_bencher.workspace import prepare_variant_workspace


def test_prepare_variant_workspace_uses_reflink_when_enabled(tmp_path: Path) -> None:
    import shutil

    copyfile_calls: list[dict] = []

    original_copyfile = shutil.copyfile

    def tracking_copyfile(*args, **kwargs):
        copyfile_calls.append(kwargs)
        return original_copyfile(*args, **kwargs)

    source = tmp_path / "source"
    source.mkdir()
    (source / "README.txt").write_text("hello")

    run_root = tmp_path / "runs"

    import agent_bencher.workspace as ws_module
    original_module_copyfile = ws_module.shutil.copyfile

    def fake_copyfile(*args, **kwargs):
        copyfile_calls.append(kwargs)
        # Don't actually try reflink, just track what was requested
        if kwargs.get("reflink"):
            raise ValueError("reflink not supported in test")
        return original_copyfile(*args, **kwargs)

    ws_module.shutil.copyfile = fake_copyfile
    try:
        prepared = prepare_variant_workspace(
            source_workspace=source,
            run_root=run_root,
            suite_name="sample-suite",
            variant_id="test-agent",
            use_reflink=True,
        )
    finally:
        ws_module.shutil.copyfile = original_module_copyfile

    assert prepared.variant_workspace.exists()
    assert (prepared.variant_workspace / "README.txt").read_text() == "hello"
    # Verify that _reflink_copy_file was used (it tries reflink='always' first)
    assert any(kwargs.get("reflink") == "always" for kwargs in copyfile_calls), \
        f"expected reflink='always' in copyfile calls, got {copyfile_calls}"


def test_prepare_variant_workspace_skips_reflink_by_default(tmp_path: Path) -> None:
    import shutil

    copyfile_calls: list[dict] = []

    original_copyfile = shutil.copyfile

    import agent_bencher.workspace as ws_module

    def fake_copyfile(*args, **kwargs):
        copyfile_calls.append(kwargs)
        if kwargs.get("reflink"):
            raise ValueError("reflink not supported")
        return original_copyfile(*args, **kwargs)

    source = tmp_path / "source"
    source.mkdir()
    (source / "README.txt").write_text("hello")

    run_root = tmp_path / "runs"

    ws_module.shutil.copyfile = fake_copyfile
    try:
        prepared = prepare_variant_workspace(
            source_workspace=source,
            run_root=run_root,
            suite_name="sample-suite",
            variant_id="test-agent",
        )
    finally:
        ws_module.shutil.copyfile = original_copyfile

    assert prepared.variant_workspace.exists()
    # Default should NOT pass reflink to copyfile
    assert not any(kwargs.get("reflink") for kwargs in copyfile_calls), \
        f"expected no reflink by default, got {copyfile_calls}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workspace_reflink.py::test_prepare_variant_workspace_uses_reflink_when_enabled tests/test_workspace_reflink.py::test_prepare_variant_workspace_skips_reflink_by_default -v`
Expected: FAIL (parameter doesn't exist)

- [ ] **Step 3: Add `use_reflink` parameter to `prepare_variant_workspace`**

Modify `prepare_variant_workspace` in `src/agent_bencher/workspace.py` (lines 56-72):

```python
def prepare_variant_workspace(
    *,
    source_workspace: Path,
    run_root: Path,
    suite_name: str,
    variant_id: str,
    use_reflink: bool = False,
) -> PreparedWorkspace:
    run_id = uuid.uuid4().hex[:8]
    base_dir = run_root / suite_name / variant_id / run_id
    workspace_dir = base_dir / "workspace"
    artifacts_dir = base_dir / "artifacts"
    ignore = _build_ignore_function(source_workspace=source_workspace, run_root=run_root)

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    copy_function = _reflink_copy_file if use_reflink else None
    kwargs: dict[str, object] = {"ignore": ignore} if ignore else {}
    if copy_function is not None:
        kwargs["copy_function"] = copy_function

    shutil.copytree(source_workspace, workspace_dir, **kwargs)

    return PreparedWorkspace(
        variant_workspace=workspace_dir,
        artifacts_dir=artifacts_dir,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workspace_reflink.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_bencher/workspace.py tests/test_workspace_reflink.py
git commit -m "feat: add use_reflink parameter to prepare_variant_workspace"
```

---

### Task 3: Add `--reflink` CLI flag

**Files:**
- Modify: `src/agent_bencher/cli.py` (add `--reflink` flag, pass to `prepare_variant_workspace`)

- [ ] **Step 1: Write the test**

Add to `tests/test_workspace_reflink.py`:

```python
from agent_bencher.cli import main


def test_main_passes_reflink_flag_to_workspace(monkeypatch, tmp_path: Path) -> None:
    from agent_bencher.models import AgentConfig, Conversation, Prompt

    monkeypatch.setattr(
        "agent_bencher.cli.load_conversation",
        lambda _path: Conversation(
            name="sample",
            source_workspace=tmp_path / "source",
            prompts=[Prompt(text="Do this")],
        ),
    )
    monkeypatch.setattr(
        "agent_bencher.cli.load_agent_config",
        lambda _path: AgentConfig(id="test-agent", frontend="opencode", model="model-x"),
    )

    class PreparedWorkspace:
        def __init__(self, path: Path) -> None:
            self.variant_workspace = path

    reflink_values: list[bool] = []

    def fake_prepare(*, source_workspace, run_root, suite_name, variant_id, use_reflink=False):
        reflink_values.append(use_reflink)
        root = tmp_path / "trial-0"
        ws = root / "workspace"
        ws.mkdir(parents=True)
        (root / "artifacts").mkdir()
        return PreparedWorkspace(ws)

    monkeypatch.setattr("agent_bencher.cli.prepare_variant_workspace", fake_prepare)
    monkeypatch.setattr("agent_bencher.cli.get_adapter", lambda f: object())
    monkeypatch.setattr("agent_bencher.cli.run_command", lambda c: None)

    from agent_bencher.models import SessionResult, TokenUsage, TurnResult

    def _make_session() -> SessionResult:
        return SessionResult(
            run_id="trial-1",
            conversation_name="sample",
            agent_id="test-agent",
            frontend="opencode",
            backend_model="model-x",
            session_id="sess-1",
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
                    session_id="sess-1",
                    exit_code=0,
                    duration_seconds=1.0,
                    stdout="{}",
                    stderr="",
                    token_usage=TokenUsage(input=100, output=40),
                )
            ],
            comment="",
        )

    monkeypatch.setattr("agent_bencher.cli.run_conversation", lambda **kw: _make_session())
    monkeypatch.setattr("agent_bencher.cli.write_batch_results", lambda **kw: None)

    # With --reflink
    main([
        "bench", "rc.yaml", "conv.yaml",
        "--reflink",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert reflink_values == [True], f"expected use_reflink=True, got {reflink_values}"

    # Without --reflink (default)
    reflink_values.clear()
    main([
        "bench", "rc.yaml", "conv.yaml",
        "--output-dir", str(tmp_path / "runs"),
    ])

    assert reflink_values == [False], f"expected use_reflink=False by default, got {reflink_values}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workspace_reflink.py::test_main_passes_reflink_flag_to_workspace -v`
Expected: FAIL (flag doesn't exist)

- [ ] **Step 3: Add `--reflink` flag to the CLI**

In `build_parser`, add after `--jobs`:

```python
    bench.add_argument(
        "--reflink",
        action="store_true",
        help="Use copy-on-write (reflink) for workspace copies. Reduces disk I/O on APFS/Btrfs.",
    )
```

- [ ] **Step 3b: Pass `use_reflink` to `prepare_variant_workspace`**

In `_run_single_trial` (or in the `main` loop if parallel execution hasn't been merged yet), pass `use_reflink`:

```python
    prepared = prepare_variant_workspace(
        source_workspace=conversation.source_workspace,
        run_root=output_dir,
        suite_name=conversation.name,
        variant_id=agent.id,
        use_reflink=use_reflink,
    )
```

Update `_run_single_trial` signature to accept `use_reflink: bool = False` and pass it through.

If parallel execution (Improvement 1) has already been merged, also update `main` to pass `args.reflink` to `_run_single_trial`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workspace_reflink.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing workspace tests for regression**

Run: `pytest tests/test_workspace.py -v`
Expected: All PASS (default `use_reflink=False` preserves existing behavior)

- [ ] **Step 6: Commit**

```bash
git add src/agent_bencher/cli.py src/agent_bencher/workspace.py tests/test_workspace_reflink.py
git commit -m "feat: add --reflink CLI flag for copy-on-write workspace setup"
```

---

### Task 4: Run full test suite

**Files:**
- Modify: any file that needs fixes

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "fix: adjust tests for reflink workspace setup"
```
