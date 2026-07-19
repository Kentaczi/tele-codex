#!/usr/bin/env python3
"""Compatibility entry point for existing tele-codex installations."""

from tele_codex.config import (
    DEFAULT_CONFIG,
    DEFAULT_HTTP_TIMEOUT,
    TelegramConfig,
    http_timeout,
    load_config,
)
from tele_codex.messages import build_message, looks_like_question
from tele_codex.notifier import cli, is_diagnostic_invocation, main, parse_args
from tele_codex.telegram import MAX_TELEGRAM_TEXT, TelegramError, send_telegram

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_HTTP_TIMEOUT",
    "MAX_TELEGRAM_TEXT",
    "TelegramConfig",
    "TelegramError",
    "build_message",
    "cli",
    "http_timeout",
    "is_diagnostic_invocation",
    "load_config",
    "looks_like_question",
    "main",
    "parse_args",
    "send_telegram",
]


if __name__ == "__main__":
    raise SystemExit(cli())
