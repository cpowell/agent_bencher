# Agent Benchmark Harness Design

Date: 2026-05-30

## Goal

Build a personal Python-based benchmark harness that measures real end-to-end agent frontend performance over a continuing conversation. The harness must execute the actual `OpenCode` and `Claude Code` CLIs, preserve their normal session behavior, and report wall-clock timing and CLI-reported token metrics without estimating missing values.

## Scope

V1 benchmarks one ordered prompt suite as one continuing conversation per frontend/backend-model variant.

Included in v1:

- Run the real `opencode` CLI
- Run the real `claude` CLI in headless mode
- Start a new agent session on prompt 1
- Continue the same session for later prompts
- Use one fresh copied workspace per variant run
- Capture per-turn timing, exit status, transcripts, session IDs, and parsed CLI token metrics
- Emit machine-readable JSON results
- Emit human-readable Markdown summaries

Explicitly not in v1:

- Isolated one-shot prompt mode
- Automatic pass/fail task assertions beyond process exit behavior
- Estimated token counts
- Automatic retries
- Extensive test coverage
- Git-based workspace preparation
- Fine-grained tool-call or interstitial telemetry

## Non-Goals

This harness is not intended to:

- Compare raw model APIs outside the agent frontends
- Normalize away frontend differences in prompts, permissions, or context handling
- Replace the native reporting or session UIs of `OpenCode` or `Claude Code`
- Produce lab-grade statistically rigorous benchmarking in v1

## Core Principle

The benchmark must measure the real agent frontend path, not a synthetic approximation.

That means:

- Use the actual CLI binaries
- Preserve normal frontend session semantics
- Preserve system prompts and built-in tooling behavior
- Preserve context accumulation across prompts
- Parse token metrics only from real CLI output or session artifacts

The harness must not talk directly to model APIs as a substitute for the frontend.

## User Workflow

The user writes a suite file containing:

- an ordered list of prompts representing one conversation
- one or more frontend/backend-model variants
- the source workspace path to copy before each variant run

The user runs the harness against the suite file.

For each variant, the harness:

1. Copies the source workspace into a fresh temporary run directory.
2. Starts a real agent session with prompt 1.
3. Continues that same session with prompts 2..N in order.
4. Records per-turn artifacts and telemetry.
5. Computes session totals after the full conversation ends or fails.
6. Writes JSON and Markdown artifacts into a timestamped results directory.

The user can then change the frontend variant configuration, backend model, or environment settings and rerun the same suite for comparison.

## Architecture

The harness should be split into small units with clear responsibilities.

### 1. Suite Loader

Responsibilities:

- Load one suite definition from YAML or JSON
- Validate required fields
- Preserve prompt ordering
- Expand frontend/backend-model variants into runnable benchmark variants

The suite is modeled as a conversation script, not a bag of independent tasks.

### 2. Workspace Sandbox Manager

Responsibilities:

- Copy the configured source workspace into a fresh temporary directory per variant run
- Return the copied workspace path to the adapter
- Keep each variant isolated from the others

The workspace is shared across all prompts in the same conversation run so filesystem changes accumulate naturally within that run.

### 3. Frontend Adapters

Responsibilities:

- Build the exact command line for each turn
- Inject per-variant environment variables
- Start a new session on turn 1
- Continue the same session on later turns
- Capture stdout/stderr
- Extract or locate the frontend session identifier
- Parse CLI-reported token metrics

There is one adapter for `OpenCode` and one for `Claude Code`.

The adapter boundary is the key extension point because the two frontends differ in:

- command syntax
- session continuation mechanics
- environment-based configuration
- output format
- token reporting surface

### 4. Telemetry Collector

Responsibilities:

- Measure wall-clock start and end times per turn
- Calculate per-turn duration
- Retain exit codes
- Attach parsed token metrics to each turn
- Compute derived throughput using only valid CLI-reported token counts

### 5. Result Recorder

