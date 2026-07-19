"""Run Codex CLI and report abnormal process exits."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .config import load_config
from .messages import build_message
from .telegram import send_telegram


def main(argv: list[str] | None = None) -> int:
    """Run Codex with the supplied arguments and preserve its exit status."""
    selected = list(sys.argv[1:] if argv is None else argv)
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin:
        print("codex executable not found", file=sys.stderr)
        return 127

    try:
        result = subprocess.run([codex_bin, *selected], check=False)
    except KeyboardInterrupt:
        return 130

    if result.returncode != 0:
        message = build_message(
            {"exit_code": result.returncode, "cwd": os.getcwd()}, "process-exit"
        )
        if message:
            try:
                send_telegram(message, load_config())
            except Exception as error:
                print(f"tele-codex notification failed: {error}", file=sys.stderr)

    return result.returncode


def cli() -> int:
    """Console-script adapter."""
    return main()
