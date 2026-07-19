import io
import unittest
from unittest.mock import Mock, patch

import codex_watch


class CodexWatchTests(unittest.TestCase):
    @patch("codex_watch.shutil.which", return_value=None)
    def test_missing_codex_returns_127(self, _which):
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(codex_watch.main(), 127)

    @patch("codex_watch.send_telegram")
    @patch("codex_watch.subprocess.run", return_value=Mock(returncode=0))
    @patch("codex_watch.shutil.which", return_value="/usr/bin/codex")
    def test_success_does_not_notify(self, _which, _run, send):
        with patch("sys.argv", ["codex_watch.py"]):
            self.assertEqual(codex_watch.main(), 0)
        send.assert_not_called()

    @patch("codex_watch.load_config", return_value={})
    @patch("codex_watch.send_telegram")
    @patch("codex_watch.subprocess.run", return_value=Mock(returncode=7))
    @patch("codex_watch.shutil.which", return_value="/usr/bin/codex")
    def test_failure_notifies_and_preserves_exit(self, _which, _run, send, _config):
        with patch("sys.argv", ["codex_watch.py"]):
            self.assertEqual(codex_watch.main(), 7)
        self.assertIn("Codex stopped", send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

