from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import stat
import uuid


@dataclass(slots=True)
class PreparedWorkspace:
    variant_workspace: Path
    artifacts_dir: Path


def _build_ignore_function(*, source_workspace: Path, run_root: Path):
    source_resolved = source_workspace.resolve()
    run_root_resolved = run_root.resolve()

    try:
        ignored_subtree = run_root_resolved.relative_to(source_resolved)
    except ValueError:
        ignored_subtree = None

    if ignored_subtree is None or not ignored_subtree.parts:
        return None

    ignored_parts = ignored_subtree.parts

    def ignore(current_dir: str, names: list[str]) -> set[str]:
        current_path = Path(current_dir).resolve()
        current_relative = current_path.relative_to(source_resolved)
        current_parts = current_relative.parts
        ignored_names: set[str] = set()

        for name in names:
            candidate_parts = current_parts + (name,)
            if ignored_parts[: len(candidate_parts)] == candidate_parts:
                ignored_names.add(name)
                continue

            candidate_path = current_path / name
            mode = candidate_path.lstat().st_mode
            is_copyable = (
                stat.S_ISREG(mode)
                or stat.S_ISDIR(mode)
                or stat.S_ISLNK(mode)
            )
            if not is_copyable:
                ignored_names.add(name)

        return ignored_names

    return ignore


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
    ignore = _build_ignore_function(source_workspace=source_workspace, run_root=run_root)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_workspace, workspace_dir, ignore=ignore)

    return PreparedWorkspace(
        variant_workspace=workspace_dir,
        artifacts_dir=artifacts_dir,
    )
