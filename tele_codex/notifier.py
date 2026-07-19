"""Command-line entry point for Codex hook and completion notifications."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_config
from .messages import build_message
from .telegram import send_telegram


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


def is_diagnostic_invocation(argv: list[str]) -> bool:
    """Return whether errors should be visible through a non-zero exit code."""
    return any(
        argument in {"--test", "--dry-run", "--process-exit"}
        or argument.startswith("--process-exit=")
        for argument in argv
    )


def cli(argv: list[str] | None = None) -> int:
    """Run the CLI, failing open only for callbacks invoked by Codex."""
    selected = list(sys.argv[1:] if argv is None else argv)
    try:
        return main(selected)
    except Exception as error:  # Notifications must never stop a Codex turn.
        print(f"tele-codex notification failed: {error}", file=sys.stderr)
        return 1 if is_diagnostic_invocation(selected) else 0
