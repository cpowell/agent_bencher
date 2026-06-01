# Repeated Benchmark Runs Design

## Goal

Add a `--runs` parameter to `agent-bencher bench` so one CLI invocation can execute the same benchmark configuration multiple times and produce a single batch-oriented artifact set with statistical summaries across successful trials.

## Scope

This design covers repeated execution of one `(run config, conversation)` pair in a single `bench` invocation. It does not add cross-config suites, parallel execution, run selection heuristics, or cache-aware scheduling.

## User Experience

The CLI remains:

```bash
agent-bencher bench <run-config> <conversation> [--comment "..."] [--output-dir runs] [--runs N]
```

`--runs` defaults to `1` when absent. The semantic meaning of `--runs N` is "execute the exact same benchmark N times as repeated trials."

The primary goal of repeated trials is statistical stability, not selecting a best run. The tool should therefore aggregate metrics across successful trials and report variability rather than highlighting a winner.

## Execution Model

The implementation should preserve the current single-conversation, single-session turn loop as a distinct unit and add a batch orchestration layer above it.

There are two execution layers:

1. A single-trial executor that prepares one isolated workspace, runs one conversation against one agent config, and returns one `SessionResult`.
2. A batch executor that invokes the single-trial executor `N` times serially, collects all trial results, computes aggregate statistics from successful trials, and writes batch-level artifacts.

Trials run serially within one CLI invocation. This feature does not introduce concurrency.

The batch executor should continue after individual trial failures. It should stop only for a top-level configuration or runtime error that prevents further trials from starting at all.

## Output Layout

Each `bench` invocation produces a batch directory, even when `--runs 1`.

Proposed layout:

```text
runs/<conversation>/<agent>/<batch-id>/
  batch.json
  summary.md
  trials/
    trial-001/
      run.json
      turns.jsonl
      conversation.md
      transcripts/
    trial-002/
      ...
```

The batch directory is the primary artifact root for the invocation. Trial directories are nested underneath it and retain the existing per-run artifacts for debugging and inspection.

This means the current top-level per-run directory shape is replaced by a batch-first shape. The compatibility rule is behavioral rather than structural: `--runs 1` still means "run once," but the output is now nested under a batch directory.

## Batch Identity

Each invocation gets a `batch_id`, analogous to the current `run_id`, derived from the invocation timestamp. Each nested trial gets its own `run_id` so existing run-level artifacts remain uniquely identifiable.

The batch metadata should include:

- `batch_id`
- conversation name
- agent ID
- frontend
- backend model
- requested run count
- successful run count
- failed run count
- overall batch status
- user comment
- started/ended timestamps

## Data Model

Keep the existing `SessionResult` as the representation of one trial. Introduce a separate batch result model instead of overloading `SessionResult`.

The batch result should contain:

- invocation metadata
- ordered list of trial `SessionResult`s
- aggregate run-level statistics over successful trials
- aggregate per-turn statistics over successful trials
- compact references to failed trials and their statuses

This separation keeps current run-level serialization logic reusable and avoids breaking code that assumes one session equals one run.

## Aggregation Semantics

The aggregate should be based only on successful trials.

### Successful Trial Definition

A successful trial is a `SessionResult` whose status is `completed`.

Trials with `partial` or `failed` status are excluded from aggregate metric calculations, but must still appear in the batch summary with trial identifiers and status.

### Run-Level Metrics

The aggregate should treat these as first-class run-level metrics:

- duration seconds
- total input tokens
- total output tokens
- effective output TPS
- effective total throughput TPS

For each metric, compute:

- mean
- min
- max
- standard deviation

If exactly one successful trial exists, standard deviation should be emitted as `0.0` rather than omitted.

### Per-Turn Metrics

Per-turn aggregates should be computed by turn index across successful trials only.

For each turn index, aggregate:

- duration seconds
- input tokens
- output tokens
- output TPS
- total throughput TPS

For each per-turn metric, compute:

- mean
- min
- max
- standard deviation

This lets users see whether variance is concentrated in particular prompts rather than only at the whole-run level.

## Failure Handling

The batch should still write artifacts when some trials fail.

Batch status should follow these rules:

- `completed`: all requested trials succeeded
- `partial`: at least one trial succeeded and at least one trial failed
- `failed`: no trial succeeded, or the batch aborted before any meaningful successful execution

Failed trials should still produce their own trial directories and as many per-run artifacts as the existing single-run path can safely write.

The aggregate summary should clearly separate:

- requested trial count
- successful trial count
- failed trial count
- failed trial identifiers and statuses

## Reporting

The batch `summary.md` should become the default human-facing entry point.

It should include:

- batch metadata
- requested/successful/failed counts
- aggregate run-level metrics table
- per-turn aggregate metrics table
- explicit list of failed trials
- links or relative paths to each nested trial directory

The batch JSON artifact should contain the machine-readable equivalent of the same information, including enough detail to rebuild the markdown report.

Trial-level `summary.md` files are optional. The existing `run.json`, `turns.jsonl`, `conversation.md`, and transcript artifacts remain required for each trial.

## Compatibility And Migration

This feature intentionally changes artifact layout by introducing a batch directory for every `bench` invocation, including `--runs 1`.

Code should be reorganized so there are clear responsibilities for:

- running one trial
- writing one trial's artifacts
- aggregating a batch
- writing one batch's artifacts

That split keeps the one-run and many-run cases on the same code path and reduces duplication.

## Testing Strategy

The implementation should be verified with automated tests covering:

- CLI parsing with default `--runs=1`
- CLI parsing with explicit `--runs N`
- batch executor invoking the single-trial executor the correct number of times
- aggregate stats over multiple successful trials
- exclusion of failed trials from aggregates
- batch status rules for all-success, mixed success/failure, and all-failed cases
- per-turn aggregate calculations by turn index
- output directory layout under a batch root
- `stddev=0.0` behavior when exactly one successful trial exists

## Non-Goals

This design does not include:

- parallel trial execution
- percentile reporting
- best-run or median-run selection
- retry logic
- deduplication or caching across trials
- multi-config suite orchestration
