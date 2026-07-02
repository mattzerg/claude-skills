---
name: apple-captures-skill
description: Read Matt's Apple Notes + Reminders captures. Quick voice-and-pencil scratch that lives outside the vault. Read-only via AppleScript. Verbs — `notes recent [--days N]`, `notes search <query>`, `reminders open`, `reminders search <query>`. v1 ships Notes + Reminders; Voice Memos deferred (need Whisper transcription pipeline; no current local recordings found at `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings`). Sibling to fakematt-operator — feeds idea-backlog with stranded captures.
---

# apple-captures-skill

Read Apple Notes + Reminders captures via AppleScript. No write, no delete.

## Verbs

### `notes recent [--days N]`
List notes modified in the last N days (default 14). Output: `[mod-date] folder/title  preview…`.

```bash
python3 ~/.claude/skills/apple-captures-skill/read_captures.py notes recent --days 7
```

### `notes search <query>`
Full-body search across Notes. Returns matching notes with snippets.

```bash
python3 ~/.claude/skills/apple-captures-skill/read_captures.py notes search "zergvert"
```

### `reminders open`
List open (incomplete) reminders across all lists.

```bash
python3 ~/.claude/skills/apple-captures-skill/read_captures.py reminders open
```

### `reminders search <query>`
Search reminder names (including completed).

```bash
python3 ~/.claude/skills/apple-captures-skill/read_captures.py reminders search "Idan"
```

## Deferred: Voice Memos

No recordings found at `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/` on 2026-05-23. Voice Memos may sync to iCloud Drive (`~/Library/Mobile Documents/com~apple~VoiceMemos/`) which wasn't present either. If Matt starts using Voice Memos again, add a `voicememos` subcommand that points at the right path + runs Whisper transcription.

## TCC permissions

First run will prompt for Automation access to Notes / Reminders. Approve. If denied, the script prints what to do at `System Settings → Privacy → Automation`.

## When to use

- "Did I jot something down about X" — Notes is the most likely place.
- fakematt-operator triage when Matt forwards a note.
- idea-backlog ingestion — Notes / Reminders are where ideas die.

## Read-only

AppleScript `get` operations only. Never `make`, `set`, or `delete`.
