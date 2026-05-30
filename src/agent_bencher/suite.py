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