Responsibilities:

- Write turn-level JSON records
- Write session-level aggregate JSON
- Store raw stdout/stderr transcripts
- Preserve warnings about parser uncertainty or incomplete runs

### 6. Report Generator

Responsibilities:

- Read raw JSON results
- Produce a Markdown summary for quick human review
- Show both turn-level and session-level results
- Make incomplete conversations obvious

## Frontend Feasibility Assumptions

The design is based on user-confirmed invocation patterns.

### OpenCode

Confirmed working patterns:

```bash
opencode run --format json -m mtplx/mtplx-qwen36-27b-optimized-speed "Reply with exactly OK"
opencode run --format json -m omlx/Qwen3.6-35B-A3B-4bit "Reply with exactly OK"
```

Design implications:

- `opencode run --format json` is the primary automation surface
- provider/model should be treated as explicit run configuration
- the adapter should preserve the real `OpenCode` session lifecycle

### Claude Code

Confirmed target pattern:

```bash
ANTHROPIC_BASE_URL='http://127.0.0.1:8000' \
ANTHROPIC_AUTH_TOKEN='blah' \
ANTHROPIC_DEFAULT_OPUS_MODEL='Qwen3.6-27B-4bit' \
ANTHROPIC_DEFAULT_SONNET_MODEL='Qwen3.6-35B-A3B-4bit' \
ANTHROPIC_DEFAULT_HAIKU_MODEL='Qwen3.6-35B-A3B-4bit' \
API_TIMEOUT_MS=3000000 \
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
claude -p "Reply with exactly OK" \
  --output-format json \
  --permission-mode bypassPermissions \
  --model opus
```

Design implications:

- the adapter must support per-variant environment maps
- `claude -p` is the primary automation surface
- benchmarking identity should be reported by backend model, not by Claude tier alias
- Claude tier is treated as an execution detail, not part of the reported identity in v1

## Data Model

The harness should persist both turn-level and session-level results.

### Turn-Level Record

Each turn record should include:

- suite identifier
- variant identifier
- frontend name
- backend model name
- prompt index
- prompt label or prompt ID
- prompt text or prompt file reference
- workspace path
- session identifier
- turn start timestamp
- turn end timestamp
- turn duration
- exit code
- stdout transcript path
- stderr transcript path
- parsed token metrics
- derived throughput values when token metrics are valid
- parser warnings

### Session-Level Aggregate

Each session record should include:

- suite identifier
- variant identifier
- frontend name
- backend model name
- workspace path
- session identifier
- number of prompts attempted
- number of prompts completed
- total start timestamp
- total end timestamp
- total wall-clock duration
- summed token metrics by category
- aggregate throughput values
- final exit status
- paths to related turn records and summary artifacts

## Suite File Shape

The suite should be YAML by default, with JSON support acceptable if convenient.

The suite must represent one ordered conversation and one or more variants to replay it against.

Representative shape:

```yaml
name: basic-conversation-benchmark
source_workspace: ../project
prompts:
  - text: "Do this"
  - text: "Explain that"
variants:
  - id: opencode-mtplx-27b
    frontend: opencode
    model: mtplx/mtplx-qwen36-27b-optimized-speed
    args:
      - --format
      - json
    env: {}
  - id: claude-qwen-opus
    frontend: claude
    model: Qwen3.6-27B-4bit
    args:
      - --output-format
      - json
      - --permission-mode
      - bypassPermissions
      - --model
      - opus
    env:
      ANTHROPIC_BASE_URL: http://127.0.0.1:8000
      ANTHROPIC_AUTH_TOKEN: blah
      ANTHROPIC_DEFAULT_OPUS_MODEL: Qwen3.6-27B-4bit
      ANTHROPIC_DEFAULT_SONNET_MODEL: Qwen3.6-35B-A3B-4bit
      ANTHROPIC_DEFAULT_HAIKU_MODEL: Qwen3.6-35B-A3B-4bit
      API_TIMEOUT_MS: "3000000"
      CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1"
```

