from pathlib import Path

from agent_bencher.suite import load_agent_config, load_conversation


def test_load_conversation_preserves_prompt_order(tmp_path: Path) -> None:
    conversation_dir = tmp_path / "conversations"
    conversation_dir.mkdir()
    conversation_path = conversation_dir / "conversation.yaml"
    conversation_path.write_text(
        "\n".join(
            [
                "name: sample-conversation",
                "source_workspace: ../source-project",
                "prompts:",
                "  - text: 'Do this'",
                "  - text: 'Explain that'",
            ]
        )
    )

    conversation = load_conversation(conversation_path)

    assert conversation.name == "sample-conversation"
    assert conversation.source_workspace == tmp_path / "source-project"
    assert [prompt.text for prompt in conversation.prompts] == ["Do this", "Explain that"]


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
