#!/usr/bin/env python3
"""Run Codex CLI and notify Telegram if the process exits abnormally."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from telegram_notify import build_message, load_config, send_telegram


def main() -> int:
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin:
        print("codex executable not found", file=sys.stderr)
        return 127

    try:
        result = subprocess.run([codex_bin, *sys.argv[1:]], check=False)
        code = result.returncode
    except KeyboardInterrupt:
        return 130

    if code != 0:
        message = build_message(
            {"exit_code": code, "cwd": os.getcwd()}, "process-exit"
        )
        if message:
            try:
                send_telegram(message, load_config())
            except Exception as error:
                print(f"tele-codex notification failed: {error}", file=sys.stderr)

    return code


if __name__ == "__main__":
    raise SystemExit(main())

