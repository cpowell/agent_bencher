from types import SimpleNamespace
from pathlib import Path
import stat

from agent_bencher.workspace import _build_ignore_function, prepare_variant_workspace


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


def test_prepare_variant_workspace_ignores_internal_run_root(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "README.txt").write_text("hello")

    run_root = source / "runs"

    prepared = prepare_variant_workspace(
        source_workspace=source,
        run_root=run_root,
        suite_name="sample-suite",
        variant_id="opencode-fast",
    )

    assert prepared.variant_workspace.exists()
    assert (prepared.variant_workspace / "README.txt").read_text() == "hello"
    assert not (prepared.variant_workspace / "runs").exists()


def test_prepare_variant_workspace_ignores_unix_socket_files(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "README.txt").write_text("hello")
    (source / "service.sock").write_text("placeholder")

    ignore = _build_ignore_function(
        source_workspace=source,
        run_root=source / "runs",
    )

    assert ignore is not None

    original_lstat = Path.lstat

    def fake_lstat(path: Path):
        if path.name == "service.sock":
            return SimpleNamespace(st_mode=stat.S_IFSOCK)
        return original_lstat(path)

    Path.lstat = fake_lstat
    try:
        ignored = ignore(str(source), ["README.txt", "service.sock"])
    finally:
        Path.lstat = original_lstat

    assert ignored == {"service.sock"}
