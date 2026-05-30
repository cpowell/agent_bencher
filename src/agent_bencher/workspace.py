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
