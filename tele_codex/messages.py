"""Translate Codex lifecycle payloads into human-readable messages."""

from __future__ import annotations

from typing import Any

from .telegram import MAX_TELEGRAM_TEXT


def looks_like_question(text: str) -> bool:
    """Conservatively classify a completed turn as needing a reply."""
    tail = text.strip()[-1200:].lower()
    phrases = (
        "need your input",
        "need your confirmation",
        "please choose",
        "please confirm",
        "which option",
        "would you like",
        "tell me which",
        "waiting for your",
        "what should i",
        "how would you like",
    )
    return tail.endswith("?") or any(phrase in tail for phrase in phrases)


def _question_text(tool_input: dict[str, Any]) -> str:
    questions = tool_input.get("questions") or []
    return "\n".join(
        str(question.get("question", "")).strip()
        for question in questions
        if isinstance(question, dict) and question.get("question")
    )


def build_message(payload: dict[str, Any], source: str) -> str | None:
    """Translate a Codex notification or hook payload into Telegram text."""
    cwd = str(payload.get("cwd") or "")

    if source == "notify":
        if payload.get("type") != "agent-turn-complete":
            return None
        detail = str(payload.get("last-assistant-message") or "Turn complete.")
        title = (
            "🟠 Codex needs your response"
            if looks_like_question(detail)
            else "✅ Codex finished"
        )
    elif source == "hook":
        event = payload.get("hook_event_name")
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        if event == "PermissionRequest":
            title = "🔐 Codex needs approval"
            detail = str(
                tool_input.get("description") or f"Tool: {tool_name or 'unknown'}"
            )
        elif event == "PreToolUse" and tool_name == "request_user_input":
            title = "🟠 Codex needs your response"
            detail = _question_text(tool_input) or "Codex requested input."
        else:
            return None
    elif source == "process-exit":
        code = payload.get("exit_code", "unknown")
        title = "🔴 Codex stopped"
        detail = f"The Codex process exited with status {code}."
    else:
        return None

    location = f"\n{cwd}" if cwd else ""
    return f"{title}{location}\n\n{detail}"[:MAX_TELEGRAM_TEXT]
