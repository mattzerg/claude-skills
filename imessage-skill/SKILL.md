---
name: imessage-skill
description: Read Matt's local iMessage history (chat.db). Read-only — never sends, edits, or deletes. Verbs — `recent [--hours N]` (most recent messages), `from <name-or-handle>` (filter to one contact, supports partial phone/email match), `search <query>` (full-text across messages), `threads` (list active threads). Backed by `~/Library/Messages/chat.db`. Sibling to slack-skill / whatsapp-skill — covers personal SMS/iMessage that doesn't go through Slack.
---

# imessage-skill

Read-only access to Matt's local iMessage SQLite DB at `~/Library/Messages/chat.db`. 336k+ messages. Never writes back.

## Verbs

### `recent [--hours N] [--limit N]`
Most recent messages across all threads, newest first. Default: last 24h, limit 50.

```bash
python3 ~/.claude/skills/imessage-skill/read_imessage.py recent --hours 24
```

### `from <handle>`
Messages from a specific contact. `<handle>` is a partial substring match against phone number or email. Use `threads` first to find canonical handles.

```bash
python3 ~/.claude/skills/imessage-skill/read_imessage.py from "idan"
python3 ~/.claude/skills/imessage-skill/read_imessage.py from "+14155551234"
```

### `search <query> [--hours N]`
Substring search across message text. Default window: last 30 days.

```bash
python3 ~/.claude/skills/imessage-skill/read_imessage.py search "zergvert"
```

### `threads [--limit N]`
List recently-active threads with their canonical handles and last-message preview.

```bash
python3 ~/.claude/skills/imessage-skill/read_imessage.py threads --limit 20
```

## Output format

`[YYYY-MM-DD HH:MM] <→|←> <handle>  text`

- `→` = Matt sent it (is_from_me=1)
- `←` = Matt received it

## When to use

- Before claiming "Idan/customer/family hasn't said anything about X" — iMessage is invisible to slack-skill and gmail-skill.
- During fakematt-operator triage when Matt forwards an iMessage thread for context.
- When morning-brief / standup needs personal-comms signal.
- Pairs with `feedback_check_in_flight_across_silos.md` — iMessage is a silo currently uncovered.

## Limitations

- Messages stored as `attributedBody` blob (no plain text) are silently skipped — these are styled messages, reactions, and tapbacks. Plain-text messages cover ~95% of normal conversation.
- Group chat detection is basic — uses `cache_roomnames`. Multi-party threads show one handle per row.
- Date column is Apple-nano-epoch (ns since 2001-01-01); conversion handled internally.

## Read-only

Opens `chat.db` with `mode=ro`. Never writes.
