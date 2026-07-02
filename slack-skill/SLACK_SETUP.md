# Slack Bridge Setup

This is the runbook for `slack_bridge.py`, the Socket Mode bridge that lets Fake Matt respond to Slack DMs and mentions through Claude Code.

## Runtime Shape

- The bridge listens through Slack Socket Mode.
- Socket Mode events are acknowledged immediately.
- Long Claude and dispatch work runs in separate bounded background worker pools.
- The bridge ignores bot-authored messages.
- Fake Matt intent confirmation is only active in the Fake Matt -> Matt DM channel: `D0B0T0ETDR8`.
- Confirmed external write-actions are delegated to `~/.claude/fakematt-today/dm_dispatch.py`.

## Required Slack App Settings

Use one Slack app with both:

- Bot token: `xoxb-...`
- App-level token: `xapp-...` with Socket Mode enabled

Required bot scopes:

- `app_mentions:read`
- `channels:history`
- `channels:read`
- `chat:write`
- `groups:history`
- `groups:read`
- `im:history`
- `im:read`
- `im:write`
- `mpim:history`
- `mpim:read`
- `reactions:read`
- `reactions:write`
- `users:read`

Optional but useful:

- `chat:write.public`
- `files:read`
- `search:read`

After changing scopes, reinstall the Slack app to the workspace and update the local token if Slack rotates it.

## Config File

`config.json` lives next to `slack_bridge.py`.

Use this shape:

```json
{
  "default": {
    "token": "xoxb-...",
    "app_token": "xapp-...",
    "workspace": "zerg",
    "allowed_users": ["U04R0EJACMR", "U0AFSSPNB1N"],
    "fm_dm_channel": "D0B0T0ETDR8"
  }
}
```

`allowed_users` is fail-closed: an empty list means nobody can trigger Claude. `fm_dm_channel` is the only DM where two-way intent confirmation can create pending actions.

Do not commit or paste real token values into docs, PRs, or Slack.

## Claude Path

By default the bridge uses:

```bash
~/.config/zerg/zclaude
```

Override with:

```bash
SLACK_BRIDGE_CLAUDE_BIN=/path/to/claude
```

The bridge must run outside Codex's filesystem sandbox when using `zclaude`, otherwise the router may fail to write its state file.

Optional worker tuning:

```bash
SLACK_BRIDGE_CLAUDE_WORKERS=2
SLACK_BRIDGE_CLAUDE_QUEUE=2
SLACK_BRIDGE_DISPATCH_WORKERS=4
SLACK_BRIDGE_DISPATCH_QUEUE=8
SLACK_BRIDGE_PROGRESS_DELAY_SECONDS=20
```

When a queue is full, the bridge rejects new work with a visible Slack "try again" message instead of silently queueing behind long-running Claude jobs.

`SLACK_BRIDGE_PROGRESS_DELAY_SECONDS` controls when the bridge posts a visible progress message. Fast replies that finish before this delay are posted directly as the only bot message. Slower replies get a progress note with a rough ETA, then a separate final response when Claude finishes.

## Start, Stop, Status

Start:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 ~/.claude/skills/slack-skill/slack_bridge.py --daemon --auto --workdir "/Users/mattheweisner/Obsidian/Zerg"
```

Stop:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 ~/.claude/skills/slack-skill/slack_bridge.py --stop
```

Status:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 ~/.claude/skills/slack-skill/slack_bridge.py --status
```

`--status` confirms PID liveness and reads `bridge_health.json`, including heartbeat age, Socket Mode connection state when the Slack SDK exposes it, worker state counts, and stale-heartbeat detection. The manual Slack smoke below is still the strongest end-to-end check.

## Manual Smoke Test

From Matt's Slack client, DM Fake Matt:

```text
just sending this to myself: https://example.com
```

Expected:

- Fake Matt adds an eyes reaction.
- Fake Matt does not reply.
- Claude is not invoked.

Then DM:

```text
Please reply with exactly: 4
```

Expected:

- Fake Matt replies with `4`.

The CLI Slack token sends as the bot, so it cannot replace this manual smoke. Bot-authored messages are intentionally ignored by the bridge.

## Automated Local Checks

Run tests for the Claude skill copy:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/slack_bridge_pycache /Library/Developer/CommandLineTools/usr/bin/python3 ~/.claude/skills/slack-skill/tests/test_slack_bridge_behavior.py
```

Run tests for the Codex skill copy:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/slack_bridge_pycache /Library/Developer/CommandLineTools/usr/bin/python3 ~/.codex/skills/slack-skill/tests/test_slack_bridge_behavior.py
```

Compile both bridge files:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/slack_bridge_pycache /Library/Developer/CommandLineTools/usr/bin/python3 -m py_compile ~/.claude/skills/slack-skill/slack_bridge.py ~/.codex/skills/slack-skill/slack_bridge.py
```

Bridge-level Claude smoke:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -c 'import importlib.util; p="/Users/mattheweisner/.claude/skills/slack-skill/slack_bridge.py"; s=importlib.util.spec_from_file_location("b", p); b=importlib.util.module_from_spec(s); s.loader.exec_module(b); b.WORK_DIR="/Users/mattheweisner/Obsidian/Zerg"; b.THREAD_SESSIONS={}; b.save_thread_sessions=lambda: None; print(b.run_claude_code("Please reply in Slack with exactly: 4", "Matt", "DM:Matt", "U0AFSSPNB1N", channel_id="DTEST"))'
```

Expected output includes:

```text
4
```

## State Files

Bridge-local state:

- `.bridge.pid`
- `.event_dedupe/`
- `bridge_health.json`
- `bridge.log`
- `dispatch_audit.jsonl`
- `inbox.jsonl`
- `pending_work.json`
- `thread_sessions.json`

Fake Matt action state:

- `~/.claude/fakematt-today/state_pending_actions.json`
- `~/.claude/fakematt-today/dm_dispatch.py`

## Known Limits

- `--status` includes best-effort Socket Mode health and heartbeat freshness, but Slack SDK connection internals can vary by version.
- `ACTIVE_THREADS` is in-memory and resets on daemon restart.
- The Slack CLI send path cannot simulate Matt's human-authored DM because it posts as the bot.
- `allowed_users` and `fm_dm_channel` are config-backed per workspace; update `config.json` before adding another trusted user or DM.
