"""Watch a Codex App Server JSONL stream and notify on lifecycle changes."""

from __future__ import annotations

import argparse
import json
import select
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TextIO

from .config import load_config
from .telegram import send_telegram

INPUT_METHODS = {
    "item/tool/requestUserInput",
    "tool/requestUserInput",
}
APPROVAL_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
    "item/permissions/requestApproval",
    "mcpServer/elicitation/request",
}
ACTIVITY_PREFIXES = ("item/", "turn/", "hook/")


def _params(message: dict[str, Any]) -> dict[str, Any]:
    value = message.get("params") or {}
    return value if isinstance(value, dict) else {}


def _turn_id(message: dict[str, Any]) -> str | None:
    params = _params(message)
    turn = params.get("turn") or {}
    if not isinstance(turn, dict):
        turn = {}
    value = params.get("turnId") or params.get("turn_id") or turn.get("id")
    return str(value) if value else None


def _question_detail(params: dict[str, Any]) -> str:
    questions = params.get("questions") or []
    if not questions and isinstance(params.get("request"), dict):
        questions = params["request"].get("questions") or []
    text = "\n".join(
        str(question.get("question", "")).strip()
        for question in questions
        if isinstance(question, dict) and question.get("question")
    )
    return text or "Codex requested input."


def _approval_detail(method: str, params: dict[str, Any]) -> str:
    reason = params.get("reason") or params.get("message")
    if not reason and isinstance(params.get("request"), dict):
        reason = params["request"].get("message")
    category = method.rsplit("/", 2)[-2] if "/" in method else method
    return str(reason or f"Approval category: {category}")


@dataclass
class ActiveTurn:
    last_activity: float
    stalled: bool = False


class StateTracker:
    """Convert App Server lifecycle messages into notification text."""

    def __init__(self, stall_seconds: float = 900) -> None:
        self.stall_seconds = stall_seconds
        self.active: dict[str, ActiveTurn] = {}

    def handle(self, message: dict[str, Any], now: float) -> list[str]:
        method = str(message.get("method") or "")
        params = _params(message)
        turn_id = _turn_id(message)
        notifications: list[str] = []

        if method == "turn/started" and turn_id:
            self.active[turn_id] = ActiveTurn(now)
            return notifications

        if method in INPUT_METHODS:
            notifications.append(
                f"🟠 Codex needs your response\n\n{_question_detail(params)}"
            )
        elif method in APPROVAL_METHODS:
            notifications.append(
                f"🔐 Codex needs approval\n\n{_approval_detail(method, params)}"
            )
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            if not isinstance(turn, dict):
                turn = {}
            status = str(turn.get("status") or params.get("status") or "completed")
            if status == "completed":
                notifications.append("✅ Codex finished\n\nTurn completed successfully.")
            elif status == "interrupted":
                notifications.append(
                    "🟡 Codex interrupted\n\nThe active turn was interrupted."
                )
            else:
                error = turn.get("error") or params.get("error") or {}
                if not isinstance(error, dict):
                    error = {}
                detail = str(error.get("message") or "The active turn failed.")
                notifications.append(f"🔴 Codex failed\n\n{detail}")
            if turn_id:
                self.active.pop(turn_id, None)
            return notifications

        if turn_id and turn_id in self.active and method.startswith(ACTIVITY_PREFIXES):
            self.active[turn_id] = ActiveTurn(now)

        return notifications

    def check_stalls(self, now: float) -> list[str]:
        if self.stall_seconds <= 0:
            return []
        notifications: list[str] = []
        for turn_id, state in self.active.items():
            idle = now - state.last_activity
            if idle >= self.stall_seconds and not state.stalled:
                state.stalled = True
                notifications.append(
                    "⚠️ Codex may be stalled\n\n"
                    f"No App Server activity for {int(idle)} seconds "
                    f"(turn {turn_id})."
                )
        return notifications


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stall-seconds",
        type=float,
        default=900,
        help="Notify after this many seconds without turn activity; 0 disables.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print notifications instead of contacting Telegram.",
    )
    return parser.parse_args(argv)


def watch(
    stream: TextIO,
    tracker: StateTracker,
    deliver: Callable[[str], None],
    *,
    poll_seconds: float = 1,
) -> int:
    """Consume live JSONL while periodically evaluating inactivity."""
    while True:
        ready, _, _ = select.select([stream], [], [], poll_seconds)
        if ready:
            line = stream.readline()
            if line == "":
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                print(f"Ignoring invalid App Server JSON: {error}", file=sys.stderr)
                continue
            if not isinstance(message, dict):
                continue
            for notification in tracker.handle(message, time.monotonic()):
                deliver(notification)
        for notification in tracker.check_stalls(time.monotonic()):
            deliver(notification)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.stall_seconds < 0:
        raise ValueError("--stall-seconds must be zero or greater")

    if args.dry_run:
        deliver = print
    else:
        config = load_config()

        def deliver(message: str) -> None:
            try:
                send_telegram(message, config)
            except Exception as error:
                print(f"tele-codex notification failed: {error}", file=sys.stderr)

    return watch(sys.stdin, StateTracker(args.stall_seconds), deliver)


def cli(argv: list[str] | None = None) -> int:
    """Run the watcher and report configuration or stream failures."""
    try:
        return main(argv)
    except Exception as error:
        print(f"tele-codex watcher failed: {error}", file=sys.stderr)
        return 1
