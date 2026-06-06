from __future__ import annotations

from agent_bencher.models import SessionResult, TurnResult


def prompt_input_tokens(turn: TurnResult) -> int:
    return turn.token_usage.input + turn.token_usage.cache_read + turn.token_usage.cache_write


def total_prompt_input_tokens(session: SessionResult) -> int:
    return sum(prompt_input_tokens(turn) for turn in session.turns)
