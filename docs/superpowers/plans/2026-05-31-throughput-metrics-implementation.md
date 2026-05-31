# Throughput Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit lowest-common-denominator throughput metrics directly into `run.json` and `turns.jsonl` so future reporting code can ingest stable run- and turn-level TPS values without recomputing them.

**Architecture:** The runner already records the raw ingredients needed for throughput: end-to-end `duration_seconds` and token counts. This plan keeps the change localized to `results.py`, where run and turn artifacts are serialized, and adds focused tests that lock in both normal calculations and zero-duration behavior.

**Tech Stack:** Python 3.14, `dataclasses`, `json`, `pytest`

---

## File Structure

### Source files

- Modify: `src/agent_bencher/results.py`
  - Add small helpers for throughput calculation and include derived TPS fields in serialized run and turn artifacts.

### Tests

- Modify: `tests/test_results.py`
  - Assert the new per-turn and per-run throughput fields.
  - Add a zero-duration regression test so artifact writing never crashes or emits divide-by-zero errors.

## Task 1: Add Per-Turn And Per-Run Throughput Fields

**Files:**
- Modify: `tests/test_results.py`
- Modify: `src/agent_bencher/results.py`

- [ ] **Step 1: Write the failing artifact assertions**

Replace the assertions at the end of `test_write_results_emits_compact_run_json_and_turns_jsonl()` in `tests/test_results.py` with:

```python
    run_payload = json.loads((tmp_path / "run.json").read_text())
    turn_payloads = [
        json.loads(line)
        for line in (tmp_path / "turns.jsonl").read_text().strip().splitlines()
    ]

    assert run_payload["run_id"] == "2026-05-31T14-26-00"
    assert run_payload["total_input_tokens"] == 310
    assert run_payload["total_output_tokens"] == 120
    assert run_payload["effective_output_tps"] == 34.285714285714285
    assert run_payload["effective_total_throughput_tps"] == 122.85714285714286
    assert "stdout" not in run_payload

    assert len(turn_payloads) == 2
    assert turn_payloads[0]["output_tps"] == 33.333333333333336
    assert turn_payloads[0]["total_throughput_tps"] == 116.66666666666667
    assert turn_payloads[1]["output_tps"] == 34.78260869565218
    assert turn_payloads[1]["total_throughput_tps"] == 126.08695652173914
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev pytest tests/test_results.py::test_write_results_emits_compact_run_json_and_turns_jsonl -v
```

Expected: FAIL because `run.json` and `turns.jsonl` do not yet contain the derived throughput fields.

- [ ] **Step 3: Add a zero-duration regression test**

Append this test to `tests/test_results.py`:

```python
def test_write_results_uses_zero_throughput_for_zero_duration(tmp_path: Path) -> None:
    session = SessionResult(
        run_id="2026-05-31T14-26-00",
        conversation_name="sample-conversation",
        agent_id="zero-duration",
        frontend="opencode",
        backend_model="sample-model",
        session_id="session-123",
        started_at="2026-05-31T14:26:00Z",
        ended_at="2026-05-31T14:26:00Z",
        duration_seconds=0.0,
        status="completed",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="instant",
                prompt_text="Reply instantly",
                session_id="session-123",
                exit_code=0,
                duration_seconds=0.0,
                started_at="2026-05-31T14:26:00Z",
                ended_at="2026-05-31T14:26:00Z",
                stdout="assistant output",
                stderr="",
                token_usage=TokenUsage(input=10, output=4),
            ),
        ],
    )

    write_results(sessions=[session], output_dir=tmp_path)

    run_payload = json.loads((tmp_path / "run.json").read_text())
    turn_payload = json.loads((tmp_path / "turns.jsonl").read_text().strip())

    assert run_payload["effective_output_tps"] == 0.0
    assert run_payload["effective_total_throughput_tps"] == 0.0
    assert turn_payload["output_tps"] == 0.0
    assert turn_payload["total_throughput_tps"] == 0.0
```

- [ ] **Step 4: Run the zero-duration test to verify it fails**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev pytest tests/test_results.py::test_write_results_uses_zero_throughput_for_zero_duration -v
```

Expected: FAIL because the throughput fields do not exist yet.

- [ ] **Step 5: Add throughput helpers and serialize the new fields**

In `src/agent_bencher/results.py`, insert these helpers below `_write_turn_transcripts()`:

```python
def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _output_tps(*, output_tokens: int, duration_seconds: float) -> float:
    return _safe_divide(output_tokens, duration_seconds)


