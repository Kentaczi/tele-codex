"""Allow ``python -m tele_codex`` to run the notifier."""

from .notifier import cli

raise SystemExit(cli())
