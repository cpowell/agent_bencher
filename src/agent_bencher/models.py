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
