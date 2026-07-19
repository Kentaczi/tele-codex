import unittest

from app_server_watch import StateTracker


class StateTrackerTests(unittest.TestCase):
    def test_exact_input_request(self):
        tracker = StateTracker()
        messages = tracker.handle(
            {
                "method": "item/tool/requestUserInput",
                "params": {
                    "turnId": "turn-1",
                    "questions": [{"question": "Deploy to production?"}],
                },
            },
            now=10,
        )
        self.assertIn("needs your response", messages[0])
        self.assertIn("Deploy to production?", messages[0])

    def test_permission_request(self):
        tracker = StateTracker()
        messages = tracker.handle(
            {
                "method": "item/permissions/requestApproval",
                "params": {"turnId": "turn-1", "reason": "Allow example.com"},
            },
            now=10,
        )
        self.assertIn("needs approval", messages[0])
        self.assertIn("Allow example.com", messages[0])

    def test_completed_turn(self):
        tracker = StateTracker()
        tracker.handle(
            {"method": "turn/started", "params": {"turn": {"id": "turn-1"}}},
            now=0,
        )
        messages = tracker.handle(
            {
                "method": "turn/completed",
                "params": {"turn": {"id": "turn-1", "status": "completed"}},
            },
            now=5,
        )
        self.assertIn("Codex finished", messages[0])
        self.assertNotIn("turn-1", tracker.active)

    def test_failed_turn_includes_error(self):
        tracker = StateTracker()
        messages = tracker.handle(
            {
                "method": "turn/completed",
                "params": {
                    "turn": {
                        "id": "turn-1",
                        "status": "failed",
                        "error": {"message": "Model connection failed"},
                    }
                },
            },
            now=5,
        )
        self.assertIn("Codex failed", messages[0])
        self.assertIn("Model connection failed", messages[0])

    def test_interrupted_turn(self):
        tracker = StateTracker()
        messages = tracker.handle(
            {
                "method": "turn/completed",
                "params": {"turn": {"id": "turn-1", "status": "interrupted"}},
            },
            now=5,
        )
        self.assertIn("Codex interrupted", messages[0])

    def test_stall_notifies_once_until_new_activity(self):
        tracker = StateTracker(stall_seconds=10)
        tracker.handle(
            {"method": "turn/started", "params": {"turn": {"id": "turn-1"}}},
            now=0,
        )
        self.assertEqual(tracker.check_stalls(now=9), [])
        self.assertEqual(len(tracker.check_stalls(now=10)), 1)
        self.assertEqual(tracker.check_stalls(now=20), [])

        tracker.handle(
            {
                "method": "item/started",
                "params": {"turnId": "turn-1", "item": {}},
            },
            now=21,
        )
        self.assertEqual(len(tracker.check_stalls(now=31)), 1)

    def test_zero_disables_stalls(self):
        tracker = StateTracker(stall_seconds=0)
        tracker.handle(
            {"method": "turn/started", "params": {"turn": {"id": "turn-1"}}},
            now=0,
        )
        self.assertEqual(tracker.check_stalls(now=999), [])


if __name__ == "__main__":
    unittest.main()

