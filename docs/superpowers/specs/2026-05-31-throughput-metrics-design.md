# Throughput Metrics Design

## Goal

Add a lowest-common-denominator throughput layer to benchmark artifacts so `OpenCode` and `Claude Code` can be compared honestly with the same definitions and without frontend-specific heuristics.

The metrics should be emitted directly by the runner into the machine-readable run artifacts. A later reporting interface can ingest them without recomputing core values.

## Principles

- Use only timings the runner can measure consistently across frontends.
- Do not infer internal model phases such as "thinking time" or "streaming time" unless every frontend exposes them reliably.
- Keep reasoning tokens out of the primary throughput metrics for now.
- Store derived throughput metrics in `run.json` and `turns.jsonl` as convenience fields, while preserving the raw duration and token counts they are derived from.

## Metric Model

### Canonical Timing Definition

All throughput metrics are based on full end-to-end measured duration.

For a turn, `duration_seconds` means:
- frontend subprocess launch
- through subprocess exit

For a run, `duration_seconds` means:
- first turn subprocess launch
- through final turn subprocess exit

This excludes harness bookkeeping such as workspace copy, transcript writing, and summary generation.

### Per-Turn Metrics

Each turn record in `turns.jsonl` should include:

- `duration_seconds`
- `input_tokens`
- `output_tokens`
- `output_tps`
- `total_throughput_tps`

Definitions:

- `output_tps = output_tokens / duration_seconds`
- `total_throughput_tps = (input_tokens + output_tokens) / duration_seconds`

If `duration_seconds` is zero, both derived TPS fields should be written as `0.0` to avoid division errors and keep the schema simple.

### Per-Run Metrics

Each run record in `run.json` should include:

- `duration_seconds`
- `total_input_tokens`
- `total_output_tokens`
- `effective_output_tps`
- `effective_total_throughput_tps`

Definitions:

- `effective_output_tps = total_output_tokens / duration_seconds`
- `effective_total_throughput_tps = (total_input_tokens + total_output_tokens) / duration_seconds`

If `duration_seconds` is zero, both derived run-level TPS fields should be written as `0.0`.

## Why This Model

This model is intentionally narrower than the earlier conversation about "processing time" and "outputting time."

The runner always knows:
- when a turn started
- when a turn ended

The runner does not always know:
- when the first readable response began

`OpenCode` exposes useful streamed event timestamps, but `Claude Code` does not currently expose enough data in a trustworthy, frontend-independent way to support an apples-to-apples phase split. Trying to infer that split would make the benchmark look more precise than it really is.

Using full end-to-end duration keeps the benchmark honest and comparable.

## Artifact Changes

### turns.jsonl

Each turn object keeps the existing timing, token, transcript, and warning fields, and adds:

- `output_tps`
- `total_throughput_tps`

The turn object should still include:

- `run_id`
- `turn_index`
- `prompt_id`
- `prompt_text`
- `session_id`
- `exit_code`
- `duration_seconds`
- `started_at`
- `ended_at`
- `input_tokens`
- `output_tokens`
- `reasoning_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `stdout_path`
- `stderr_path`
- `warnings`

### run.json

The run object keeps the existing summary fields and adds:

- `effective_output_tps`
- `effective_total_throughput_tps`

The run object should still include:

- `run_id`
- `conversation_name`
- `agent_id`
- `frontend`
- `backend_model`
- `started_at`
- `ended_at`
- `duration_seconds`
- `prompts_attempted`
- `prompts_completed`
- `session_id`
- `status`
- `total_input_tokens`
- `total_output_tokens`
- `total_reasoning_tokens`
- `total_cache_read_tokens`
- `total_cache_write_tokens`
- `conversation_path`
- `transcript_dir`

## Reporting Implications

The later reporting interface can treat these fields as the canonical benchmark throughput numbers:

- per-turn `output_tps`
- per-turn `total_throughput_tps`
- per-run `effective_output_tps`
- per-run `effective_total_throughput_tps`

This keeps the reporting layer simple. It only has to ingest and graph the values rather than redefining them.

The reporting interface may still recompute these values as a validation step, but it should not need to invent or infer them.

## Non-Goals

This design does not introduce:

- "thinking time"
- "pre-response latency"
- "response streaming duration"
- throughput definitions that include reasoning tokens
- frontend-specific derived metrics that only some adapters can populate

Those can be reconsidered later as optional advanced metrics if every frontend can support them honestly or if the tool explicitly distinguishes universal metrics from frontend-specific diagnostics.

## Testing Scope

Implementation should verify:

- per-turn TPS fields are emitted into `turns.jsonl`
- per-run TPS fields are emitted into `run.json`
- calculations match the existing token and duration fields
- zero-duration cases do not crash and emit `0.0`

Golden-path coverage is sufficient for v1. This does not require a large new test surface.
