from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from agent_bencher.models import SessionResult, TurnResult
from agent_bencher.report import build_markdown_report


def _write_turn_transcripts(*, output_dir: Path, turn: TurnResult, turn_index: int) -> None:
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stdout.txt"
    stderr_path = transcripts_dir / f"{turn_index:02d}-{turn.prompt_id}.stderr.txt"

    stdout_path.write_text(turn.stdout)
    stderr_path.write_text(turn.stderr)

    turn.stdout_path = str(stdout_path)
    turn.stderr_path = str(stderr_path)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _output_tps(*, output_tokens: int, duration_seconds: float) -> float:
    return _safe_divide(output_tokens, duration_seconds)


def _total_throughput_tps(*, input_tokens: int, output_tokens: int, duration_seconds: float) -> float:
    return _safe_divide(input_tokens + output_tokens, duration_seconds)


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
        "comment": session.comment,
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


def _extract_text_blocks(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []

    extracted: list[str] = []
    for item in value:
        if isinstance(item, str):
            extracted.append(item)
            continue
        if not isinstance(item, dict):
            continue

        if item.get("type") == "text" and isinstance(item.get("text"), str):
            extracted.append(item["text"])
            continue

        content = item.get("content")
        if isinstance(content, str):
            extracted.append(content)

    return extracted


def _extract_assistant_text_from_payload(payload: dict) -> list[str]:
    extracted: list[str] = []

    if payload.get("type") == "text":
        part = payload.get("part", {})
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            extracted.append(text.strip())

    message = payload.get("message")
    if payload.get("type") == "assistant" and isinstance(message, dict):
        extracted.extend(
            text.strip()
            for text in _extract_text_blocks(message.get("content"))
            if text.strip()
        )

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("text", "message", "content"):
            extracted.extend(
                text.strip()
                for text in _extract_text_blocks(result.get(key))
                if text.strip()
            )

    return extracted


def _extract_human_readable_stdout(stdout: str) -> str:
    stripped = stdout.strip()
    if not stripped:
        return ""

    extracted: list[str] = []

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        extracted.extend(_extract_assistant_text_from_payload(payload))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                extracted.extend(_extract_assistant_text_from_payload(item))
    else:
        parsed_any_json = False
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                line_payload = json.loads(line)
            except json.JSONDecodeError:
                return stripped
            if isinstance(line_payload, dict):
                parsed_any_json = True
                extracted.extend(_extract_assistant_text_from_payload(line_payload))
        if not parsed_any_json:
            return stripped

    if extracted:
        return "\n\n".join(extracted)

    return ""


def _parse_iso_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_wall_clock(value: str) -> str:
    parsed = _parse_iso_timestamp(value)
    if parsed is None:
        return value or "unknown"
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%fZ")


def _format_t_plus(*, reference: str, value: str) -> str:
    reference_dt = _parse_iso_timestamp(reference)
    value_dt = _parse_iso_timestamp(value)
    if reference_dt is None or value_dt is None:
        return "unknown"
    return f"T+{(value_dt - reference_dt).total_seconds():.2f}s"


def _extract_response_started_at(stdout: str) -> str:
    stripped = stdout.strip()
    if not stripped:
        return ""

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict) or item.get("type") != "assistant":
                continue
            timestamp = item.get("timestamp")
            if isinstance(timestamp, str) and timestamp:
                return timestamp
        return ""

    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            line_payload = json.loads(line)
        except json.JSONDecodeError:
            return ""
        if not isinstance(line_payload, dict) or line_payload.get("type") != "text":
            continue
        timestamp = line_payload.get("timestamp")
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(timestamp, str) and timestamp:
            return timestamp

    return ""


def _write_combined_conversation_artifact(*, output_dir: Path, session: SessionResult) -> Path:
    destination = output_dir / "conversation.md"
    lines = [
        f"# {session.conversation_name}",
        "",
        f"- agent: {session.agent_id}",
        f"- frontend: {session.frontend}",
        f"- backend model: {session.backend_model}",
        f"- session id: {session.session_id}",
        "",
    ]

    if session.comment:
        lines.extend(
            [
                f"User comment: {session.comment}",
                "",
            ]
        )

    for turn_index, turn in enumerate(session.turns, start=1):
        assistant_text = _extract_human_readable_stdout(turn.stdout)
        response_started_at = _extract_response_started_at(turn.stdout) or turn.ended_at
        prompt_time = f"{_format_wall_clock(turn.started_at)}, {_format_t_plus(reference=session.started_at, value=turn.started_at)}"
        response_begin_time = (
            f"{_format_wall_clock(response_started_at)}, "
            f"{_format_t_plus(reference=session.started_at, value=response_started_at)}"
        )
        response_end_time = f"{_format_wall_clock(turn.ended_at)}, {_format_t_plus(reference=session.started_at, value=turn.ended_at)}"
        lines.extend(
            [
                f"## Turn {turn_index}",
                "",
                f"### Prompt ({prompt_time})",
                turn.prompt_text,
                "",
                f"### Response ({response_begin_time})",
                assistant_text or "_No human-readable assistant text extracted._",
                "",
                f"_Response concluded at {response_end_time}_",
                "",
            ]
        )

        if turn.stderr:
            lines.extend(
                [
                    "### Stderr",
                    "```text",
                    turn.stderr,
                    "```",
                    "",
                ]
            )

    destination.write_text("\n".join(lines))
    return destination


def write_results(*, sessions: list[SessionResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        for turn_index, turn in enumerate(session.turns, start=1):
            _write_turn_transcripts(output_dir=output_dir, turn=turn, turn_index=turn_index)

        conversation_path = str(_write_combined_conversation_artifact(output_dir=output_dir, session=session))
        transcript_dir = str(output_dir / "transcripts")

        turns_destination = output_dir / "turns.jsonl"
        turns_destination.write_text(
            "\n".join(
                json.dumps(_serialize_turn(turn, run_id=session.run_id, turn_index=index))
                for index, turn in enumerate(session.turns, start=1)
            )
            + "\n"
        )

        run_destination = output_dir / "run.json"
        run_destination.write_text(
            json.dumps(_serialize_run(session, conversation_path=conversation_path, transcript_dir=transcript_dir), indent=2)
        )

    (output_dir / "summary.md").write_text(build_markdown_report(sessions))
