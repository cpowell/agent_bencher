from __future__ import annotations

from pathlib import Path

import yaml

from agent_bencher.models import AgentConfig, Conversation, Prompt


def load_conversation(path: Path) -> Conversation:
    data = yaml.safe_load(path.read_text())
    prompts = [Prompt(text=item["text"]) for item in data["prompts"]]
    source_workspace = (path.parent / data["source_workspace"]).resolve()

    return Conversation(
        name=data["name"],
        source_workspace=source_workspace,
        prompts=prompts,
    )


def load_agent_config(path: Path) -> AgentConfig:
    data = yaml.safe_load(path.read_text())

    return AgentConfig(
        id=data["id"],
        frontend=data["frontend"],
        model=data["model"],
        args=list(data.get("args", [])),
        env={key: str(value) for key, value in data.get("env", {}).items()},
    )
