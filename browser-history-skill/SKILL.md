---
name: browser-history-skill
description: Read Matt's local browser history across Chrome, Safari, and Brave. Read-only — never writes. Verbs — `recent [--hours N]`, `search <query>`, `for-domain <domain>`. Backed by per-browser SQLite DBs at standard macOS locations. Copies the DB file before reading to dodge SQLITE_BUSY when a browser is open. Feeds idea-backlog (what Matt has been reading), competitive-review (matt-was-on-this-page-already), and "what was that link from earlier."
---

# browser-history-skill

Read recent URLs from Chrome, Safari, and Brave. Read-only.

## Verbs

### `recent [--hours N] [--limit N] [--browser X]`
Most recent visits across all browsers (or one). Default: 24h, 50 rows.

```bash
python3 ~/.claude/skills/browser-history-skill/read_history.py recent --hours 24
python3 ~/.claude/skills/browser-history-skill/read_history.py recent --browser chrome
```

### `search <query>`
Substring match across URL + title. Default window: 30 days.

```bash
python3 ~/.claude/skills/browser-history-skill/read_history.py search "zergai.com"
```

### `for-domain <domain>`
All visits to a domain. Useful for "have I been on Durable's pricing page lately."

```bash
python3 ~/.claude/skills/browser-history-skill/read_history.py for-domain durable.co
```

## Output

`[YYYY-MM-DD HH:MM] <browser>  <url>   "<title>"`

## How it dodges DB locks

Chrome and Brave lock their `History` SQLite file while the browser runs. The script copies to `/tmp/` first, then reads. Safari is safer but uses the same pattern for consistency.

## When to use

- Before recommending a URL Matt already visited.
- Feeding idea-backlog with "Matt's been reading X" signals.
- competitive-review when Matt mentions a competitor he was just looking at.
- "What was that page from this morning."

## Read-only

Reads from copy in `/tmp/`. Never touches the canonical browser DBs.
