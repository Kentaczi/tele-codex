"""Small standard-library client for Telegram's Bot API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import TelegramConfig, http_timeout

MAX_TELEGRAM_TEXT = 4000


class TelegramError(RuntimeError):
    """A Telegram request completed without a usable success response."""


def _credentials(
    config: TelegramConfig | Mapping[str, str],
) -> tuple[str, str]:
    if isinstance(config, TelegramConfig):
        return config.bot_token, config.chat_id
    return config["bot_token"], config["chat_id"]


def send_telegram(
    text: str,
    config: TelegramConfig | Mapping[str, str],
    *,
    timeout: float | None = None,
) -> None:
    """Send a plain-text message using Telegram's ``sendMessage`` method."""
    selected_timeout = http_timeout() if timeout is None else timeout
    if selected_timeout <= 0:
        raise ValueError("Telegram request timeout must be greater than zero")

    bot_token, chat_id = _credentials(config)
    body = urlencode(
        {
            "chat_id": chat_id,
            "text": text[:MAX_TELEGRAM_TEXT],
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=body,
        method="POST",
    )

    try:
        with urlopen(request, timeout=selected_timeout) as response:
            raw_response = response.read()
    except HTTPError as error:
        raise TelegramError(f"Telegram returned HTTP {error.code}") from error
    except URLError as error:
        reason = getattr(error, "reason", "network error")
        raise TelegramError(f"Telegram connection failed: {reason}") from error
    except TimeoutError as error:
        raise TelegramError("Telegram connection timed out") from error

    try:
        result = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TelegramError("Telegram returned invalid JSON") from error

    if not isinstance(result, dict) or result.get("ok") is not True:
        description = (
            str(result.get("description") or "unknown API error")
            if isinstance(result, dict)
            else "unexpected API response"
        )
        raise TelegramError(f"Telegram rejected the message: {description}")
