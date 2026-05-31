# Reporting Artifact Design

Date: 2026-05-31

## Goal

Adjust the benchmark runner's output so a future reporting interface can recurse the `runs/` tree, ingest concise machine-readable artifacts, and summarize or graph benchmark history without reverse-engineering human-facing files.

## Scope

This design covers only the artifact and directory shape produced by the runner after a benchmark invocation.

Included in scope:

- immutable per-run output directories
- stable machine-readable per-run artifacts
- stable machine-readable per-turn artifacts
- timing semantics for measured benchmark duration
- failure handling for partial and failed runs

Explicitly out of scope:

- the future reporting UI itself
- global manifest or index files
- benchmark execution logic unrelated to artifact production
- request-proxy or hidden prompt introspection

## Problem Statement

The current runner writes outputs under:

`runs/<conversation>/<agent>/`

This has two problems:

1. repeated runs of the same conversation/agent pair overwrite top-level artifacts such as `summary.md`, `conversation.md`, and the session JSON
2. the machine-readable output is too session-centric and too close to an internal debug dump for a downstream reporting tool to ingest cleanly

The runner needs a durable, append-only output model so the reporting layer can sweep the filesystem and treat each benchmark invocation as an immutable record.

## Core Decision

Each benchmark invocation should write to its own immutable run directory:

`runs/<conversation>/<agent>/<run-id>/`

The `run-id` should be timestamp-only, using a cross-platform-safe format:

`2026-05-28T14-26-00`

This format is:

- readable
- sortable lexicographically
- safe on Windows and other filesystems that reject `:`

## Artifact Layout

For one benchmark invocation, the run directory should contain:

- `run.json`
- `turns.jsonl`
- `summary.md`
- `conversation.md`
- `transcripts/`
- optionally `workspace/` if the copied workspace continues to be retained

Example:

```text
runs/
  sample-conversation/
    claude-qwen36-35b/
      2026-05-31T14-26-00/
        run.json
        turns.jsonl
        summary.md
        conversation.md
        transcripts/
          01-inspect.stdout.txt
          01-inspect.stderr.txt
          02-summarize.stdout.txt
          02-summarize.stderr.txt
        workspace/
```

## Artifact Roles

### `run.json`

This is the canonical machine-readable summary for one benchmark invocation.

It should contain one compact object with:

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

It should not embed large stdout or stderr blobs.

### `turns.jsonl`

This is the canonical machine-readable per-turn feed.

It should contain one JSON object per prompt turn with:

- `run_id`
- `turn_index`
- `prompt_id`
- `prompt_text`
- `session_id`
- `exit_code`
- `duration_seconds`
- `input_tokens`
- `output_tokens`
- `reasoning_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `stdout_path`
- `stderr_path`
- `warnings`

This format is intended for:

- charting
- per-turn comparisons
- long-term aggregation
- simple tabular import

### `summary.md`

This remains a human-facing artifact.

It should provide:

- top-level totals
- one per-turn metrics table
- links or file paths to transcript files
- a reference to `conversation.md`

This file is not the canonical source for reporting ingestion.

### `conversation.md`

This remains a human-facing artifact.

It should present:

- the prompt sequence
- the human-readable assistant responses
- optional stderr sections only when useful

It should avoid raw metadata-heavy event dumps wherever practical.

### `transcripts/`

This directory should preserve the raw per-turn stdout and stderr streams as plain text files.

These are the durable low-level artifacts the runner can always emit even when the higher-level conversation rendering is lossy or frontend-specific.

## Discovery Model

The future reporting interface should discover runs by walking the directory tree.

No global index file is required in this phase.

The reporting tool should recurse:

- `runs/<conversation>/`
- then each `agent/`
- then each `run-id/`
- then ingest `run.json` and `turns.jsonl`

This is intentionally simple and append-only.

## Timing Semantics

The benchmark's official timing metrics must exclude harness bookkeeping.

Measured benchmark duration should include only the agent execution window:

- start timing immediately before the first agent subprocess is launched
- stop timing immediately after the final agent subprocess exits

The following must be excluded from the primary benchmark timing:

- config loading
- run-directory creation
- workspace copying
- transcript writing
- `conversation.md` generation
- `turns.jsonl` generation
- `run.json` generation
- `summary.md` generation

If setup or bookkeeping durations are later recorded for diagnostics, they should be secondary metadata rather than the headline benchmark numbers.

## Write Order

For one run, the recommended artifact write flow is:

1. allocate `run-id`
2. create the run directory
3. execute the conversation
4. write per-turn transcript files
5. write `conversation.md`
6. write `turns.jsonl`
7. write `run.json`
8. write `summary.md`

This ordering ensures the structured artifacts can reference files that already exist.

If durability concerns become more important later, `turns.jsonl` and `run.json` may be moved earlier than the human-facing artifacts, but the directory model does not depend on that decision.

## Failure Model

The run directory should still exist even if the benchmark fails.

Each run should be represented as an immutable record with a clear status.

Suggested statuses:

- `completed`
- `failed`
- `partial`
- `harness_error`

Rules:

- if a turn fails, measured execution stops there
- completed turns remain recorded
- the failed turn should be recorded if any output or timing data exists
- later turns must not be fabricated
- already-written transcript files remain valid artifacts
- `run.json` should clearly identify the status and prompt counts

This allows the future reporting interface to aggregate failures and partial runs without special-case logic or guessing.

## Data Ownership Boundaries

The runner should own:

- producing raw transcripts
- producing compact run-level metrics
- producing compact turn-level metrics

The future reporting interface should own:

- aggregation across many runs
- trend analysis
- charts
- dashboards
- filtering and comparisons

This keeps the runner focused on capture and persistence rather than presentation logic that belongs in the reporting layer.

## Rationale

This design favors:

- append-only historical records
- easy filesystem discovery
- low ambiguity for downstream ingestion
- separation between human-facing and machine-facing artifacts

It avoids:

- overwriting previous runs
- scraping metrics out of Markdown
- bloated JSON files with embedded raw streams
- introducing a global manifest before it is needed

## Open Decisions Deferred

These are intentionally left for later implementation planning:

- whether `run.json` uses absolute or relative paths
- whether `workspace/` remains retained by default or becomes optional
- whether `conversation.md` should include stderr by default or only conditionally
- whether `turns.jsonl` is newline-delimited JSON text or a compact JSON array file

None of these block the core artifact model.