def _total_throughput_tps(*, input_tokens: int, output_tokens: int, duration_seconds: float) -> float:
    return _safe_divide(input_tokens + output_tokens, duration_seconds)
```

Then update `_serialize_turn()` to:

```python
def _serialize_turn(turn: TurnResult, *, run_id: str, turn_index: int) -> dict:
    return {
        "run_id": run_id,
        "turn_index": turn_index,
        "prompt_id": turn.prompt_id,
        "prompt_text": turn.prompt_text,
        "session_id": turn.session_id,
        "exit_code": turn.exit_code,
        "duration_seconds": turn.duration_seconds,
        "started_at": turn.started_at,
        "ended_at": turn.ended_at,
        "input_tokens": turn.token_usage.input,
        "output_tokens": turn.token_usage.output,
        "output_tps": _output_tps(
            output_tokens=turn.token_usage.output,
            duration_seconds=turn.duration_seconds,
        ),
        "total_throughput_tps": _total_throughput_tps(
            input_tokens=turn.token_usage.input,
            output_tokens=turn.token_usage.output,
            duration_seconds=turn.duration_seconds,
        ),
        "reasoning_tokens": turn.token_usage.reasoning,
        "cache_read_tokens": turn.token_usage.cache_read,
        "cache_write_tokens": turn.token_usage.cache_write,
        "stdout_path": turn.stdout_path,
        "stderr_path": turn.stderr_path,
        "warnings": list(turn.warnings),
    }
```

And update `_serialize_run()` to:

```python
def _serialize_run(session: SessionResult, *, conversation_path: str, transcript_dir: str) -> dict:
    total_input_tokens = sum(turn.token_usage.input for turn in session.turns)
    total_output_tokens = sum(turn.token_usage.output for turn in session.turns)
    total_reasoning_tokens = sum(turn.token_usage.reasoning for turn in session.turns)
    total_cache_read_tokens = sum(turn.token_usage.cache_read for turn in session.turns)
    total_cache_write_tokens = sum(turn.token_usage.cache_write for turn in session.turns)

    return {
        "run_id": session.run_id,
        "conversation_name": session.conversation_name,
        "agent_id": session.agent_id,
        "frontend": session.frontend,
        "backend_model": session.backend_model,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "duration_seconds": session.duration_seconds,
        "prompts_attempted": session.prompts_attempted,
        "prompts_completed": session.prompts_completed,
        "session_id": session.session_id,
        "status": session.status,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "effective_output_tps": _output_tps(
            output_tokens=total_output_tokens,
            duration_seconds=session.duration_seconds,
        ),
        "effective_total_throughput_tps": _total_throughput_tps(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            duration_seconds=session.duration_seconds,
        ),
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
        "total_cache_write_tokens": total_cache_write_tokens,
        "conversation_path": conversation_path,
        "transcript_dir": transcript_dir,
    }
```

- [ ] **Step 6: Run the result tests**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev pytest tests/test_results.py -v
```

Expected: PASS

- [ ] **Step 7: Run the full suite**

Run:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev pytest -v
```

Expected: PASS with all tests green.

- [ ] **Step 8: Commit the throughput artifact slice**

Suggested commit text for the user:

```text
feat: emit throughput metrics in benchmark artifacts
Add per-turn and per-run TPS fields to turns.jsonl and run.json using full end-to-end duration so reporting tools can ingest stable cross-frontend throughput numbers directly.
```

## Self-Review Coverage

- Spec coverage:
  - per-turn `output_tps`: Task 1
  - per-turn `total_throughput_tps`: Task 1
  - per-run `effective_output_tps`: Task 1
  - per-run `effective_total_throughput_tps`: Task 1
  - zero-duration behavior: Task 1

- Placeholder scan:
  - No TODO/TBD markers
  - All commands and assertions are concrete

- Type consistency:
  - Uses existing `TurnResult`, `SessionResult`, and `TokenUsage` names
  - Keeps metric names aligned with the throughput spec
