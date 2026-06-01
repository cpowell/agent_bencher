# agent-bencher

Benchmark real agent frontends over a multi-turn conversation.

## Layout

- `conversations/`: ordered prompt sequences to replay
- `run_configs/`: frontend/model/CLI/env presets
- `runs/`: generated benchmark artifacts

## Conversation Format

`source_workspace` is resolved relative to the conversation YAML file's directory.

```yaml
name: sample-conversation
source_workspace: ..
prompts:
  - text: "Inspect this repository and tell me, in 3 concise bullets, what the benchmark harness currently does."
  - text: "Now summarize the current architecture in 2 short paragraphs, focusing on how a benchmark suite gets executed."
```

## Run Config Format

```yaml
id: opencode-mtplx-qwen36-27b
frontend: opencode
model: mtplx/mtplx-qwen36-27b-optimized-speed
args:
  - --format
  - json
env: {}
```

## Usage

Run one conversation against one run config:

```bash
uv run python -m agent_bencher bench \
  run_configs/opencode-mtplx-qwen36-27b.yaml \
  conversations/sample-conversation.yaml
```

Write artifacts somewhere other than `runs/`:

```bash
uv run python -m agent_bencher bench \
  run_configs/claude-qwen36-27b.yaml \
  conversations/sample-conversation.yaml \
  --output-dir /tmp/agent-bencher-runs \
  --comment "nightly local comparison"
```

Artifacts land under:

```text
runs/<conversation>/<run-config-id>/<run-id>/
```
