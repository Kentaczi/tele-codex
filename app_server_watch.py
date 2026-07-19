#!/usr/bin/env python3
"""Compatibility entry point for the Codex App Server watcher."""

from tele_codex.app_server import ActiveTurn, StateTracker, cli, main, parse_args, watch

__all__ = ["ActiveTurn", "StateTracker", "cli", "main", "parse_args", "watch"]


if __name__ == "__main__":
    raise SystemExit(cli())
