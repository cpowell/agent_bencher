from pathlib import Path

from agent_bencher.suite import load_suite


def test_load_suite_preserves_prompt_order_and_variant_config(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        "\n".join(
            [
                "name: sample-suite",
                "source_workspace: /tmp/source-project",
                "prompts:",
                "  - id: intro",
                "    text: 'Do this'",
                "  - id: explain",
                "    text: 'Explain that'",
                "variants:",
                "  - id: opencode-fast",
                "    frontend: opencode",
                "    model: mtplx/mtplx-qwen36-27b-optimized-speed",
                "    args: ['--format', 'json']",
                "    env: {}",
            ]
        )
    )

    suite = load_suite(suite_path)

    assert suite.name == "sample-suite"
    assert suite.source_workspace == Path("/tmp/source-project")
    assert [prompt.id for prompt in suite.prompts] == ["intro", "explain"]
    assert suite.variants[0].frontend == "opencode"
    assert suite.variants[0].model == "mtplx/mtplx-qwen36-27b-optimized-speed"
    assert suite.variants[0].args == ["--format", "json"]
