"""Credential and runtime configuration for Telegram notifications."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".codex" / "telegram.json"
DEFAULT_HTTP_TIMEOUT = 5.0


@dataclass(frozen=True)
class TelegramConfig:
    """Credentials required by the Telegram Bot API."""

    bot_token: str
    chat_id: str


def load_config(path: Path | None = None) -> TelegramConfig:
    """Load credentials from the environment or a private JSON file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if bool(token) != bool(chat_id):
        raise ValueError(
            "Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or unset both"
        )
    if token and chat_id:
        return TelegramConfig(bot_token=token, chat_id=chat_id)

    selected = path or Path(
        os.environ.get("CODEX_TELEGRAM_CONFIG", str(DEFAULT_CONFIG))
    ).expanduser()
    config = json.loads(selected.read_text(encoding="utf-8"))

    missing = [key for key in ("bot_token", "chat_id") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing configuration value(s): {', '.join(missing)}")

    return TelegramConfig(
        bot_token=str(config["bot_token"]),
        chat_id=str(config["chat_id"]),
    )


def http_timeout() -> float:
    """Return a positive request timeout, leaving margin for hook runners."""
    value = float(os.environ.get("TELEGRAM_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT))
    if value <= 0:
        raise ValueError("TELEGRAM_HTTP_TIMEOUT must be greater than zero")
    return value
