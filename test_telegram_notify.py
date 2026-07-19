import unittest

from telegram_notify import build_message, looks_like_question


class QuestionClassificationTests(unittest.TestCase):
    def test_question_mark_needs_response(self):
        self.assertTrue(looks_like_question("Which option should I use?"))

    def test_confirmation_phrase_needs_response(self):
        self.assertTrue(looks_like_question("I need your confirmation before continuing."))

    def test_completed_statement_is_finished(self):
        self.assertFalse(looks_like_question("Implemented and verified all tests."))


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


if __name__ == "__main__":
    unittest.main()