The precise field names may change during implementation, but the suite must preserve these semantics:

- ordered prompts
- source workspace path
- explicit frontend identity
- explicit backend-model identity
- per-variant arguments
- per-variant environment

## Conversation Execution Model

For each variant:

1. Copy the source workspace once.
2. Start a fresh frontend session in the copied workspace.
3. Send prompt 1.
4. Parse the resulting session identifier and token metrics.
5. Continue the same session for prompt 2 and later prompts.
6. Stop on the first unrecoverable failure.
7. Write a partial result if the conversation did not complete.

The harness must use each frontend's native continuation mechanism. It must not emulate continuation by replaying old prompts into a new session.

## Output Artifacts

Each harness run should create a timestamped results directory.

It should contain:

- raw turn-level JSON
- raw session-level aggregate JSON
- per-turn stdout transcripts
- per-turn stderr transcripts
- a Markdown summary report
- optional copied suite file for reproducibility

The Markdown report should show:

- per-variant session totals
- per-turn breakdowns
- incomplete conversation markers such as `completed 3/5 prompts`
- parser warnings when token metrics were not fully valid

## Token Metrics Policy

V1 uses only CLI-reported token metrics.

Rules:

- never estimate token counts
- never backfill token counts from a tokenizer library
- if token parsing fails, token fields are invalid rather than guessed
- throughput is computed only when the required token counts are valid

If the frontend exposes token metrics cumulatively rather than per turn, the adapter may derive per-turn deltas from successive cumulative values as long as the derivation is exact and based only on frontend-reported values.

## Error Handling

The harness is a data collection tool. Failures are themselves benchmark results when they occur inside the frontend run.

### Startup Failure

Examples:

- CLI binary missing
- invalid command arguments
- auth or provider env misconfigured
- first prompt cannot start a session

Behavior:

- mark the variant failed
- record the startup failure
- stop that variant immediately

### Mid-Conversation Failure

Examples:

- turn N exits non-zero
- session continuation fails
- provider call fails during a later turn

Behavior:

- record the failed turn
- preserve transcripts and any valid token metrics
- stop the conversation for that variant
- report the session as incomplete

### Parse Failure

Examples:

- token metrics missing from output
- session ID cannot be extracted
- output format drift breaks parsing

Behavior:

- record the turn and session
- mark affected fields invalid
- attach parser warnings
- do not invent replacement values

### Harness Failure

Examples:

- suite schema invalid
- workspace copy fails
- internal harness exception

Behavior:

- fail the run or variant as appropriate
- surface the harness error clearly

## Testing Strategy

Testing in v1 is intentionally minimal and protects only the golden path and integrity-critical pieces.

Included:

- suite parsing sanity check
- adapter continuation command construction checks
- parser fixture tests using real captured CLI outputs
- one fake-adapter smoke test for a multi-turn conversation
- manual live verification of one short conversation per frontend

Explicitly deferred:

- broad unit test coverage
- extensive edge-case coverage
- automatic failure-mode simulation
- performance benchmarking of the harness itself

## Operational Constraints

- The harness is a personal tool, so pragmatism is preferred over framework-heavy design.
- It should be easy to edit model names, environment variables, and prompt suites without changing Python code.
- The harness should favor readable result artifacts over over-abstracted internals.
- The workspace `/Users/chris/Code/python/agent_bencher` is not currently a git repository, so this spec can be written here but cannot be committed until the project is placed in or initialized as a git repo.

## Open Decisions Deferred to Implementation Planning

These are intentionally left for the implementation plan rather than expanded here:

- exact Python package layout
- specific schema validation library, if any
- exact temp-directory retention policy
- exact Markdown table format
- exact JSON file partitioning strategy
- whether YAML support is implemented directly or through a general config loader

These are implementation details, not design blockers.
