from __future__ import annotations

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


def _extract_text_from_content_block(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        extracted: list[str] = []
        for item in value:
            if isinstance(item, str):
                extracted.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    extracted.append(item["text"])
                elif isinstance(item.get("content"), str):
                    extracted.append(item["content"])
        return extracted
    return []


def _extract_human_readable_stdout(stdout: str) -> str:
    stripped = stdout.strip()
    if not stripped:
        return ""

    lines = [line for line in stdout.splitlines() if line.strip()]
    extracted: list[str] = []
    parsed_any_json = False

    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return stripped

        parsed_any_json = True
        if not isinstance(payload, dict):
            continue

        if payload.get("type") == "text":
            part = payload.get("part", {})
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                extracted.append(text.strip())
                continue

        result = payload.get("result", payload)
        if isinstance(result, dict):
            for key in ("text", "message", "content"):
                extracted.extend(
                    text.strip()
                    for text in _extract_text_from_content_block(result.get(key))
                    if text.strip()
                )

    if extracted:
        return "\n\n".join(extracted)

    if parsed_any_json:
        return ""

    return stripped


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

    for turn_index, turn in enumerate(session.turns, start=1):
        assistant_text = _extract_human_readable_stdout(turn.stdout)
        lines.extend(
            [
                f"## Turn {turn_index}: {turn.prompt_id}",
                "",
                "### Prompt",
                turn.prompt_text,
                "",
                "### Response",
                assistant_text or "_No human-readable assistant text extracted._",
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


def _serialize_turn(turn: TurnResult) -> dict:
    return {
        "prompt_id": turn.prompt_id,
        "prompt_text": turn.prompt_text,
        "session_id": turn.session_id,
        "exit_code": turn.exit_code,
        "duration_seconds": turn.duration_seconds,
        "token_usage": {
            "input": turn.token_usage.input,
            "output": turn.token_usage.output,
            "reasoning": turn.token_usage.reasoning,
            "cache_read": turn.token_usage.cache_read,
            "cache_write": turn.token_usage.cache_write,
        },
        "stdout_path": turn.stdout_path,
        "stderr_path": turn.stderr_path,
        "warnings": list(turn.warnings),
    }


def _serialize_session(session: SessionResult, *, conversation_path: str) -> dict:
    return {
        "conversation_name": session.conversation_name,
        "agent_id": session.agent_id,
        "frontend": session.frontend,
        "backend_model": session.backend_model,
        "session_id": session.session_id,
        "prompts_attempted": session.prompts_attempted,
        "prompts_completed": session.prompts_completed,
        "conversation_path": conversation_path,
        "turns": [_serialize_turn(turn) for turn in session.turns],
    }


def write_results(*, sessions: list[SessionResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = output_dir / "json"
    raw_dir.mkdir(exist_ok=True)

    for session in sessions:
        for turn_index, turn in enumerate(session.turns, start=1):
            _write_turn_transcripts(output_dir=output_dir, turn=turn, turn_index=turn_index)

        conversation_path = str(_write_combined_conversation_artifact(output_dir=output_dir, session=session))
        destination = raw_dir / f"{session.agent_id}.json"
        destination.write_text(json.dumps(_serialize_session(session, conversation_path=conversation_path), indent=2))

    (output_dir / "summary.md").write_text(build_markdown_report(sessions))
