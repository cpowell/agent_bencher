from agent_bencher.batch import build_batch_result
from agent_bencher.models import SessionResult, TokenUsage, TurnResult


def make_session(*, run_id: str, status: str, duration: float, input_tokens: int, output_tokens: int) -> SessionResult:
    return SessionResult(
        run_id=run_id,
        conversation_name="sample",
        agent_id="open-fast",
        frontend="opencode",
        backend_model="model-x",
        session_id=f"session-{run_id}",
        started_at="2026-06-01T00:00:00Z",
        ended_at="2026-06-01T00:00:01Z",
        duration_seconds=duration,
        status=status,
        prompts_attempted=1,
        prompts_completed=1 if status == "completed" else 0,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id=f"session-{run_id}",
                exit_code=0 if status == "completed" else 1,
                duration_seconds=duration,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=input_tokens, output=output_tokens),
            )
        ],
        comment="",
    )


def test_build_batch_result_aggregates_successful_trials_only() -> None:
    batch = build_batch_result(
        batch_id="2026-06-01T12-00-00",
        requested_runs=3,
        comment="",
        sessions=[
            make_session(run_id="r1", status="completed", duration=10.0, input_tokens=100, output_tokens=50),
            make_session(run_id="r2", status="failed", duration=20.0, input_tokens=999, output_tokens=1),
            make_session(run_id="r3", status="completed", duration=14.0, input_tokens=140, output_tokens=70),
        ],
    )

    assert batch.status == "partial"
    assert batch.successful_runs == 2
    assert batch.failed_runs == 1
    assert batch.run_metrics["duration_seconds"].mean == 12.0
    assert batch.run_metrics["total_input_tokens"].min == 100
    assert batch.run_metrics["total_input_tokens"].max == 140
    assert batch.turn_metrics[0]["input_tokens"].mean == 120.0


def test_build_batch_result_uses_zero_stddev_for_single_success() -> None:
    batch = build_batch_result(
        batch_id="2026-06-01T12-00-00",
        requested_runs=2,
        comment="",
        sessions=[
            make_session(run_id="r1", status="completed", duration=10.0, input_tokens=100, output_tokens=50),
            make_session(run_id="r2", status="failed", duration=20.0, input_tokens=999, output_tokens=1),
        ],
    )

    assert batch.run_metrics["duration_seconds"].stddev == 0.0
    assert batch.turn_metrics[0]["output_tokens"].stddev == 0.0


def test_build_batch_result_counts_cached_prompt_tokens_in_input_metrics() -> None:
    session = SessionResult(
        run_id="r1",
        conversation_name="sample",
        agent_id="claude-cached",
        frontend="claude",
        backend_model="model-x",
        session_id="session-r1",
        started_at="2026-06-01T00:00:00Z",
        ended_at="2026-06-01T00:00:10Z",
        duration_seconds=10.0,
        status="completed",
        prompts_attempted=1,
        prompts_completed=1,
        turns=[
            TurnResult(
                prompt_id="01",
                prompt_text="Do this",
                session_id="session-r1",
                exit_code=0,
                duration_seconds=10.0,
                stdout="{}",
                stderr="",
                token_usage=TokenUsage(input=0, output=40, cache_read=1000, cache_write=200),
            )
        ],
        comment="",
    )

    batch = build_batch_result(batch_id="2026-06-01T12-00-00", requested_runs=1, comment="", sessions=[session])

    assert batch.run_metrics["total_input_tokens"].mean == 1200.0
    assert batch.turn_metrics[0]["input_tokens"].mean == 1200.0
    assert batch.run_metrics["effective_total_throughput_tps"].mean == 124.0
    assert batch.turn_metrics[0]["total_throughput_tps"].mean == 124.0
