# agent-bencher

- Speed-benchmark real agent frontends against local models over continuing multi-turn conversations. 
- Test and tune your server and model settings for the best possible LLM performance.
- Skip synthetic tests and see how **your** model, agent and server settings execute using **your** style of prompting.

`agent-bencher` replays a conversation sequentially, prompt-by-prompt, against a real agent CLI, measures each turn, and writes artifacts you can inspect later. It currently supports:

- Multi-turn conversation replay against a copied workspace
- `claude` and `opencode` frontend adapters
- Repeated trials with batch-level aggregates
- Per-turn token and throughput metrics
- Human-readable conversation transcripts plus raw stdout/stderr capture
- Visualizations generated from the latest batch for each agent config

You'll receive statistics like this extract:

> ## Run-Level Aggregates
>
> | Metric | Mean | Min | Max | Stddev |
> | --- | ---: | ---: | ---: | ---: |
> | duration_seconds | 115.74 | 100.51 | 142.45 | 18.95 |
> | total_input_tokens | 177219.67 | 169455.00 | 182794.00 | 5661.59 |
> | total_output_tokens | 2954.33 | 2719.00 | 3243.00 | 217.22 |
> | effective_output_tps | 25.88 | 22.77 | 27.82 | 2.22 |
> | effective_total_throughput_tps | 1601.82 | 1212.36 | 1812.10 | 275.68 |

## Requirements

- Python 3.12+, uv
- A frontend CLI installed and available on `PATH`:
  - `claude` for `frontend: claude`
  - `opencode` for `frontend: opencode`
- A server running one or more local models

## Install and usage

Using `uv`:

```bash
uv sync
uv run python -m agent_bencher --help
```

## How to actually use the tool

1. Define your own conversation (or just start with the sample conversation).
1. Set up a server like LM Studio, oMLX with a model, context size, etc.
1. Define a run configuration. The supplied ones for claude and opencode will serve as good templates.
1. Configure your frontend config file. (See below for details on these files.)
    - `~/.config/opencode/opencode.json`
    - `~/.claude/settings.json`
1. Run the tool, for example: 
    `uv run python -m agent_bencher bench ./run_configs/claude-qwen3.6-35B-A3B-oQ6-fp16-mtp.yaml ./conversations/sample-conversation.yaml --runs 3 --comment "MTP enabled, 132K context"`
1. Watch the progress bar:
    ```
    Run started at 2026-06-08T20:29:14Z
    prompt 3/7: Inspect this repository and tell me, in 3...:  29%|█████▍             | 2/7 [00:32<01:26, 17.28s/prompt]
    ```
1. At the conclusion of your run, find your statistics `summary.md` under `runs/[your conversation name]/[your run config]`.

## Important frontend configuration information (don't skip this!)
The tool just executes the frontends via their exposed command line interfaces. But these frontends all configure things slightly differently; there are specifics to be mindful of.

### Claude Code
- In the run configuration YAML file set `args` and `env` for your system.
- Note how all three model definitions point to the same model (the one under test). This is because Claude likes to invoke the Haiku model for its own purposes sometimes; standardizing this way ensures that Claude Code will only invoke the model under test no matter what.
- Note this command line parameter:
    ```
      - --tools
      - "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch,Skill,Agent"  
    ```
    This is important because it drastically reduces tool context usage by excluding tools you won't use locally.
- Your `~/.claude/settings.json` *is* read automatically and *does* need to match your server settings such as the context length. (Context length is set by `CLAUDE_CODE_AUTO_COMPACT_WINDOW`.) Here is a reasonable `env` section you might like to use as a starting point:

    ```
      "env": {
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75",
        "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "132768",
        "CLAUDE_CODE_DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
        "CLAUDE_CODE_DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
        "CLAUDE_CODE_GLOB_TIMEOUT_SECONDS": "60",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "32000",
        "CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE": "1",
        "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",
        "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "900000"
      },
    ```

    If you're running Claude Code against local models these env vars will go a long way to making the experience smooth for you. You can consult https://code.claude.com/docs/en/env-vars for detailed explanations. Unsetting `CLAUDE_CODE_ATTRIBUTION_HEADER` is documented in `https://unsloth.ai/docs/basics/claude-code` as a big aid to local inference speed.

### OpenCode
- `args` and `env` in the run config YAML file are not as important as for Claude Code.
- However your `~/.config/opencode/opencode.json` is critical. This is where you must predefine your provider, model, context length. A model stanza might look like this:
    ```
    "omlx": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "oMLX",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "blah"
      },
      "models": {
        "Qwen3.5-122B-A10B-4bit": {
          "name": "Qwen3.5-122B-A10B-4bit",
          "modalities": {
            "input": [
              "text",
              "image"
            ],
            "output": [
              "text"
            ]
          },
          "attachment": true,
          "limit": {
            "context": 132768,
            "output": 16384
          }
        },
    ```

## Miscellaneous notes
### Repository Layout

