# tele-codex

Telegram notifications for local Codex sessions, with no third-party Python
dependencies.

It can notify you when:

- a Codex turn finishes;
- the last response appears to require your reply;
- Codex requests command, network, filesystem, or app approval;
- Codex opens an explicit user-input prompt; or
- a Codex CLI process launched through the optional wrapper exits abnormally.

## How it works

Codex's user-level `notify` command receives `agent-turn-complete` events as a
JSON argument. Lifecycle hooks receive JSON on standard input. This project
translates those payloads into Telegram Bot API `sendMessage` requests.

The finished-versus-needs-response distinction is necessarily heuristic because
the external `notify` event currently reports turn completion, not a separate
"needs input" status. Explicit input prompts and approval requests are handled
directly by hooks.

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

From this repository:

```bash
install -m 700 telegram_notify.py ~/.codex/telegram_notify.py
cp telegram.example.json ~/.codex/telegram.json
chmod 600 ~/.codex/telegram.json
```

Edit `~/.codex/telegram.json` and insert your bot token and chat ID. You can
instead provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the environment.

Test the connection:

```bash
/usr/bin/python3 ~/.codex/telegram_notify.py --test
```

## 3. Configure Codex

Add the following to the user-level `~/.codex/config.toml`:

```toml
notify = [
  "/usr/bin/python3",
  "/Users/YOU/.codex/telegram_notify.py"
]

[[hooks.PermissionRequest]]
matcher = ".*"

[[hooks.PermissionRequest.hooks]]
type = "command"
command = '/usr/bin/python3 "/Users/YOU/.codex/telegram_notify.py"'
timeout = 15

[[hooks.PreToolUse]]
matcher = "^request_user_input$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "/Users/YOU/.codex/telegram_notify.py"'
timeout = 15
```

Replace `/Users/YOU` with your home directory, restart Codex, and approve the
hook trust prompt if one appears. The `notify` setting must be user-level;
Codex ignores it in project `.codex/config.toml` files.

## Optional: abnormal CLI exit notifications

Install the wrapper beside the notifier:

```bash
install -m 700 codex_watch.py ~/.codex/codex_watch.py
```

Then launch CLI sessions with:

```bash
/usr/bin/python3 ~/.codex/codex_watch.py
```

The wrapper sends a red notification if the Codex process returns a non-zero
status. It deliberately does not kill or label a long-running task as stalled.
A genuine freeze cannot trigger an in-process hook; reliable hang detection
requires an independent supervisor or an App Server client with a carefully
chosen inactivity policy.

## Test locally

```bash
python3 -m unittest -v
python3 telegram_notify.py --dry-run \
  '{"type":"agent-turn-complete","cwd":"/tmp/demo","last-assistant-message":"All checks passed."}'
```

## References

- [Codex notifications](https://developers.openai.com/codex/config-advanced#notifications)
- [Codex hooks](https://developers.openai.com/codex/hooks)
- [Codex App Server events](https://developers.openai.com/codex/app-server#events)
- [Telegram bot tutorial](https://core.telegram.org/bots/tutorial)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## License

MIT
