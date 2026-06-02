from __future__ import annotations

import math

from agent_bencher.models import BatchResult, MetricSummary, SessionResult


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _summarize(values: list[float]) -> MetricSummary:
    if not values:
        return MetricSummary(mean=0.0, min=0.0, max=0.0, stddev=0.0)
    if len(values) == 1:
        return MetricSummary(mean=values[0], min=values[0], max=values[0], stddev=0.0)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return MetricSummary(mean=mean, min=min(values), max=max(values), stddev=math.sqrt(variance))


def _total_input_tokens(session: SessionResult) -> int:
    return sum(turn.token_usage.input for turn in session.turns)


def _total_output_tokens(session: SessionResult) -> int:
    return sum(turn.token_usage.output for turn in session.turns)


def _effective_output_tps(session: SessionResult) -> float:
    return _safe_divide(_total_output_tokens(session), session.duration_seconds)


def _effective_total_throughput_tps(session: SessionResult) -> float:
    return _safe_divide(_total_input_tokens(session) + _total_output_tokens(session), session.duration_seconds)


def build_batch_result(*, batch_id: str, requested_runs: int, comment: str, sessions: list[SessionResult]) -> BatchResult:
    if not sessions:
        raise ValueError("batch requires at least one session")

    successful = [session for session in sessions if session.status == "completed"]
    failed = [session for session in sessions if session.status != "completed"]
    first = sessions[0]

    run_metrics = {
        "duration_seconds": _summarize([session.duration_seconds for session in successful]),
        "total_input_tokens": _summarize([float(_total_input_tokens(session)) for session in successful]),
        "total_output_tokens": _summarize([float(_total_output_tokens(session)) for session in successful]),
        "effective_output_tps": _summarize([_effective_output_tps(session) for session in successful]),
        "effective_total_throughput_tps": _summarize([_effective_total_throughput_tps(session) for session in successful]),
    }

    turn_metrics: list[dict[str, MetricSummary]] = []
    if successful:
        turn_count = len(successful[0].turns)
        for turn_index in range(turn_count):
            turns = [session.turns[turn_index] for session in successful]
            turn_metrics.append(
                {
                    "duration_seconds": _summarize([turn.duration_seconds for turn in turns]),
                    "input_tokens": _summarize([float(turn.token_usage.input) for turn in turns]),
                    "output_tokens": _summarize([float(turn.token_usage.output) for turn in turns]),
                    "output_tps": _summarize(
                        [_safe_divide(turn.token_usage.output, turn.duration_seconds) for turn in turns]
                    ),
                    "total_throughput_tps": _summarize(
                        [
                            _safe_divide(turn.token_usage.input + turn.token_usage.output, turn.duration_seconds)
                            for turn in turns
                        ]
                    ),
                }
            )

    if len(successful) == requested_runs:
        status = "completed"
    elif successful:
        status = "partial"
    else:
        status = "failed"

    return BatchResult(
        batch_id=batch_id,
        conversation_name=first.conversation_name,
        agent_id=first.agent_id,
        frontend=first.frontend,
        backend_model=first.backend_model,
        comment=comment,
        requested_runs=requested_runs,
        successful_runs=len(successful),
        failed_runs=len(failed),
        started_at=sessions[0].started_at,
        ended_at=sessions[-1].ended_at,
        duration_seconds=sum(session.duration_seconds for session in sessions),
        status=status,
        sessions=sessions,
        run_metrics=run_metrics,
        turn_metrics=turn_metrics,
    )