- `conversations/`: benchmark conversations to replay
- `run_configs/`: frontend/model presets
- `runs/`: generated benchmark outputs
- `src/agent_bencher/`: CLI, adapters, metrics, reporting, and visualization code
- `tests/`: behavior tests for adapters, CLI, reporting, batching, and charts

### Conversation Format

`source_workspace` is resolved relative to the conversation YAML file.

```yaml
name: sample-conversation
source_workspace: ..
prompts:
  - text: "Inspect this repository and tell me what it does."
  - text: "Now summarize the architecture in 2 short paragraphs."
```

Fields:

- `name`: logical suite name used in artifact paths
- `source_workspace`: repository or directory copied for each trial
- `prompts`: ordered list of prompts sent in sequence

### Run Config Format

```yaml
id: opencode-mtplx-qwen36-27b
frontend: opencode
model: mtplx/mtplx-qwen36-27b-optimized-speed
args:
  - --format
  - json
env: {}
```

Fields:

- `id`: stable agent/config identifier used in artifact paths and reports
- `frontend`: currently `claude` or `opencode`
- `model`: model name recorded in reports and passed to the adapter when relevant
- `args`: extra CLI arguments appended to the frontend command
- `env`: environment variable overrides for the frontend process

### How It Runs

For each trial, the harness:

1. Copies the source workspace into a fresh temporary run directory.
2. Starts the first turn with the selected frontend adapter.
3. Continues later turns using the session ID returned by that frontend.
4. Captures stdout, stderr, exit code, timestamps, and token usage per turn.
5. Writes trial artifacts immediately so partial results survive failures or interrupts.

Successful trial workspaces are deleted after completion. Failed or partial trial workspaces are left on disk for inspection.

### Usage

Run one conversation against one config:

```bash
uv run python -m agent_bencher bench \
  run_configs/opencode-mtplx-qwen36-27b.yaml \
  conversations/sample-conversation.yaml
```

Run repeated trials and attach a note:

```bash
uv run python -m agent_bencher bench \
  run_configs/claude-qwen36-27b.yaml \
  conversations/sample-conversation.yaml \
  --runs 5 \
  --comment "local comparison after prompt edits"
```

Write artifacts somewhere other than `runs/`:

```bash
uv run python -m agent_bencher bench \
  run_configs/claude-qwen36-27b.yaml \
  conversations/sample-conversation.yaml \
  --output-dir /tmp/agent-bencher-runs
```

Generate charts from a conversation directory:

```bash
uv run python -m agent_bencher viz \
  runs/sample-conversation
```

### CLI

#### `bench`

```text
python -m agent_bencher bench <run-config> <conversation> [--runs N] [--comment TEXT] [--output-dir DIR]
```

Options:

- `--runs`: number of repeated trials to execute, default `1`
- `--comment`: optional note recorded in run artifacts
- `--output-dir`: root directory for generated artifacts, default `runs`

#### `viz`

```text
python -m agent_bencher viz <conversation-dir>
```

This command reads the latest batch directory for each agent under the conversation directory and writes PNG charts to `<conversation-dir>/viz/`.

Charts currently generated:

- `duration.png`
- `output_tps.png`
- `total_throughput_tps.png`

### Artifact Layout

Batch runs are written under:

```text
runs/<conversation>/<agent-id>/<batch-id>/
```

Within each batch directory:

```text
batch.json
summary.md
trials/
  trial-001/
    conversation.md
    run.json
    summary.md
    turns.jsonl
    transcripts/
      01-01.stdout.txt
      01-01.stderr.txt
```

Key artifacts:

- `batch.json`: batch-level metadata, success counts, aggregate metrics, and trial index
- `summary.md`: batch summary with run-level and per-turn aggregates
- `trials/trial-###/run.json`: compact per-trial totals and effective throughput metrics
- `trials/trial-###/turns.jsonl`: one JSON record per turn
- `trials/trial-###/conversation.md`: human-readable prompt/response transcript with timestamps
- `trials/trial-###/transcripts/*`: raw stdout/stderr captured for each turn

### Metrics

The harness records:

- Duration per turn and per run
- Prompt input tokens
- Output tokens
- Reasoning tokens
- Cache read and cache write tokens
- Output tokens per second
- Total throughput tokens per second

Input token totals include cache read and cache write tokens.

Batch summaries aggregate successful trials only, with mean/min/max/stddev for run-level and per-turn metrics.

## Frontend Adapters

### Claude

- Starts with `claude -p <prompt> ...`
- Continues with `claude -p <prompt> --resume <session_id> ...`
- Parses JSON output and recovers some fields even from malformed JSON when possible

### OpenCode

- Starts with `opencode run ... -m <model> <prompt>`
- Continues with `opencode run ... -m <model> --session <session_id> <prompt>`
- Parses JSONL event streams for session IDs, token counts, and fatal errors

## Notes

- The harness writes partial artifacts during multi-run batches, so interrupted runs still leave usable data behind.
- `viz` ignores the `viz/` directory itself and compares the latest batch found for each agent config.
- Progress is shown on stderr when the process is attached to a TTY.
