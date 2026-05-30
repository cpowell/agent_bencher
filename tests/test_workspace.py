import socket
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

    socket_path = source / "service.sock"
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(socket_path))

    try:
        prepared = prepare_variant_workspace(
            source_workspace=source,
            run_root=tmp_path / "runs",
            suite_name="sample-suite",
            variant_id="opencode-fast",
        )
    finally:
        sock.close()

    assert prepared.variant_workspace.exists()
    assert (prepared.variant_workspace / "README.txt").read_text() == "hello"
    assert not (prepared.variant_workspace / "service.sock").exists()
