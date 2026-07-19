#!/usr/bin/env python3
"""Compatibility entry point for the Codex process wrapper."""

from tele_codex.codex_runner import cli, main

__all__ = ["cli", "main"]


if __name__ == "__main__":
    raise SystemExit(cli())
