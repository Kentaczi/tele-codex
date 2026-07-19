# tele-codex

Telegram notifications for local Codex sessions, with no third-party Python
dependencies.

It can notify you when:

- a Codex turn finishes;
- the last response appears to require your reply;
- Codex requests command, network, filesystem, or app approval;
- Codex opens an explicit user-input prompt; or
- a Codex CLI process launched through the optional wrapper exits abnormally.

For clients that expose the Codex App Server event stream, the optional watcher
also reports exact completed, interrupted, failed, input-request, and approval
events, with configurable inactivity alerts.

## How it works

Codex's user-level `notify` command receives `agent-turn-complete` events as a
JSON argument. Lifecycle hooks receive JSON on standard input. This project
translates those payloads into Telegram Bot API `sendMessage` requests.

The finished-versus-needs-response distinction is necessarily heuristic because
the external `notify` event currently reports turn completion, not a separate
"needs input" status. Approval requests are handled directly by hooks. The
`request_user_input` hook is best-effort because specialized tool paths can vary
by Codex surface; App Server events are the exact integration path.

## Requirements

- Codex local client (desktop app, CLI, or IDE integration)
- Python 3.9+
- A Telegram bot and chat ID

## 1. Create a Telegram bot

1. Open `@BotFather` in Telegram.
2. Run `/newbot` and keep the returned token private.
3. Send one message to the new bot.
4. Retrieve your chat ID:

   ```bash
   read -s TELEGRAM_BOT_TOKEN
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates"
   unset TELEGRAM_BOT_TOKEN
   ```

   Find the numeric value under `result[].message.chat.id`.

Telegram bot tokens grant full control of the bot. Never commit or share one.

## 2. Install the notifier

Clone the repository and install it in an isolated virtual environment:

```bash
git clone https://github.com/Kentaczi/tele-codex.git
cd tele-codex
python3 -m venv .venv
.venv/bin/python -m pip install .
cp telegram.example.json ~/.codex/telegram.json
chmod 600 ~/.codex/telegram.json
```

Edit `~/.codex/telegram.json` and insert your bot token and chat ID. You can
instead provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the environment.

Test the connection:

```bash
.venv/bin/tele-codex --test
```

This command returns a non-zero status if credentials, networking, or the
Telegram API are not working. `TELEGRAM_HTTP_TIMEOUT` can override the default
five-second request deadline.

## 3. Configure Codex

Add the following to the user-level `~/.codex/config.toml`:

```toml
notify = [
  "/ABSOLUTE/PATH/TO/tele-codex/.venv/bin/tele-codex"
]

[[hooks.PermissionRequest]]
matcher = ".*"

[[hooks.PermissionRequest.hooks]]
type = "command"
command = '"/ABSOLUTE/PATH/TO/tele-codex/.venv/bin/tele-codex"'
timeout = 20

[[hooks.PreToolUse]]
matcher = "^request_user_input$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '"/ABSOLUTE/PATH/TO/tele-codex/.venv/bin/tele-codex"'
timeout = 20
```

Replace `/ABSOLUTE/PATH/TO` with the checkout's absolute parent path, restart
Codex, and approve the hook trust prompt if one appears. The `notify` setting
must be user-level; Codex ignores it in project `.codex/config.toml` files.

The `PermissionRequest` hook is part of Codex's documented lifecycle hook
contract. The `request_user_input` matcher is a convenient best-effort path for
local clients. A completed final response is also classified heuristically as
"needs your response" when it ends with a question or an input-related phrase.

## Optional: abnormal CLI exit notifications

Then launch CLI sessions with:

```bash
.venv/bin/tele-codex-watch
```

The wrapper sends a red notification if the Codex process returns a non-zero
status. It deliberately does not kill or label a long-running task as stalled.
A genuine freeze cannot trigger an in-process hook; reliable hang detection
requires an independent supervisor or an App Server client with a carefully
chosen inactivity policy.

## Optional: exact App Server state watcher

`app_server_watch.py` consumes a mirrored Codex App Server JSONL event stream.
It recognizes exact input requests, approval requests, and
`turn/completed` statuses (`completed`, `interrupted`, or `failed`). While a
turn is active, it can report prolonged inactivity once per quiet period.

Have your App Server client mirror each received JSON-RPC message as one JSON
object per line, then pipe that stream into:

```bash
your-app-server-event-tap | \
  .venv/bin/tele-codex-app-server --stall-seconds 900
```

Use `--dry-run` to print notifications during integration testing and
`--stall-seconds 0` to disable inactivity alerts. The watcher is an event-stream
consumer; it does not attach to an already-running desktop or CLI session and
does not declare that inactivity proves a hang.

If the same session also uses the basic `notify` command, both integrations can
report turn completion. Disable one completion path in your event tap or accept
the duplicate when evaluating the watcher.

## Test locally

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q tele_codex tests *.py
.venv/bin/tele-codex --dry-run \
  '{"type":"agent-turn-complete","cwd":"/tmp/demo","last-assistant-message":"All checks passed."}'
```

## Project structure

Core behavior lives in the `tele_codex` package:

- `config.py` loads and validates credentials and runtime settings;
- `telegram.py` contains the Telegram transport;
- `messages.py` translates Codex callbacks into notification text;
- `notifier.py` handles completion and hook callbacks;
- `codex_runner.py` supervises Codex CLI exits; and
- `app_server.py` tracks exact App Server lifecycle events.

The three top-level Python scripts are thin compatibility entry points. Tests
live under `tests/`, while `pyproject.toml` defines the installable commands.

## References

- [Codex notifications](https://developers.openai.com/codex/config-advanced#notifications)
- [Codex hooks](https://developers.openai.com/codex/hooks)
- [Codex App Server events](https://developers.openai.com/codex/app-server#events)
- [Telegram bot tutorial](https://core.telegram.org/bots/tutorial)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## License

MIT
