from pathlib import Path

from agent_bencher.suite import load_agent_config, load_conversation


def test_load_conversation_preserves_prompt_order(tmp_path: Path) -> None:
    conversation_path = tmp_path / "conversation.yaml"
    conversation_path.write_text(
        "\n".join(
            [
                "name: sample-conversation",
                "source_workspace: /tmp/source-project",
                "prompts:",
                "  - id: intro",
                "    text: 'Do this'",
                "  - id: explain",
                "    text: 'Explain that'",
            ]
        )
    )

    conversation = load_conversation(conversation_path)

    assert conversation.name == "sample-conversation"
    assert conversation.source_workspace == Path("/tmp/source-project")
    assert [prompt.id for prompt in conversation.prompts] == ["intro", "explain"]


def test_load_agent_config_reads_single_variant_file(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.yaml"
    agent_path.write_text(
        "\n".join(
            [
                "id: opencode-fast",
                "frontend: opencode",
                "model: mtplx/mtplx-qwen36-27b-optimized-speed",
                "args: ['--format', 'json']",
                "env: {}",
            ]
        )
    )

    agent = load_agent_config(agent_path)

    assert agent.id == "opencode-fast"
    assert agent.frontend == "opencode"
    assert agent.model == "mtplx/mtplx-qwen36-27b-optimized-speed"
    assert agent.args == ["--format", "json"]
