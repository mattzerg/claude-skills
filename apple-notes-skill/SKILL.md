---
name: apple-notes-skill
description: Import Apple Notes into Matt's Obsidian vault and route idea-shaped notes into the idea-backlog. Reads Notes via osascript (Automation permission required). Notes whose title starts with "idea:" or that contain #idea become idea-backlog entries under MattZerg/Ideas/<category>/ (vault_path-staged writes); all other notes can be plain-imported to Notes/Apple Notes/. Modes — `list` (preview folders + flag idea notes, no writes), `ideas [--dry-run]` (route idea notes to the backlog), `import [--force]` (full plain import). USE PROACTIVELY when Matt says "import my notes", "check apple notes", "notes to ideas", "pull my apple notes", "turn my notes into ideas", or "sync apple notes to the vault". Degrades gracefully with a one-time-approval message if Notes access is denied. Never sends or deletes; vault writes only.
allowed-tools: Bash, Read, Write
---

# apple-notes-skill

Bridges Apple Notes into Matt's vault. The wiring lives in `run.py`; this file
documents how to invoke it.

## Commands

| Command | What it does |
|---|---|
| `list [--folder F]` | List Notes folders + titles, flag idea-shaped notes by title. No writes — safe preview. |
| `ideas [--dry-run] [--folder F] [--category C]` | Route idea-shaped notes → `MattZerg/Ideas/<category>/`. Scans bodies too (catches `#idea` anywhere). `--dry-run` prints planned writes without touching the vault. |
| `import [--force] [--folder F]` | Plain-import every note to `MattZerg/Notes/Apple Notes/<folder>/`. `--force` overwrites existing files. |

Run with the system Python so osascript Automation context is consistent:

```
/usr/bin/python3 ~/.claude/skills/apple-notes-skill/run.py list
/usr/bin/python3 ~/.claude/skills/apple-notes-skill/run.py ideas --dry-run
/usr/bin/python3 ~/.claude/skills/apple-notes-skill/run.py ideas
```

## Idea routing

A note is "idea-shaped" if its title starts with `idea:` (case-insensitive) OR
its title/body contains `#idea`. Such notes are written as idea-backlog entries
matching the idea schema (see `~/.claude/skills/idea-backlog/SKILL.md`):

- Frontmatter: `id`, `title`, `category`, `subcategory: apple-notes`, `tags`,
  `status: raw`, `conviction: medium`, `effort/time_estimate/cost_estimate:
  unknown`, `created`, `last_touched`, `sources`, `source: apple-notes`.
- Body: `## Idea` / `## Why interesting` / `## Open questions` / `## Source excerpt`.
- Category is inferred from folder + keywords (`zerg-product`, `zerg-content`,
  `zerg-tooling`, `personal-venture`, `personal-life`, `research`), overridable
  with `--category`. Default is `personal-venture`.

Writes go through the launchd-safe `vault_path.vault_write()` helper (staged to
`~/.zerg-vault-writeback/`, flushed to iCloud within ~60s), so the skill works
the same from cron and interactive contexts.

## Permissions

Apple Notes is read via `osascript`. The controlling process must hold
Automation permission for Notes. If access is denied (TCC / `-1743` / "not
allowed"), the skill exits non-zero with a one-line remediation: run
`list` once in **Terminal.app** and approve the "control Notes" prompt, then
re-run. It never crashes on a permission error.

## Hard rules

- Read-only against Apple Notes — never creates, edits, or deletes notes.
- Vault writes only (Ideas/ + Notes/Apple Notes/). Never publishes or sends.
- `ideas --dry-run` first when unsure; it shows every planned write.
