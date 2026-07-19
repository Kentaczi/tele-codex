import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs

from tele_codex.config import TelegramConfig, load_config
from tele_codex.messages import build_message, looks_like_question
from tele_codex.notifier import cli
from tele_codex.telegram import MAX_TELEGRAM_TEXT, TelegramError, send_telegram


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class QuestionClassificationTests(unittest.TestCase):
    def test_question_mark_needs_response(self):
        self.assertTrue(looks_like_question("Which option should I use?"))

    def test_confirmation_phrase_needs_response(self):
        self.assertTrue(looks_like_question("I need your confirmation before continuing."))

    def test_completed_statement_is_finished(self):
        self.assertFalse(looks_like_question("Implemented and verified all tests."))


class ConfigTests(unittest.TestCase):
    def test_environment_credentials(self):
        with patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "42"},
            clear=True,
        ):
            self.assertEqual(load_config(), TelegramConfig("token", "42"))

    def test_partial_environment_credentials_fail(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Set both"):
                load_config()

    def test_missing_file_value_fails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "telegram.json"
            path.write_text('{"bot_token": "token"}', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "chat_id"):
                    load_config(path)


class TelegramTransportTests(unittest.TestCase):
    CONFIG = {"bot_token": "secret-token", "chat_id": "123"}

    @patch("tele_codex.telegram.urlopen")
    def test_encodes_send_message_request(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(b'{"ok": true, "result": {}}')

        send_telegram("hello & goodbye", self.CONFIG, timeout=3)

        request = mocked_urlopen.call_args.args[0]
        timeout = mocked_urlopen.call_args.kwargs["timeout"]
        body = parse_qs(request.data.decode("utf-8"))
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/sendMessage"))
        self.assertEqual(body["chat_id"], ["123"])
        self.assertEqual(body["text"], ["hello & goodbye"])
        self.assertEqual(timeout, 3)

    @patch("tele_codex.telegram.urlopen")
    def test_rejected_api_response_fails(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(
            b'{"ok": false, "description": "chat not found"}'
        )
        with self.assertRaisesRegex(TelegramError, "chat not found"):
            send_telegram("hello", self.CONFIG)

    @patch("tele_codex.telegram.urlopen")
    def test_invalid_json_fails(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(b"not-json")
        with self.assertRaisesRegex(TelegramError, "invalid JSON"):
            send_telegram("hello", self.CONFIG)

    @patch("tele_codex.telegram.urlopen", side_effect=URLError("offline"))
    def test_network_error_is_sanitized(self, _mocked_urlopen):
        with self.assertRaisesRegex(TelegramError, "offline") as raised:
            send_telegram("hello", self.CONFIG)
        self.assertNotIn("secret-token", str(raised.exception))

    @patch("tele_codex.telegram.urlopen", side_effect=TimeoutError())
    def test_timeout_has_actionable_error(self, _mocked_urlopen):
        with self.assertRaisesRegex(TelegramError, "timed out"):
            send_telegram("hello", self.CONFIG)

    def test_nonpositive_explicit_timeout_fails(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            send_telegram("hello", self.CONFIG, timeout=0)


class MessageTests(unittest.TestCase):
    def test_turn_complete(self):
        message = build_message(
            {
                "type": "agent-turn-complete",
                "cwd": "/repo",
                "last-assistant-message": "All checks passed.",
            },
            "notify",
        )
        self.assertEqual(message, "✅ Codex finished\n/repo\n\nAll checks passed.")

    def test_permission_request(self):
        message = build_message(
            {
                "hook_event_name": "PermissionRequest",
                "tool_name": "Bash",
                "tool_input": {"description": "Allow network access?"},
            },
            "hook",
        )
        self.assertIn("Codex needs approval", message)
        self.assertIn("Allow network access?", message)

    def test_request_user_input(self):
        message = build_message(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "request_user_input",
                "tool_input": {
                    "questions": [{"question": "Which environment?"}]
                },
            },
            "hook",
        )
        self.assertIn("Codex needs your response", message)
        self.assertIn("Which environment?", message)

    def test_unrelated_hook_is_ignored(self):
        self.assertIsNone(
            build_message(
                {"hook_event_name": "PostToolUse", "tool_name": "Bash"},
                "hook",
            )
        )

    def test_process_exit(self):
        message = build_message(
            {"exit_code": 9, "cwd": "/repo"}, "process-exit"
        )
        self.assertIn("Codex stopped", message)
        self.assertIn("status 9", message)

    def test_long_message_is_truncated(self):
        message = build_message(
            {
                "type": "agent-turn-complete",
                "last-assistant-message": "x" * (MAX_TELEGRAM_TEXT + 100),
            },
            "notify",
        )
        self.assertEqual(len(message), MAX_TELEGRAM_TEXT)


class ExitBehaviorTests(unittest.TestCase):
    @patch("tele_codex.notifier.send_telegram", side_effect=TelegramError("offline"))
    def test_manual_test_failure_returns_nonzero(self, _mocked_send):
        with patch("tele_codex.notifier.load_config", return_value={}):
            with patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(cli(["--test"]), 1)

    def test_callback_parse_failure_fails_open(self):
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(cli(["not-json"]), 0)

    def test_dry_run_parse_failure_returns_nonzero(self):
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(cli(["--dry-run", "not-json"]), 1)


if __name__ == "__main__":
    unittest.main()
