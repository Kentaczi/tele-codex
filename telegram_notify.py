#!/usr/bin/env python3
"""Send Codex lifecycle notifications to Telegram using only the stdlib."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_CONFIG = Path.home() / ".codex" / "telegram.json"
MAX_TELEGRAM_TEXT = 4000


def load_config(path: Path | None = None) -> dict[str, str]:
    """Load credentials from the environment or a private JSON file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if token and chat_id:
        return {"bot_token": token, "chat_id": chat_id}

    selected = path or Path(
        os.environ.get("CODEX_TELEGRAM_CONFIG", str(DEFAULT_CONFIG))
    ).expanduser()
    config = json.loads(selected.read_text(encoding="utf-8"))

    missing = [key for key in ("bot_token", "chat_id") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing configuration value(s): {', '.join(missing)}")

    return {
        "bot_token": str(config["bot_token"]),
        "chat_id": str(config["chat_id"]),
    }


def send_telegram(text: str, config: dict[str, str]) -> None:
    """Call Telegram's sendMessage Bot API method."""
    body = urlencode(
        {
            "chat_id": config["chat_id"],
            "text": text[:MAX_TELEGRAM_TEXT],
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(
        "https://api.telegram.org/"
        f"bot{config['bot_token']}/sendMessage",
        data=body,
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        response.read()


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
    detail = ""

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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "payload",
        nargs="?",
        help="Codex notify JSON payload. Hooks instead provide JSON on stdin.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Credentials file (default: ~/.codex/telegram.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated message without contacting Telegram.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test message to the configured Telegram chat.",
    )
    parser.add_argument(
        "--process-exit",
        type=int,
        metavar="CODE",
        help="Send an abnormal Codex process-exit notification.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.test:
        message = "✅ tele-codex test notification"
    elif args.process_exit is not None:
        message = build_message(
            {"exit_code": args.process_exit, "cwd": os.getcwd()}, "process-exit"
        )
    elif args.payload:
        message = build_message(json.loads(args.payload), "notify")
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            raise ValueError("Expected a notify JSON argument or hook JSON on stdin")
        message = build_message(json.loads(raw), "hook")

    if message is None:
        return 0
    if args.dry_run:
        print(message)
        return 0

    send_telegram(message, load_config(args.config))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # Notifications must never stop a Codex turn.
        print(f"tele-codex notification failed: {error}", file=sys.stderr)
        raise SystemExit(0)

