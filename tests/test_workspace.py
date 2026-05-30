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
