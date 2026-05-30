from agent_bencher.adapters.claude import ClaudeAdapter
from agent_bencher.adapters.opencode import OpenCodeAdapter


def get_adapter(frontend: str):
    registry = {
        "claude": ClaudeAdapter,
        "opencode": OpenCodeAdapter,
    }

    if frontend not in registry:
        raise ValueError(f"unsupported frontend: {frontend}")

    return registry[frontend]()
