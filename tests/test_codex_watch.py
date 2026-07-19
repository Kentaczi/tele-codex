import io
import unittest
from unittest.mock import Mock, patch

from tele_codex import codex_runner


class CodexWatchTests(unittest.TestCase):
    @patch("tele_codex.codex_runner.shutil.which", return_value=None)
    def test_missing_codex_returns_127(self, _which):
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(codex_runner.main(), 127)

    @patch("tele_codex.codex_runner.send_telegram")
    @patch("tele_codex.codex_runner.subprocess.run", return_value=Mock(returncode=0))
    @patch("tele_codex.codex_runner.shutil.which", return_value="/usr/bin/codex")
    def test_success_does_not_notify(self, _which, _run, send):
        with patch("sys.argv", ["codex_watch.py"]):
            self.assertEqual(codex_runner.main(), 0)
        send.assert_not_called()

    @patch("tele_codex.codex_runner.load_config", return_value={})
    @patch("tele_codex.codex_runner.send_telegram")
    @patch("tele_codex.codex_runner.subprocess.run", return_value=Mock(returncode=7))
    @patch("tele_codex.codex_runner.shutil.which", return_value="/usr/bin/codex")
    def test_failure_notifies_and_preserves_exit(self, _which, _run, send, _config):
        with patch("sys.argv", ["codex_watch.py"]):
            self.assertEqual(codex_runner.main(), 7)
        self.assertIn("Codex stopped", send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
